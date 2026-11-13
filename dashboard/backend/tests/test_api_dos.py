"""Requests built to make the API do far more work, or fail far louder, than a visitor's: export bodies that would
make every CSV row megabytes wide, text the database driver refuses, dates at datetime's limits, made-up chart
filters that would each mint a new cache entry, and stored values that aren't readings (NaN, the vendors'
"no reading" sentinel) on the routes that send raw values.

Most run on throwaway SQLite files. The ones whose failure only happens on PostgreSQL (the driver's NUL refusal, NaN,
which SQLite stores as NULL, and /api/series, whose SQL is PostgreSQL's) run when TEST_POSTGRES_URL points at a
disposable database, as in CI. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import csv
import datetime as dt
import io
import json
import os
import time
import types
import unittest.mock

from tests.test_export_abuse import MINE, ExportTestCase
from tests.test_export_limits import SAMPLING

from config import Config

T0 = dt.datetime(2026, 11, 1, 0, 0)  # naive Toronto wall time, as ingestion stores it
LOGGER = "2577531"
SENSOR = {"domain": "sensor", "start": "2026-11-01T00:00:00", "end": "2026-11-01T23:59:59",
          "group_types": ["Logger"], "station_ids": [LOGGER], "group_measurement_types": {"Logger": ["Water Level"]}}


def strict_json(text):
    """JSON as a browser's JSON.parse reads it: a bare NaN or Infinity is an error, not a number."""
    def refuse(token):
        raise ValueError(f"not JSON: {token}")
    return json.loads(text, parse_constant=refuse)


class SensorData:
    """A day of 10-minute logger readings (144 timestamps, two metrics) plus a weather station, in the test's
    database."""

    def add_readings(self, extra=()):
        from db.models import SensorMeasurement
        from api.services import catalog
        rows = []
        for i in range(144):
            at = T0 + dt.timedelta(minutes=10 * i)
            rows.append(SensorMeasurement(station_id=LOGGER, group_type="Logger", measurement_type="Water Level",
                                          unit="m", value=1.0 + i / 1000, recorded_at=at))
            rows.append(SensorMeasurement(station_id=LOGGER, group_type="Logger", measurement_type="Water Temperature",
                                          unit="°C", value=4.0, recorded_at=at))
        rows.append(SensorMeasurement(station_id="22051538", group_type="Weather", measurement_type="Rain", unit="mm",
                                      value=0.2, recorded_at=T0))
        for station, group, metric, value, at in extra:
            rows.append(SensorMeasurement(station_id=station, group_type=group, measurement_type=metric, unit="",
                                          value=value, recorded_at=at))
        self.db.session.add_all(rows)
        self.db.session.commit()
        catalog.forget()


