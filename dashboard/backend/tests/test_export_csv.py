"""The sensor export CSV (api/services/exports.py) is streamed in batches instead of loaded whole; these tests check
it is byte-for-byte what the old load-everything version wrote, and that text cells can't run as spreadsheet
formulas. Run from dashboard/backend: python -m unittest discover -s tests -t .

The comparison runs on SQLite and, with TEST_POSTGRES_URL set (as in CI), on PostgreSQL too, where the rows really
arrive through a server-side cursor."""
import csv
import datetime as dt
import os
import pathlib
import shutil
import sys
import tempfile
import unittest.mock
from typing import Dict, List

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database

from config import Config  # noqa: E402
from api.services import exports as export_service  # noqa: E402
from api.services.exports import (  # noqa: E402
    SENSOR_FILTER_CONFIG,
    _get_logger_label,
    _sensor_query,
    csv_cell,
    normalize_export_payload,
    safe_csv_cell,
    write_export_csv,
)
from db.models import SensorMeasurement  # noqa: E402


def legacy_sensor_csv(filters: Dict, output_path: str) -> int:
    """The sensor export as it was before streaming (every reading loaded with .all()), kept as the reference the
    streamed output must match. Copied unchanged apart from the def line, this docstring, an unused loop
    variable renamed to _ and the time column's header, which now names the zone."""
    requested_groups = set(filters.get("group_types", []))

    query = _sensor_query(filters)
    records = query.order_by(SensorMeasurement.recorded_at).all()

    # Build lookup dictionaries by group and timestamp
    weather_data = {}  # (timestamp, metric) -> value
    quality_data = {}  # (timestamp, metric) -> value
    logger_data = {}   # (timestamp, station_id, metric) -> value

    all_timestamps = set()
    all_weather_metrics = set()
    all_quality_metrics = set()
    all_logger_metrics = set()
    all_logger_stations = set()
    units_by_metric = {}

    # First pass: collect all data and organize by group
    for record in records:
        timestamp = record.recorded_at.isoformat() if record.recorded_at else ""
        metric = record.measurement_type or ""
        value = record.value
        unit = record.unit or ""
        group_type = record.group_type or ""
        station_id = str(record.station_id or "") if record.station_id else ""

        all_timestamps.add(timestamp)
        units_by_metric[metric] = unit

        if group_type == "Weather" and "Weather" in requested_groups:
            weather_data[(timestamp, metric)] = value
            all_weather_metrics.add(metric)
        elif group_type == "Quality" and "Quality" in requested_groups:
            quality_data[(timestamp, metric)] = value
            all_quality_metrics.add(metric)
        elif group_type == "Logger" and "Logger" in requested_groups and station_id:
            logger_data[(timestamp, station_id, metric)] = value
            all_logger_metrics.add(metric)
            all_logger_stations.add(station_id)

    # Set up which groups we should include (based on request, not just what has data)
    include_weather = "Weather" in requested_groups
    include_quality = "Quality" in requested_groups
    include_logger = "Logger" in requested_groups

    # Apply measurement type filters
    allowed_metrics = set(filters.get("measurement_types", []))
    if allowed_metrics:
        all_weather_metrics = {m for m in all_weather_metrics if m in allowed_metrics}
        all_quality_metrics = {m for m in all_quality_metrics if m in allowed_metrics}
        all_logger_metrics = {m for m in all_logger_metrics if m in allowed_metrics}

    requested_metric_map: Dict[str, List[str]] = filters.get("group_measurement_types", {}) or {}

    weather_metrics = requested_metric_map.get("Weather") or sorted(all_weather_metrics)
    quality_metrics = requested_metric_map.get("Quality") or sorted(all_quality_metrics)
    logger_metrics = requested_metric_map.get("Logger") or sorted(all_logger_metrics)

    # Determine logger stations to include
    selected_station_ids = filters.get("station_ids") or []
    if selected_station_ids:
        effective_logger_stations = [str(sid) for sid in selected_station_ids]
    else:
        configured_ids = list(SENSOR_FILTER_CONFIG["gauges"]["sites"].keys())
        effective_logger_stations = configured_ids
        extras = sorted(all_logger_stations.difference(set(configured_ids)))
        effective_logger_stations.extend(extras)

    # Build header row - ALWAYS include requested groups in the output order: Weather, Quality, Logger
    headers = ["ID", export_service.TIMESTAMP_HEADER]

    # Weather section: Include if requested (even if no data)
    if include_weather:
        headers.append("Group")
        for metric in weather_metrics:
            unit = units_by_metric.get(metric, "")
            unit = unit.replace(" asl", "").strip() if unit else ""
            headers.append(f"{metric}: {unit}" if unit else metric)

    # Blank column separator between Weather and Quality
    if include_quality and include_weather:
        headers.append("")

    # Quality section: Include if requested (even if no data)
    if include_quality:
        headers.append("Group")
        for metric in quality_metrics:
            unit = units_by_metric.get(metric, "")
            unit = unit.replace(" asl", "").strip() if unit else ""
            headers.append(f"{metric}: {unit}" if unit else metric)

    # Blank column separator between Quality and Logger
    if include_logger and (include_weather or include_quality):
        headers.append("")

    # Logger section: Include if requested (even if no data)
    if include_logger:
        headers.append("Group")
        if effective_logger_stations:
            for _ in effective_logger_stations:
                headers.append("Sensor")
                for metric in logger_metrics:
                    unit = units_by_metric.get(metric, "")
                    unit = unit.replace(" asl", "").strip() if unit else ""
                    headers.append(f"{metric}: {unit}" if unit else metric)

    with open(output_path, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(headers)

        # Write data rows
        sorted_timestamps = sorted(all_timestamps)
        for row_num, timestamp in enumerate(sorted_timestamps, 1):
            csv_row = [row_num, timestamp]

            # Weather section data
            if include_weather:
                csv_row.append("Weather")
                for metric in weather_metrics:
                    csv_row.append(weather_data.get((timestamp, metric), ""))

            # Blank separator
            if include_quality and include_weather:
                csv_row.append("")

            # Quality section data
            if include_quality:
                csv_row.append("Quality")
                for metric in quality_metrics:
                    csv_row.append(quality_data.get((timestamp, metric), ""))

            # Blank separator
            if include_logger and (include_weather or include_quality):
                csv_row.append("")

            # Logger section data
            if include_logger:
                csv_row.append("Logger")
                for station_id in effective_logger_stations:
                    csv_row.append(_get_logger_label(station_id))
                    for metric in logger_metrics:
                        csv_row.append(logger_data.get((timestamp, station_id, metric), ""))

            if len(csv_row) < len(headers):
                csv_row.extend([""] * (len(headers) - len(csv_row)))
            elif len(csv_row) > len(headers):
                csv_row = csv_row[: len(headers)]

            writer.writerow(csv_row)

    return len(records)


def fixture_readings():
    """Four hours of 15-minute readings from 2026-10-31 23:00, naive Toronto wall time as ingestion stores it, so
    they cross 01:00-02:00 on Nov 1, the hour repeated when clocks fall back. Readings are left out or empty here
    and there, a unit changes partway (the latest one names the column), one logger isn't a configured one, and
    one reading has a fraction of a second."""
    start = dt.datetime(2026, 10, 31, 23, 0)
    readings = []

    def add(station, group, metric, unit, when, value):
        readings.append(dict(station_id=station, group_type=group, measurement_type=metric, unit=unit,
                             recorded_at=when, value=value))

    for i in range(17):
        when = start + dt.timedelta(minutes=15 * i)
        if i % 5 != 3:
            add("22051538", "Weather", "Air Temperature", "°C", when, round(-2.5 + 0.75 * i, 2))
        if i % 4 != 1:
            add("22051538", "Weather", "Rain", "mm", when, None if i == 6 else 0.2 * (i % 3))
        add("22051538", "Weather", "Water Level", "m asl", when, 85.0 + i / 100)
        if i % 2 == 0:
            add("WQ", "Quality", "Turbidity", "FNU" if i < 8 else "NTU", when, 3.0 + i)
            add("WQ", "Quality", "pH", "", when, 7.1)
        for n, station in enumerate(("2577531", "2577533", "2577599")):
            if (i + n) % 3 != 0:
                add(station, "Logger", "Water Level", "m", when, 0.4 + n + i / 50)
            if i % 6 != n:
                add(station, "Logger", "Water Temperature", "°C", when, 4.0 - n)
    add("22051538", "Weather", None, "", start + dt.timedelta(minutes=30), 1.0)  # a reading with no name
    add("2577533", "Logger", "Water Level", "m", dt.datetime(2026, 11, 1, 1, 37, 12, 500000), 0.9)  # off the grid
    add("2577534", "Logger", "Water Level", "m", dt.datetime(2026, 11, 1, 2, 59), 1.5)  # a lone reading
    return readings


ALL = ["Weather", "Quality", "Logger"]
FILTER_CASES = {
    "every group, everything": dict(group_types=ALL),
    "metrics chosen per group": dict(group_types=ALL, group_measurement_types={
        "Weather": ["Rain", "Air Temperature"], "Logger": ["Water Level"]}),
    "two loggers": dict(group_types=["Logger"], station_ids=["2577533", "2577599"]),
    "one measurement": dict(group_types=["Weather", "Logger"], measurement_types=["Water Level"]),
    "quality and loggers, part of the range": dict(group_types=["Quality", "Logger"],
                                                   start="2026-11-01T00:40:00", end="2026-11-01T01:50:00"),
    "nothing in range": dict(group_types=["Quality"], start="2026-12-01T00:00:00", end="2026-12-02T00:00:00"),
}


def payload(**case):
    base = {"domain": "sensor", "start": "2026-10-31T00:00:00", "end": "2026-11-02T00:00:00"}
    base.update(case)
    return base


class StreamedCsvMatchesTheOldOne:
    """Mixed into a TestCase whose setUpClass sets cls.app (pushed) and cls.db, with the tables created."""

    @classmethod
    def load_fixture(cls):
        cls.db.session.query(SensorMeasurement).delete()
        cls.db.session.add_all(SensorMeasurement(**r) for r in fixture_readings())
        cls.db.session.commit()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="export-csv-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def both(self, case):
        filters = normalize_export_payload(payload(**case))
        old_path, new_path = os.path.join(self.tmp, "old.csv"), os.path.join(self.tmp, "new.csv")
        old_count = legacy_sensor_csv(filters, old_path)
        new_count = write_export_csv(filters, new_path)
        return (pathlib.Path(old_path).read_bytes(), old_count), (pathlib.Path(new_path).read_bytes(), new_count)

    def test_same_bytes_as_before(self):
        for name, case in FILTER_CASES.items():
            with self.subTest(name):
                old, new = self.both(case)
                self.assertEqual(new, old)

    def test_same_bytes_when_read_a_few_rows_at_a_time(self):
        with unittest.mock.patch.object(export_service, "STREAM_BATCH_ROWS", 7):
            for name, case in FILTER_CASES.items():
                with self.subTest(name):
                    old, new = self.both(case)
                    self.assertEqual(new, old)

    def test_the_fixture_covers_what_it_should(self):
        (text, count), _ = self.both(FILTER_CASES["every group, everything"])
        rows = list(csv.reader(text.decode("utf-8").splitlines()))
        self.assertEqual(count, len(fixture_readings()))
        self.assertIn("Turbidity: NTU", rows[0])  # the latest unit names the column
        self.assertIn("Water Level: m", rows[0])  # " asl" dropped
        stamps = [r[1] for r in rows[1:]]
        self.assertIn("2026-11-01T01:30:00", stamps)
        self.assertIn("2026-11-01T01:37:12.500000", stamps)
        self.assertIn("Logger 2577599", rows[1])
        self.assertTrue(any("" in r[3:] for r in rows[1:]))  # missing values are blank
        self.assertIn("-2.5", rows[1])  # a negative number, unchanged

    def test_progress_is_reported_while_writing(self):
        calls = []
        with unittest.mock.patch.object(export_service, "STREAM_BATCH_ROWS", 50):
            written = write_export_csv(payload(group_types=ALL), os.path.join(self.tmp, "p.csv"),
                                       progress_callback=lambda done, total: calls.append(done), estimated_rows=999)
        self.assertEqual(calls[:-1], list(range(50, written + 1, 50)))
        self.assertEqual(calls[-1], written)


class SqliteStreamedCsvTests(StreamedCsvMatchesTheOldOne, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="export-csv-db-")
        uri = f"sqlite:///{os.path.join(cls.dir, 't.db')}"
        with unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", uri):
            from server import create_app
            cls.app = create_app()
        from db.database import db
        cls.db = db
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()
        cls.load_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.drop_all()
        cls.db.engine.dispose()
        cls.ctx.pop()
        shutil.rmtree(cls.dir, ignore_errors=True)


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the export CSV against PostgreSQL")
class PostgresStreamedCsvTests(StreamedCsvMatchesTheOldOne, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", os.environ["TEST_POSTGRES_URL"]):
            from server import create_app
            cls.app = create_app()
        from db.database import db
        cls.db = db
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()
        cls.load_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.drop_all()
        cls.db.engine.dispose()
        cls.ctx.pop()

    def test_rows_come_through_a_server_side_cursor(self):
        from sqlalchemy import select
        with export_service._streaming_connection() as conn:
            result = conn.execute(select(SensorMeasurement.id))
            self.assertTrue(result.cursor.name)  # psycopg2 names its server-side cursors
            result.close()


class FormulaInjectionTests(unittest.TestCase):
    def test_text_that_a_spreadsheet_would_run_gets_an_apostrophe(self):
        for text in ("=1+1", "+1", "-cmd", "@SUM(A1)", "\tx", "\rx", "=HYPERLINK(\"http://x\")"):
            self.assertEqual(safe_csv_cell(text), "'" + text)

    def test_numbers_and_ordinary_text_are_unchanged(self):
        for value in (-3.2, -1, 0, 5.5, None, "", "Logger 1", "2026-11-01T01:30:00", "pH", "Water Level: m"):
            self.assertEqual(safe_csv_cell(value), value)

    def test_a_missing_value_is_an_empty_field(self):
        # NaN, infinities and the vendors' "no reading" sentinel are stored in some older rows; none is a reading
        for value in (None, float("nan"), float("inf"), float("-inf"), -100000.0, -99999.0):
            self.assertEqual(csv_cell(value), "")
        for value in (0.0, -2.5, -99998.5, "=1+1"):
            self.assertEqual(csv_cell(value), safe_csv_cell(value))


class SamplingExportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="export-sampling-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        uri = f"sqlite:///{os.path.join(self.dir, 't.db')}"
        patch = unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", uri)
        patch.start()
        self.addCleanup(patch.stop)
        from server import create_app
        from db.database import db
        self.db = db
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.db.engine.dispose()
        self.ctx.pop()

    def test_text_cells_are_neutralized_and_numbers_kept(self):
        from db.models import SamplingMeasurement
        when = dt.datetime(2026, 11, 1, 10, 0)
        self.db.session.add_all([
            SamplingMeasurement(site_id="=HYPERLINK(\"http://x\")", creek_id="+C1", measurement_type="@pH",
                                unit="-", value=-3.5, recorded_at=when),
            SamplingMeasurement(site_id="S2", creek_id="C2", measurement_type="Nitrate", unit="mg/L", value=1.25,
                                recorded_at=when + dt.timedelta(hours=1)),
        ])
        self.db.session.commit()
        path = os.path.join(self.dir, "out.csv")
        written = write_export_csv({"domain": "sampling", "start": "2026-11-01T00:00:00",
                                    "end": "2026-11-02T00:00:00"}, path)
        rows = list(csv.reader(pathlib.Path(path).read_text(encoding="utf-8").splitlines()))
        self.assertEqual(written, 2)
        self.assertEqual(rows[1], ["sampling", "2026-11-01T10:00:00", "", "", "'+C1", "'=HYPERLINK(\"http://x\")",
                                   "'@pH", "-3.5", "'-"])
        self.assertEqual(rows[2], ["sampling", "2026-11-01T11:00:00", "", "", "C2", "S2", "Nitrate", "1.25", "mg/L"])


if __name__ == "__main__":
    unittest.main()
