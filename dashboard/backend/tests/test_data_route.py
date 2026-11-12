"""Tests for the /api/data route, run against an in-memory SQLite database. Run from dashboard/backend:
python -m unittest discover -s tests -t ."""
import datetime as dt
import importlib
import os
import pathlib
import sys
from unittest import TestCase, main, mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from config import Config  # noqa: E402
from server import create_app  # noqa: E402
from db.database import db  # noqa: E402
from db.models import SensorMeasurement  # noqa: E402
from api.routes import data as data_route  # noqa: E402

# Config reads DATABASE_URL once, when first imported: if another test module imported it first (with its own
# placeholder URL), the line above came too late. Point the app at SQLite either way.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"

T0 = dt.datetime(2026, 11, 1, 0, 0)


class DataRouteTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()
        # 8 weather readings, one per 10 minutes, and 2 logger readings
        for i in range(8):
            db.session.add(SensorMeasurement(station_id="22051538", group_type="Weather", measurement_type="Air Temperature",
                                             value=10 + i, unit="°C", recorded_at=T0 + dt.timedelta(minutes=10 * i)))
        for i in range(2):
            db.session.add(SensorMeasurement(station_id="2577531", group_type="Logger", measurement_type="Water Temperature",
                                             value=5 + i, unit="°C", recorded_at=T0 + dt.timedelta(minutes=10 * i)))
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.drop_all()
        cls.ctx.pop()

    def get(self, start, end, groups, limit):
        # The limit is read once at import; patch the parsed value for this request only
        query = "&".join([f"start={start.isoformat()}", f"end={end.isoformat()}"] + [f"group_type={g}" for g in groups])
        with mock.patch.object(data_route, "MAX_ROWS", limit):
            return self.client.get(f"/api/data?{query}")

    def test_over_the_limit_is_refused_with_413_and_counts(self):
        r = self.get(T0, T0 + dt.timedelta(hours=2), ["Weather"], limit=5)
        self.assertEqual(r.status_code, 413)
        body = r.get_json()
        self.assertEqual(body["rows"], 8)
        self.assertEqual(body["max_rows"], 5)
        self.assertIn("shorter range", body["error"])

    def test_within_the_limit_returns_rows_in_time_order(self):
        r = self.get(T0, T0 + dt.timedelta(minutes=25), ["Weather", "Logger"], limit=5)
        self.assertEqual(r.status_code, 200)
        rows = r.get_json()
        self.assertEqual(len(rows), 5)  # 3 weather + 2 logger
        self.assertEqual(set(rows[0]), {"station_id", "group_type", "measurement_type", "value", "unit", "recorded_at"})
        self.assertEqual([x["recorded_at"] for x in rows], sorted(x["recorded_at"] for x in rows))

    def test_exactly_at_the_limit_is_allowed(self):
        self.assertEqual(self.get(T0, T0 + dt.timedelta(hours=2), ["Weather"], limit=8).status_code, 200)

    def test_groups_filter_the_count(self):
        self.assertEqual(self.get(T0, T0 + dt.timedelta(hours=2), ["Logger"], limit=5).status_code, 200)

    def test_missing_or_bad_parameters(self):
        self.assertEqual(self.client.get("/api/data?start=2026-11-01").status_code, 400)
        self.assertEqual(self.client.get("/api/data?start=x&end=y&group_type=Weather").status_code, 400)


class MaxRowsSettingTests(TestCase):
    """DATA_MAX_ROWS is parsed once at import; a bad value falls back to the default instead of failing requests."""

    def test_unset_or_empty_uses_the_default_quietly(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertEqual(data_route.parse_max_rows(value), data_route.DEFAULT_MAX_ROWS)

    def test_non_numeric_zero_or_negative_falls_back_with_a_warning(self):
        for value in ("300k", "abc", "1.5", "0", "-5"):
            with self.subTest(value=value):
                with self.assertLogs(data_route.log, level="WARNING") as logs:
                    self.assertEqual(data_route.parse_max_rows(value), data_route.DEFAULT_MAX_ROWS)
                self.assertIn("DATA_MAX_ROWS", logs.output[0])

    def test_a_positive_whole_number_is_used(self):
        self.assertEqual(data_route.parse_max_rows("1000"), 1000)
        self.assertEqual(data_route.parse_max_rows(" 50000 "), 50000)

    def test_a_bad_value_at_import_does_not_break_the_module(self):
        try:
            with mock.patch.dict(os.environ, {"DATA_MAX_ROWS": "300k"}), self.assertLogs(data_route.log, "WARNING"):
                importlib.reload(data_route)
            self.assertEqual(data_route.MAX_ROWS, data_route.DEFAULT_MAX_ROWS)
        finally:
            importlib.reload(data_route)  # patch.dict has restored os.environ by now


if __name__ == "__main__":
    main()