class ExportListTests(ExportTestCase):
    ROUTES = ("/api/exports/estimate", "/api/exports/sync", "/api/exports/jobs")

    def test_duplicates_are_dropped_and_lists_are_capped(self):
        from api.services.exports import MAX_LIST_VALUES, normalize_export_payload
        filters = normalize_export_payload({**SENSOR, "station_ids": [LOGGER, LOGGER, "2577532", LOGGER, " "]})
        self.assertEqual(filters["station_ids"], [LOGGER, "2577532"])
        too_many = [str(i) for i in range(MAX_LIST_VALUES + 1)]
        bodies = [
            {**SENSOR, "station_ids": too_many},
            {**SENSOR, "group_measurement_types": {"Logger": too_many}},
            {**SENSOR, "measurement_types": too_many},
            {**SAMPLING, "site_ids": too_many},
            {**SENSOR, "station_ids": ["x" * 65]},
            {**SENSOR, "station_ids": [{"nested": "object"}]},
            {**SENSOR, "group_types": ["Logger", "Sensors"]},  # only Weather, Quality and Logger exist
        ]
        for path in self.ROUTES:
            for body in bodies:
                r = self.post(path, body)
                self.assertEqual(r.status_code, 400, (path, str(body)[:80]))
        self.delay.assert_not_called()

    def test_control_characters_and_lone_surrogates_are_refused(self):
        # JSON may hold both; PostgreSQL's driver refuses a NUL (a 500 before), and a lone surrogate can't be
        # encoded as UTF-8 at all
        for raw in ('"2577531\\u0000"', '"\\ud800"', '"Water\\nLevel"'):
            body = ('{"domain": "sensor", "start": "2026-11-01T00:00:00", "end": "2026-11-02T00:00:00", '
                    f'"group_types": ["Logger"], "station_ids": [{raw}]}}')
            for path in self.ROUTES:
                r = self.client.post(path, data=body, content_type="application/json",
                                     headers={"X-Forwarded-For": MINE})
                self.assertEqual(r.status_code, 400, (path, raw))
                self.assertEqual(r.get_json()["error"], "station_ids has a name that isn't valid")

    def test_a_body_over_the_limit_is_refused_before_it_is_read(self):
        self.assertEqual(Config.MAX_CONTENT_LENGTH, 64 * 1024)
        body = {**SENSOR, "station_ids": ["1"] * 20_000}  # about 100 KB
        for path in self.ROUTES:
            self.assertEqual(self.post(path, body).status_code, 413, path)

    def test_only_validation_messages_reach_the_page(self):
        from api.routes.exports import _invalid
        from api.services.exports import ExportValidationError
        with self.app.test_request_context():
            self.assertEqual(_invalid(ExportValidationError("start must be before end"))[0].get_json(),
                             {"error": "start must be before end"})
            leak = ValueError("A string literal cannot contain NUL (0x00) characters.")
            self.assertEqual(_invalid(leak)[0].get_json(), {"error": "This export request isn't valid."})

    def test_instants_in_the_repeated_fall_back_hour_are_a_valid_range(self):
        # 05:50Z is 01:50 EDT and 06:10Z is 01:10 EST: a 20-minute range whose wall-clock times run backwards
        body = {**SAMPLING, "start": "2026-11-01T05:50:00Z", "end": "2026-11-01T06:10:00Z"}
        self.assertEqual(self.post("/api/exports/estimate", body).status_code, 200)
        self.assertEqual(self.post("/api/exports/estimate", {**body, "start": body["end"], "end": body["start"]})
                         .status_code, 400)

    def test_dates_outside_the_supported_years_are_refused(self):
        for start, end in (("1969-12-31T00:00:00", "1970-01-02T00:00:00"), ("2100-12-31", "2101-01-01")):
            self.assertEqual(self.post("/api/exports/estimate", {**SAMPLING, "start": start, "end": end})
                             .status_code, 400)


