"""Golden-file tests for the files people download or receive: the dashboard's Download CSV (sensor and sampling,
api/services/exports.py and the /api/exports/* routes), the monthly file sent to Borealis and SharePoint
(scripts/upload_data.py), the sampling template and an uploaded sampling file read back through /api/samples and
/api/recent. Each output is compared byte for byte with a file in tests/golden/ (see the README there: a difference
means the public file format changed). UPDATE_GOLDEN=1 rewrites the golden files instead of comparing.

Every test runs on SQLite and, with TEST_POSTGRES_URL set (as in CI), on PostgreSQL, against the same golden files.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import csv
import datetime as dt
import difflib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest.mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database

from config import Config  # noqa: E402
from api.services.exports import write_export_csv  # noqa: E402
from utils.sampling_csv import validate_csv  # noqa: E402

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden"
UPDATE = os.getenv("UPDATE_GOLDEN") == "1"


def check_golden(test, name, actual: bytes):
    """Compare `actual` with tests/golden/<name>, or write it there with UPDATE_GOLDEN=1."""
    path = GOLDEN / name
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(actual)
        return
    test.assertTrue(path.exists(), f"{path} is missing; create it with UPDATE_GOLDEN=1 (tests/golden/README.md)")
    expected = path.read_bytes()
    if actual != expected:
        diff = "".join(difflib.unified_diff(
            [repr(line) + "\n" for line in expected.decode("utf-8").splitlines(keepends=True)],
            [repr(line) + "\n" for line in actual.decode("utf-8").splitlines(keepends=True)],
            f"golden/{name}", "actual"))
        test.fail(f"{name} differs from its golden file. If the format change is intended, regenerate it with "
                  f"UPDATE_GOLDEN=1 (tests/golden/README.md).\n{diff}")


def ties_sorted(test, text: str, time_column: int) -> bytes:
    """A sampling CSV with the rows of each timestamp sorted. The export orders rows by time only, so readings
    taken at the same time (one site's parameters, or sites visited together) come in no defined order, and the
    order differs between databases. Checks the timestamps never go backwards on the way."""
    lines = text.split("\r\n")
    test.assertEqual(lines[-1], "", "the file ends with a line break")
    header, body = lines[0], lines[1:-1]
    times = [row[time_column] for row in csv.reader(body)]
    test.assertEqual(len(times), len(body), "one line per row")
    test.assertEqual(times, sorted(times), "rows are in time order")
    ordered = sorted(zip(times, body))
    return "\r\n".join([header] + [line for _, line in ordered] + [""]).encode("utf-8")


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


# Sensor readings as ingestion stores them: naive America/Toronto wall time. The same readings feed the dashboard
# export and the monthly file. Hand-checkable on purpose: three groups, two configured loggers and one that isn't
# configured, readings and whole groups missing, one stored NULL, a unit change (Turbidity FNU, then NTU), " asl"
# in a unit, numbers in several shapes, and these times:
#   2026-10-01 00:00  first reading of October
#   2026-10-31 01:00  early on the first picked day: in the Download CSV (Oct 31 00:00 Toronto is 04:00 UTC)
#   2026-10-31 23:45  last reading of October
#   2026-11-01 00:00  midnight on the 1st: November's file only
#   2026-11-01 01:30  the hour repeated when clocks fall back; stored once (the unique key has no offset)
#   2026-11-01 02:00
#   2026-11-02 03:00  after the last picked day: not in the Download CSV, though 03:00 is before its end bound
#                     read as wall time (2026-11-02T04:59:59.999Z is Nov 1 23:59:59.999 Toronto)
#   2026-11-30 23:45  last reading of November
#   2026-12-01 00:00  in neither file
# No value is a vendor "no reading" sentinel (e.g. -100000): the export passes values through unfiltered, and these
# files pin the format, not sentinel handling.
WEATHER, QUALITY = "22051538", "4501"
WSE, WT = "Water Surface Elevation", "Water Temperature"


def sensor_readings():
    t = dt.datetime
    rows = [
        (t(2026, 10, 1, 0, 0), WEATHER, "Weather", "Air Temperature", "°C", 12.5),
        (t(2026, 10, 1, 0, 0), WEATHER, "Weather", "Rain", "mm", 0.0),
        (t(2026, 10, 1, 0, 0), QUALITY, "Quality", "Turbidity", "FNU", 3.2),
        (t(2026, 10, 1, 0, 0), "2577531", "Logger", WSE, "m asl", 85.123),
        (t(2026, 10, 1, 0, 0), "2577531", "Logger", WT, "°C", 11.0),

        (t(2026, 10, 31, 1, 0), WEATHER, "Weather", "Air Temperature", "°C", 1.5),

        (t(2026, 10, 31, 23, 45), WEATHER, "Weather", "Air Temperature", "°C", -2.5),
        (t(2026, 10, 31, 23, 45), QUALITY, "Quality", "Turbidity", "FNU", 4.0),
        (t(2026, 10, 31, 23, 45), QUALITY, "Quality", WT, "°C", 6.25),
        (t(2026, 10, 31, 23, 45), "2577531", "Logger", WSE, "m asl", 85.2),
        (t(2026, 10, 31, 23, 45), "2577531", "Logger", WT, "°C", 4.0),
        (t(2026, 10, 31, 23, 45), "2577533", "Logger", WSE, "m asl", 84.95),

        (t(2026, 11, 1, 0, 0), WEATHER, "Weather", "Air Temperature", "°C", -3.0),
        (t(2026, 11, 1, 0, 0), WEATHER, "Weather", "Rain", "mm", 0.2),
        (t(2026, 11, 1, 0, 0), "2577531", "Logger", WSE, "m asl", 85.21),
        (t(2026, 11, 1, 0, 0), "2577531", "Logger", WT, "°C", None),
        (t(2026, 11, 1, 0, 0), "2577533", "Logger", WSE, "m asl", 84.96),
        (t(2026, 11, 1, 0, 0), "2577533", "Logger", WT, "°C", 4.5),

        (t(2026, 11, 1, 1, 30), WEATHER, "Weather", "Air Temperature", "°C", -3.5),
        (t(2026, 11, 1, 1, 30), WEATHER, "Weather", "Rain", "mm", 0.0),
        (t(2026, 11, 1, 1, 30), QUALITY, "Quality", "Turbidity", "NTU", 5.5),
        (t(2026, 11, 1, 1, 30), QUALITY, "Quality", WT, "°C", 6.0),
        (t(2026, 11, 1, 1, 30), "2577531", "Logger", WSE, "m asl", 85.22),
        (t(2026, 11, 1, 1, 30), "2577531", "Logger", WT, "°C", 4.25),
        (t(2026, 11, 1, 1, 30), "2577599", "Logger", WSE, "m asl", 85.0),
        (t(2026, 11, 1, 1, 30), "2577599", "Logger", WT, "°C", 5.0),

        (t(2026, 11, 1, 2, 0), WEATHER, "Weather", "Air Temperature", "°C", -4.0),
        (t(2026, 11, 1, 2, 0), WEATHER, "Weather", "Rain", "mm", 1e-05),
        (t(2026, 11, 1, 2, 0), QUALITY, "Quality", "Turbidity", "NTU", 0.30000000000000004),
        (t(2026, 11, 1, 2, 0), "2577533", "Logger", WSE, "m asl", 84.97),
        (t(2026, 11, 1, 2, 0), "2577533", "Logger", WT, "°C", 4.5),

        (t(2026, 11, 2, 3, 0), WEATHER, "Weather", "Air Temperature", "°C", -5.0),

        (t(2026, 11, 30, 23, 45), WEATHER, "Weather", "Air Temperature", "°C", 1.0),
        (t(2026, 11, 30, 23, 45), WEATHER, "Weather", "Pressure", "mbar", 1013.25),
        (t(2026, 11, 30, 23, 45), QUALITY, "Quality", "Turbidity", "NTU", 48.0),

        (t(2026, 12, 1, 0, 0), WEATHER, "Weather", "Air Temperature", "°C", 0.5),
    ]
    return [dict(recorded_at=when, station_id=station, group_type=group, measurement_type=metric, unit=unit,
                 value=value) for when, station, group, metric, unit, value in rows]


# A measurement name a spreadsheet would run as a formula. The dashboard export prefixes such text with an
# apostrophe. Loaded for the dashboard export only (the monthly file doesn't prefix; see the README).
FORMULA_METRIC = '=HYPERLINK("http://example.invalid","x")'


def sensor_readings_with_formula():
    return sensor_readings() + [dict(recorded_at=dt.datetime(2026, 11, 1, 1, 30), station_id=QUALITY,
                                     group_type="Quality", measurement_type=FORMULA_METRIC, unit="", value=7.0)]


# The sampling file a researcher uploads (golden/sampling_upload.csv, the documented format: several creeks and
# sites, name and unit aliases, a below-detection value, a blank and a rejected row that are skipped, a time in the
# fall-back hour, no time, a quoted comma, and a reading early on Nov 3 that a download of Oct 31-Nov 2 leaves out),
# read by the validator into rows. Plus rows that didn't come through the validator (older imports) with text a
# spreadsheet would run, to check the export neutralizes it.
def sampling_rows():
    result = validate_csv(GOLDEN / "sampling_upload.csv")
    assert result.ok, [str(e) for e in result.errors]
    formula_rows = [
        dict(site_id='=HYPERLINK("http://example.invalid")', creek_id="+19431905", measurement_type="@pH",
             unit="-", value=-3.5, recorded_at=dt.datetime(2026, 11, 2, 15, 0)),
    ]
    return result.records + formula_rows


# What the dashboard sends: the picked days' Toronto midnight and 23:59:59.999, in UTC
SENSOR_ALL = {"domain": "sensor", "start": "2026-10-31T04:00:00.000Z", "end": "2026-11-02T04:59:59.999Z",
              "group_types": ["Weather", "Quality", "Logger"], "measurement_types": [], "station_ids": []}
SENSOR_ALL_NAME = "WELLWestCampus_WaterLogger_WaterQuality_WeatherStation_20261031_20261101.csv"
SENSOR_CHOSEN = {"domain": "sensor", "start": "2026-11-01T04:00:00.000Z", "end": "2026-11-02T04:59:59.999Z",
                 "group_types": ["Logger"], "station_ids": ["2577533", "2577599"],
                 "group_measurement_types": {"Logger": [WT, WSE]}}
SENSOR_CHOSEN_NAME = "WELLWestCampus_WaterLogger_20261101_20261101.csv"
SAMPLING_ALL = {"domain": "sampling", "start": "2026-10-31T04:00:00.000Z", "end": "2026-11-03T04:59:59.999Z"}
SAMPLING_ALL_NAME = "well_export_sampling_20261031_20261102.csv"


class DatabaseCase(unittest.TestCase):
    """A Flask app on a database of its own (cls.uri), with cls.load() run once."""

    uri = None  # set by setUpClass of the SQLite and PostgreSQL subclasses

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp(prefix="golden-csv-")
        cls.exports = os.path.join(cls.tmp, "exports")
        uri = cls.uri or f"sqlite:///{os.path.join(cls.tmp, 'golden.db')}"
        cls.patches = [unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", uri),
                       unittest.mock.patch.object(Config, "EXPORTS_DIR", cls.exports)]
        for patch in cls.patches:
            patch.start()
        from server import create_app
        from db.database import db
        cls.db = db
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.drop_all()   # a PostgreSQL database shared with other tests may still hold their tables
        db.create_all()
        cls.load()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.drop_all()
        cls.db.engine.dispose()
        cls.ctx.pop()
        for patch in cls.patches:
            patch.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def load(cls):
        raise NotImplementedError

    @classmethod
    def add_sensor(cls, readings):
        from db.models import SensorMeasurement
        cls.db.session.add_all(SensorMeasurement(**r) for r in readings)
        cls.db.session.commit()

    def export(self, payload) -> bytes:
        path = os.path.join(self.tmp, "export.csv")
        write_export_csv(payload, path)
        return pathlib.Path(path).read_bytes()


class SensorExport:
    """The dashboard's sensor Download CSV, from the service and through the export routes."""

    @classmethod
    def load(cls):
        cls.add_sensor(sensor_readings_with_formula())

    def test_every_group(self):
        data = self.export(SENSOR_ALL)
        check_golden(self, "sensor_export_all_groups.csv", data)
        rows = list(csv.reader(io.StringIO(data.decode("utf-8"), newline="")))
        header = rows[0]
        self.assertEqual(header[:3], ["ID", "Timestamp", "Group"])
        self.assertEqual([h for h in header if h == "Group"], ["Group"] * 3)
        self.assertEqual(header.count("Sensor"), 6)  # the five configured loggers, then one seen in the data
        self.assertIn("Turbidity: NTU", header)  # the latest reading's unit names the column
        self.assertIn(f"{WSE}: m", header)  # " asl" dropped
        self.assertIn("'" + FORMULA_METRIC, header)
        # Toronto wall time from the picked days (sent in UTC); the fall-back hour's reading once
        self.assertEqual([r[1] for r in rows[1:]], ["2026-10-31T01:00:00", "2026-10-31T23:45:00",
                                                     "2026-11-01T00:00:00", "2026-11-01T01:30:00",
                                                     "2026-11-01T02:00:00"])
        self.assertEqual([r[0] for r in rows[1:]], ["1", "2", "3", "4", "5"])

    def test_chosen_loggers_and_metrics(self):
        data = self.export(SENSOR_CHOSEN)
        check_golden(self, "sensor_export_two_loggers.csv", data)
        header = next(csv.reader(io.StringIO(data.decode("utf-8"), newline="")))
        self.assertEqual(header, ["ID", "Timestamp", "Group", "Sensor", f"{WT}: °C", f"{WSE}: m",
                                  "Sensor", f"{WT}: °C", f"{WSE}: m"])

    def test_file_names(self):
        from api.services.exports import default_export_filename, normalize_export_payload
        self.assertEqual(default_export_filename(normalize_export_payload(SENSOR_ALL)), SENSOR_ALL_NAME)
        self.assertEqual(default_export_filename(normalize_export_payload(SENSOR_CHOSEN)), SENSOR_CHOSEN_NAME)

    def test_estimate_route(self):
        response = self.app.test_client().post("/api/exports/estimate", json=SENSOR_ALL)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        # Readings from Oct 31 01:00 to Nov 1 02:00, the formula-named one included
        self.assertEqual((body["estimated_rows"], body["recommended_mode"]), (27, "sync"))

    def test_sync_route(self):
        for payload, golden, name in ((SENSOR_ALL, "sensor_export_all_groups.csv", SENSOR_ALL_NAME),
                                      (SENSOR_CHOSEN, "sensor_export_two_loggers.csv", SENSOR_CHOSEN_NAME)):
            with self.subTest(name):
                response = self.app.test_client().post("/api/exports/sync", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/csv")
                self.assertEqual(response.headers["Content-Disposition"], f"attachment; filename={name}")
                check_golden(self, golden, response.data)
                response.close()
        # The temporary file is removed after sending
        self.assertEqual([f for f in os.listdir(self.exports) if f.startswith("sync_export_")], [])

    def test_job_routes(self):
        from tasks import exports as export_tasks
        client = self.app.test_client()
        with unittest.mock.patch.object(export_tasks.generate_export_job, "delay") as delay:
            response = client.post("/api/exports/jobs", json=SENSOR_ALL, headers={"X-Forwarded-For": "192.0.2.1"})
        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["job_id"]
        delay.assert_called_once_with(job_id)

        status = client.get(f"/api/exports/jobs/{job_id}").get_json()
        self.assertEqual((status["status"], status["download_ready"]), ("queued", False))
        self.assertEqual(client.get(f"/api/exports/jobs/{job_id}/download").status_code, 409)

        with unittest.mock.patch.object(export_tasks, "worker_app", return_value=self.app):
            export_tasks.generate_export_job(job_id)
        self.db.session.expire_all()
        status = client.get(f"/api/exports/jobs/{job_id}").get_json()
        self.assertEqual((status["status"], status["download_ready"], status["produced_rows"],
                          status["progress_pct"], status["artifact_name"]), ("ready", True, 27, 100.0, SENSOR_ALL_NAME))

        response = client.get(f"/api/exports/jobs/{job_id}/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertEqual(response.headers["Content-Disposition"], f"attachment; filename={SENSOR_ALL_NAME}")
        check_golden(self, "sensor_export_all_groups.csv", response.data)
        response.close()
        self.assertEqual(client.get("/api/exports/jobs/no-such-job").status_code, 404)


class MonthlyFile:
    """The monthly file scripts/upload_data.py sends to Borealis (and scripts/sharepoint_upload.py to SharePoint),
    built through exported_month(), the function both call."""

    @classmethod
    def load(cls):
        cls.add_sensor(sensor_readings())

    def month(self, year, month):
        from scripts import upload_data
        with contextlib.redirect_stdout(io.StringIO()):
            name, content, folder = upload_data.exported_month(
                upload_data.parse_args(["--year", str(year), "--month", str(month)]))
        self.assertEqual(folder, year)
        return name, content.encode("utf-8")

    def test_october_and_november(self):
        for (year, month), expected_name in (((2026, 10), "WELLWestCampus_Oct2026.csv"),
                                             ((2026, 11), "WELLWestCampus_Nov2026.csv")):
            with self.subTest(expected_name):
                name, data = self.month(year, month)
                self.assertEqual(name, expected_name)
                check_golden(self, f"monthly/{expected_name}", data)

    def test_each_reading_is_in_exactly_one_month(self):
        october = self.month(2026, 10)[1].decode("utf-8")
        november = self.month(2026, 11)[1].decode("utf-8")
        stamps = {name: [row[1] for row in csv.reader(io.StringIO(text, newline=""))][1:]
                  for name, text in (("Oct", october), ("Nov", november))}
        self.assertEqual(stamps["Oct"], ["2026-10-01T00:00:00", "2026-10-31T01:00:00", "2026-10-31T23:45:00"])
        self.assertEqual(stamps["Nov"], ["2026-11-01T00:00:00", "2026-11-01T01:30:00", "2026-11-01T02:00:00",
                                         "2026-11-02T03:00:00", "2026-11-30T23:45:00"])
        self.assertIn("Turbidity: FNU", october.splitlines()[0])  # each file names a metric by its own last unit
        self.assertIn("Turbidity: NTU", november.splitlines()[0])

    def test_a_month_without_readings_exits_2(self):
        with self.assertRaises(SystemExit) as raised:
            self.month(2026, 9)
        self.assertEqual(raised.exception.code, 2)


class Sampling:
    """An uploaded sampling file, stored as the import stores it, and read back through the sampling Download CSV,
    /api/samples and /api/recent."""

    @classmethod
    def load(cls):
        cls.store_sampling(sampling_rows())

    @classmethod
    def store_sampling(cls, rows):
        from db.models import SamplingMeasurement
        cls.db.session.add_all(SamplingMeasurement(**r) for r in rows)
        cls.db.session.commit()

    def test_the_upload_is_read_as_documented(self):
        result = validate_csv(GOLDEN / "sampling_upload.csv")
        self.assertEqual((len(result.records), result.blank, result.rejected, result.below_detection), (11, 1, 1, 1))
        stored = [{**r, "recorded_at": r["recorded_at"].isoformat()} for r in result.records]
        check_golden(self, "sampling_upload_rows.json", json_bytes(stored))

    def test_template_round_trip(self):
        response = self.app.test_client().get("/api/samples/template.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Disposition"], "attachment; filename=well_sampling_template.csv")
        template = response.data
        response.close()
        self.assertEqual(template, (APP / "sampling_template.csv").read_bytes())
        result = validate_csv(template)
        self.assertTrue(result.ok, [str(e) for e in result.errors])
        self.assertEqual(
            [(r["recorded_at"].isoformat(), r["site_id"], r["creek_id"], r["measurement_type"], r["value"], r["unit"])
             for r in result.records],
            [("2026-05-06T09:40:00", "1", "20962187", "E. coli", 48.0, "CFU/100 mL"),
             ("2026-05-06T09:40:00", "1", "20962187", "Ammonia nitrogen", 0.01, "mg/L"),
             ("2026-05-06T10:15:00", "2", "19431905", "pH", 8.06, "pH units")])

    def test_export(self):
        data = self.export(SAMPLING_ALL)
        text = data.decode("utf-8")
        check_golden(self, "sampling_export.csv", ties_sorted(self, text, time_column=1))
        rows = list(csv.reader(io.StringIO(text, newline="")))
        self.assertEqual(rows[0], ["domain", "recorded_at", "group_type", "station_id", "creek_id", "site_id",
                                   "measurement_type", "value", "unit"])
        self.assertEqual(len(rows), 1 + 11)
        # The 2026-11-03 04:30 reading is after the last picked day (Nov 2 in Toronto) though before the end
        # bound read as wall time
        self.assertEqual(max(r[1] for r in rows[1:]), "2026-11-02T15:00:00")

    def test_export_routes(self):
        from api.services.exports import default_export_filename, normalize_export_payload
        self.assertEqual(default_export_filename(normalize_export_payload(SAMPLING_ALL)), SAMPLING_ALL_NAME)
        client = self.app.test_client()
        self.assertEqual(client.post("/api/exports/estimate", json=SAMPLING_ALL).get_json()["estimated_rows"], 11)
        response = client.post("/api/exports/sync", json=SAMPLING_ALL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Disposition"], f"attachment; filename={SAMPLING_ALL_NAME}")
        check_golden(self, "sampling_export.csv", ties_sorted(self, response.data.decode("utf-8"), time_column=1))
        response.close()

    def test_samples_route(self):
        client = self.app.test_client()
        # Naive bounds are Toronto wall time, like recorded_at
        every = client.get("/api/samples?start=2026-10-31T00:00:00&end=2026-11-02T23:59:59").get_json()
        self.assertEqual(len(every), 11)
        chosen = client.get("/api/samples?start=2026-10-31T00:00:00&end=2026-11-02T23:59:59"
                            "&ancaster=true&coldwater=true").get_json()
        times = [r["recorded_at"] for r in chosen]
        self.assertEqual(times, sorted(times))
        check_golden(self, "samples_ancaster_coldwater.json",
                     json_bytes(sorted(chosen, key=lambda r: (r["recorded_at"], r["site_id"], r["measurement_type"]))))
        self.assertEqual(client.get("/api/samples?start=2026-10-31").status_code, 400)

    def test_recent_route(self):
        recent = self.app.test_client().get("/api/recent").get_json()
        check_golden(self, "recent.json", json_bytes(sorted(recent, key=lambda r: (r["measurement_type"],
                                                                                    r["site_id"]))))


class SqliteSensorExportTests(SensorExport, DatabaseCase):
    pass


class SqliteMonthlyFileTests(MonthlyFile, DatabaseCase):
    pass


class SqliteSamplingTests(Sampling, DatabaseCase):
    pass


POSTGRES = os.getenv("TEST_POSTGRES_URL")
needs_postgres = unittest.skipUnless(POSTGRES, "set TEST_POSTGRES_URL to run the golden files against PostgreSQL")


@needs_postgres
class PostgresSensorExportTests(SensorExport, DatabaseCase):
    uri = POSTGRES


@needs_postgres
class PostgresMonthlyFileTests(MonthlyFile, DatabaseCase):
    uri = POSTGRES


@needs_postgres
class PostgresSamplingTests(Sampling, DatabaseCase):
    uri = POSTGRES

    @classmethod
    def store_sampling(cls, rows):
        # As scripts/inject_sampling.py stores an upload (INSERT ... ON CONFLICT, PostgreSQL only)
        sys.path.insert(0, str(APP / "scripts"))
        import inject_sampling
        inject_sampling.store_rows(cls.db.session, rows)
        cls.db.session.commit()


if __name__ == "__main__":
    unittest.main()