class ExportSizeTests(SensorData, ExportTestCase):
    """The disk check's estimate must bound the file, however wide the request asks it to be, and the writer must
    stop a file that outgrows its budget anyway."""

    def setUp(self):
        super().setUp()
        self.add_readings()

    def sync(self, body):
        r = self.post("/api/exports/sync", body)
        data = r.get_data()
        r.close()
        return r, data

    def test_made_up_stations_and_metrics_get_no_columns(self):
        junk = [f"junk-{i}" for i in range(49)]
        body = {**SENSOR, "station_ids": [LOGGER] + junk,
                "group_measurement_types": {"Logger": ["Water Level"] + junk}}
        r, data = self.sync(body)
        self.assertEqual(r.status_code, 200, data[:200])
        header = next(csv.reader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(header[2:], ["Group", "Sensor", "Water Level: m"])
        self.assertEqual(data, self.sync(SENSOR)[1], "the same file as asking for the real station only")

    def test_the_estimate_bounds_the_file(self):
        from api.services.exports import estimate_rows, export_size_bytes, normalize_export_payload
        bodies = [
            SENSOR,
            {**SENSOR, "station_ids": [], "group_measurement_types": {}},  # every logger and metric
            {**SENSOR, "group_types": ["Weather", "Quality", "Logger"], "station_ids": [],
             "group_measurement_types": {}},
            {**SENSOR, "station_ids": [LOGGER] + [f"junk-{i}" for i in range(49)]},
        ]
        for body in bodies:
            filters = normalize_export_payload(body)
            estimate = export_size_bytes(filters, estimate_rows(filters))
            r, data = self.sync(body)
            self.assertEqual(r.status_code, 200)
            self.assertLessEqual(len(data), estimate, body)
            self.assertLess(estimate, 20 * len(data), "an estimate far too large would refuse exports for nothing")

    def test_the_disk_check_counts_columns_not_only_readings(self):
        from api.services.exports import EXPORT_BYTES_PER_ROW, export_size_bytes, normalize_export_payload
        filters = normalize_export_payload({**SENSOR, "station_ids": [], "group_measurement_types": {}})
        # 144 rows of 5 configured loggers x 2 metrics: far more than 288 readings x 80 bytes
        self.assertGreater(export_size_bytes(filters, 288), 288 * EXPORT_BYTES_PER_ROW)
        free = types.SimpleNamespace(free=Config.EXPORT_MIN_FREE_MB * 2**20 + 288 * EXPORT_BYTES_PER_ROW + 1)
        with unittest.mock.patch("api.services.exports.shutil.disk_usage", return_value=free), \
                self.assertLogs("api.routes.exports", "WARNING"):
            r = self.post("/api/exports/sync", {**SENSOR, "station_ids": [], "group_measurement_types": {}})
        self.assertEqual(r.status_code, 507)

    def leftovers(self):
        return [name for name in os.listdir(self.exports) if name.startswith("sync_export_")]

    def test_a_file_past_its_byte_budget_is_stopped_and_deleted(self):
        from api.services.exports import WriteBudget
        with unittest.mock.patch("api.routes.exports.write_budget", return_value=WriteBudget(max_bytes=2000)), \
                self.assertLogs("api.routes.exports", "WARNING"):
            r = self.post("/api/exports/sync", SENSOR)
        self.assertEqual(r.status_code, 413)
        self.assertIn("too large", r.get_json()["error"])
        self.assertEqual(self.leftovers(), [])

    def test_a_file_past_its_deadline_is_stopped_and_deleted(self):
        from api.services import exports as export_service
        late = export_service.WriteBudget(deadline=time.monotonic() - 1)
        with unittest.mock.patch("api.routes.exports.write_budget", return_value=late), \
                unittest.mock.patch.object(export_service, "DEADLINE_CHECK_ROWS", 1), \
                self.assertLogs("api.routes.exports", "WARNING"):
            r = self.post("/api/exports/sync", SENSOR)
        self.assertEqual(r.status_code, 504)
        self.assertEqual(self.leftovers(), [])

    def test_the_writer_never_goes_below_the_free_space_floor(self):
        from api.services.exports import write_budget
        free = types.SimpleNamespace(free=Config.EXPORT_MIN_FREE_MB * 2**20 + 5000)
        with unittest.mock.patch("api.services.exports.shutil.disk_usage", return_value=free):
            self.assertEqual(write_budget().max_bytes, 5000)
        with unittest.mock.patch.object(Config, "EXPORT_MAX_FILE_MB", 1):
            self.assertLessEqual(write_budget().max_bytes, 2**20)

    def test_a_failed_direct_export_leaves_no_file(self):
        def fail(filters, path, **kwargs):
            with open(path, "w") as f:
                f.write("half a file")
            raise OSError(28, "No space left on device")
        with unittest.mock.patch("api.routes.exports.write_export_csv", side_effect=fail):
            r = self.post("/api/exports/sync", SENSOR)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self.leftovers(), [])

    def test_sentinels_and_infinities_are_empty_cells(self):
        from db.models import SensorMeasurement
        at = T0 + dt.timedelta(minutes=10)
        row = SensorMeasurement.query.filter_by(station_id=LOGGER, measurement_type="Water Level",
                                                recorded_at=at).one()
        row.value = -100000.0
        self.db.session.commit()
        _, data = self.sync(SENSOR)
        rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(rows[2][-1], "")  # the second timestamp's Water Level
        self.assertNotIn("-100000", data.decode("utf-8"))


class JobQuotaOrderTests(ExportTestCase):
    def test_a_visitor_over_the_hourly_quota_costs_no_row_count(self):
        with unittest.mock.patch.object(Config, "EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER", 1):
            self.assertEqual(self.post("/api/exports/jobs", SAMPLING).status_code, 202)
            self.db.session.query(self.ExportJob).update({"status": "ready"})  # finished: only the quota is left
            self.db.session.commit()
            with unittest.mock.patch("api.routes.exports.estimate_rows") as count:
                r = self.post("/api/exports/jobs", {**SAMPLING, "end": "2026-11-03T00:00:00"})
            self.assertEqual(r.status_code, 429)
            count.assert_not_called()

    def test_a_second_job_needs_half_the_places_free(self):
        others = ["a", "b", "c"]
        for i, fingerprint in enumerate(others):
            self.add_job(f"other-{i}", "queued", fingerprint=fingerprint)
        self.assertEqual(self.post("/api/exports/jobs", SAMPLING).status_code, 202)  # a first job: 4 of 6 places
        r = self.post("/api/exports/jobs", {**SAMPLING, "end": "2026-11-03T00:00:00"})
        self.assertEqual(r.status_code, 429, "a second job while fewer than half the places are free")
        self.assertIn("busy", r.get_json()["error"])
        # Someone without a job still gets one of the places left
        self.assertEqual(self.post("/api/exports/jobs", SAMPLING, "198.51.100.99").status_code, 202)
        # With half the places free, a second job is fine
        self.db.session.query(self.ExportJob).filter(self.ExportJob.id.like("other-%")).update({"status": "ready"})
        self.db.session.commit()
        self.assertEqual(self.post("/api/exports/jobs", {**SAMPLING, "end": "2026-11-03T00:00:00"}).status_code, 202)


class JobIdTests(ExportTestCase):
    def test_a_job_id_that_isnt_a_uuid_is_a_404_before_the_database(self):
        for job_id in ("%00", "not-a-uuid", "..", "00000000-0000-4000-8000-00000000000g"):
            for suffix in ("", "/download"):
                self.assertEqual(self.client.get(f"/api/exports/jobs/{job_id}{suffix}").status_code, 404, job_id)


class RawValueTests(SensorData, ExportTestCase):
    """/api/data and /api/latest send stored values; one that isn't a reading is null."""

    def test_a_sentinel_is_null_on_the_raw_routes(self):
        self.add_readings(extra=[("4501", "Quality", "ODO", -100000.0, T0 + dt.timedelta(days=1))])
        r = self.client.get("/api/data?start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Quality")
        self.assertEqual([row["value"] for row in strict_json(r.get_data(as_text=True))], [None])
        latest = strict_json(self.client.get("/api/latest").get_data(as_text=True))
        self.assertEqual([s["value"] for s in latest if s["station_id"] == "4501"], [None])
        self.assertIn(1.143, [s["value"] for s in latest], "real readings are unchanged")


class DateLimitTests(ExportTestCase):
    def test_dates_near_datetimes_limits_are_400s_not_500s(self):
        for path in ("/api/series?bucket=600&start=9999-12-31T00:00:00&end=9999-12-31T23:59:59&group_type=Weather",
                     "/api/series?start=9999-12-30T00:00:00&end=9999-12-31T23:59:59&group_type=Weather",
                     "/api/series?start=0001-01-01T00:00:00&end=0001-01-02T00:00:00&group_type=Weather",
                     "/api/windrose?start=9999-12-30T00:00:00&end=9999-12-31T23:59:59",
                     "/api/data?start=9999-12-30T00:00:00&end=9999-12-31T23:59:59&group_type=Weather",
                     "/api/samples?start=1900-01-01&end=2100-01-01"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 400, path)
            self.assertIn("error", r.get_json())

    def test_a_tile_whose_end_overflows_is_a_400(self):
        from api.routes.series import check_tiles
        with self.assertRaises(OverflowError):  # why the route catches it, should the year check ever widen
            check_tiles(dt.datetime(9999, 12, 31), dt.datetime(9999, 12, 31, 23, 59, 59), 600)

    def test_a_bucket_that_isnt_ascii_digits_is_refused_with_the_routes_message(self):
        r = self.client.get("/api/series?bucket=%C2%B2&start=2026-11-01T00:00:00&end=2026-11-02T00:00:00"
                            "&group_type=Weather")
        self.assertEqual(r.status_code, 400)
        self.assertIn("bucket must be one of", r.get_json()["error"])

    def test_control_characters_in_series_filters_are_refused(self):
        for q in ("station_id=%00", "measurement_type=Rain%00", "series=Weather|22051538|Rain%0A"):
            r = self.client.get(f"/api/series?start=2026-11-01T00:00:00&end=2026-11-02T00:00:00"
                                f"&group_type=Weather&{q}")
            self.assertEqual(r.status_code, 400, q)
        r = self.client.get("/api/data?start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Weather%00")
        self.assertEqual(r.status_code, 400)


class SentryThrottleTests(unittest.TestCase):
    def setUp(self):
        from utils import sentry
        self.sentry = sentry
        saved = dict(sentry._last_sent)
        sentry._last_sent.clear()
        self.addCleanup(lambda: (sentry._last_sent.clear(), sentry._last_sent.update(saved)))

    def event(self, path="/api/series", mechanism="flask"):
        return {"request": {"method": "GET", "url": f"http://backend{path}?start=x"},
                "exception": {"values": [{"type": "ValueError", "mechanism": {"type": mechanism}}]}}

    def test_a_repeated_unhandled_request_error_is_sent_once_an_hour(self):
        exc = ValueError("boom 1")
        hint = {"exc_info": (ValueError, exc, None)}
        self.assertIsNotNone(self.sentry.before_send(self.event(), hint))
        self.assertIsNone(self.sentry.before_send(self.event(), {"exc_info": (ValueError, ValueError("boom 2"), None)}),
                          "the same failure with only a number changed")
        self.assertIsNotNone(self.sentry.before_send(self.event("/api/windrose"), hint), "another route")
        self.assertIsNotNone(self.sentry.before_send(self.event(mechanism="generic"), hint),
                             "captured on purpose (capture_job_error throttles those itself)")


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"),
                     "set TEST_POSTGRES_URL to run the API abuse tests against PostgreSQL")
class PostgresTests(SensorData, unittest.TestCase):
    """What only PostgreSQL shows: its driver refuses a NUL character (a plain ValueError, which was a 500 and a
    Sentry event), it stores NaN (SQLite stores NULL), and /api/series's SQL is PostgreSQL's."""

    def setUp(self):
        patch = unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", os.environ["TEST_POSTGRES_URL"])
        patch.start()
        self.addCleanup(patch.stop)
        from server import create_app
        from db.database import db
        from db.models import ExportJob
        from tasks import exports as export_tasks
        self.db, self.ExportJob = db, ExportJob
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        delay = unittest.mock.patch.object(export_tasks.generate_export_job, "delay")
        self.delay = delay.start()
        self.addCleanup(delay.stop)
        self.client = self.app.test_client()
        self.add_readings(extra=[
            ("4501", "Quality", "ODO", 8.0, T0),
            ("4501", "Quality", "ODO", float("nan"), T0 + dt.timedelta(minutes=10)),
            ("4501", "Quality", "ODO", -100000.0, T0 + dt.timedelta(minutes=20)),
            ("4501", "Quality", "ODO", float("inf"), T0 + dt.timedelta(minutes=30)),
            ("4502", "Quality", "pH", float("nan"), T0),  # a series whose newest reading is NaN
        ])

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.db.engine.dispose()
        self.ctx.pop()

    def post(self, path, body):
        return self.client.post(path, json=body, headers={"X-Forwarded-For": MINE})

    def test_malformed_and_driver_refused_bodies_are_400s(self):
        from tests.test_export_abuse import MalformedBodyTests
        MalformedBodyTests.test_bodies_that_arent_valid_exports_are_400s(self)
        for raw in ('"\\u0000"', '"\\ud800"'):
            for field in ("station_ids", "measurement_types"):
                body = ('{"domain": "sensor", "start": "2026-11-01T00:00:00", "end": "2026-11-02T00:00:00", '
                        f'"group_types": ["Logger"], "{field}": [{raw}]}}')
                for path in ("/api/exports/estimate", "/api/exports/sync", "/api/exports/jobs"):
                    r = self.client.post(path, data=body, content_type="application/json")
                    self.assertEqual(r.status_code, 400, (path, field, raw))

    def test_a_nul_that_reaches_the_driver_anyway_is_a_400_and_no_error_report(self):
        from sqlalchemy import text

        @self.app.route("/test-nul")
        def nul():
            return {"n": self.db.session.execute(text("SELECT :v"), {"v": "a\x00b"}).scalar()}

        with unittest.mock.patch("sentry_sdk.capture_exception") as captured, \
                self.assertLogs(self.app.logger, "WARNING"):
            r = self.client.get("/test-nul")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("NUL", r.get_data(as_text=True))
        captured.assert_not_called()
        self.assertEqual(self.client.get("/api/latest").status_code, 200, "the session still works")

    def test_nul_in_series_filters_and_job_ids(self):
        r = self.client.get("/api/series?start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Weather"
                            "&station_id=%00")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get("/api/exports/jobs/%00").status_code, 404)

    def test_nan_and_sentinels_are_null_on_the_raw_routes(self):
        r = self.client.get("/api/data?start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Quality")
        self.assertEqual(r.status_code, 200)
        rows = strict_json(r.get_data(as_text=True))
        values = {(row["station_id"], row["recorded_at"]): row["value"] for row in rows}
        self.assertEqual(values[("4501", "2026-11-01T00:00:00")], 8.0)
        self.assertEqual([values[("4501", f"2026-11-01T00:{m}:00")] for m in ("10", "20", "30")], [None] * 3)
        latest = strict_json(self.client.get("/api/latest").get_data(as_text=True))
        self.assertEqual({s["station_id"]: s["value"] for s in latest if s["group_type"] == "Quality"},
                         {"4501": None, "4502": None})

    def test_nan_and_sentinels_are_empty_cells_in_both_export_files(self):
        sensor = {"domain": "sensor", "start": "2026-11-01T00:00:00", "end": "2026-11-01T00:30:00",
                  "group_types": ["Quality"]}
        r = self.post("/api/exports/sync", sensor)
        text_ = r.get_data(as_text=True)
        r.close()
        rows = list(csv.reader(io.StringIO(text_)))
        odo = rows[0].index("ODO")
        self.assertEqual([row[odo] for row in rows[1:]], ["8.0", "", "", ""])
        self.assertNotIn("nan", text_.lower())
        from api.services.exports import iter_export_rows, normalize_export_payload, csv_cell
        values = [csv_cell(row["value"]) for row in iter_export_rows(normalize_export_payload(sensor))]
        self.assertEqual(sorted(values, key=str), ["", "", "", "", 8.0])

    def series(self, query):
        return self.client.get(f"/api/series?{query}")

    def test_made_up_filter_values_mint_no_cache_keys(self):
        from utils import response_cache
        from api.routes.series import TILE_BUCKETS, tile_start
        stored = {}
        start = tile_start(T0, 600)
        end = start + dt.timedelta(seconds=TILE_BUCKETS * 600)
        tile = f"start={start.isoformat()}&end={end.isoformat()}&bucket=600&group_type=Logger"
        with unittest.mock.patch.object(response_cache, "get", side_effect=lambda key: None), \
                unittest.mock.patch.object(response_cache, "put",
                                           side_effect=lambda key, body, ttl: stored.setdefault(key, body)):
            real = self.series(f"{tile}&station_id={LOGGER}")
            self.assertEqual(real.status_code, 200)
            for i in range(5):
                r = self.series(f"{tile}&station_id={LOGGER}&station_id=junk-{i}&measurement_type=Water%20Level"
                                f"&measurement_type=junk-{i}")
                self.assertEqual(r.status_code, 200)
            self.assertEqual(len(stored), 2, "the real station alone, and with its real measurement")
            # Filters that name nothing at all: an empty answer, no query and nothing stored
            with unittest.mock.patch.object(self.db.session, "execute", wraps=self.db.session.execute) as run:
                r = self.series(f"{tile}&station_id=junk-x")
                self.assertEqual(r.get_json()["series"], [])
                self.assertFalse(any("WITH b AS" in str(call.args[0]) for call in run.call_args_list))
            r = self.series(f"start={start.isoformat()}&end={end.isoformat()}&bucket=600"
                            f"&series=Logger|{LOGGER}|Nope")
            self.assertEqual((r.status_code, r.get_json()["series"]), (200, []))
            self.assertEqual(len(stored), 2)
        body = self.series(f"{tile}&station_id={LOGGER}&station_id=junk").get_json()
        self.assertEqual({s["measurement_type"] for s in body["series"]}, {"Water Level", "Water Temperature"})

    def test_a_new_series_is_known_as_soon_as_its_first_reading_is_stored(self):
        from db.models import SensorMeasurement
        from api.routes.series import TILE_BUCKETS, tile_start
        start = tile_start(T0, 600)
        q = (f"start={start.isoformat()}&end={(start + dt.timedelta(seconds=TILE_BUCKETS * 600)).isoformat()}"
             f"&bucket=600&series=Logger|2577536|Water%20Level")
        self.assertEqual(self.series(q).get_json()["series"], [])
        self.db.session.add(SensorMeasurement(station_id="2577536", group_type="Logger", measurement_type="Water Level",
                                              unit="m", value=2.0, recorded_at=T0))
        self.db.session.commit()
        self.assertEqual([s["station_id"] for s in self.series(q).get_json()["series"]], ["2577536"])


if __name__ == "__main__":
    unittest.main()
