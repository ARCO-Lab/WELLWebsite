"""Tests for the /api/latest route, run against an in-memory SQLite database. Run from dashboard/backend:
python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from config import Config  # noqa: E402
from server import create_app  # noqa: E402
from db.database import db  # noqa: E402
from db.models import SensorMeasurement  # noqa: E402

# Config reads DATABASE_URL once, when first imported, so a test module imported earlier may have set it already
# (with a placeholder, or a real URL from the environment). Point the app at SQLite either way.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"

NOW = dt.datetime(2026, 11, 10, 12, 0)
LONG_AGO = dt.datetime(2025, 10, 6, 16, 30)  # a logger that stopped reporting about a year ago


def reading(station, group, mtype, value, at, unit="°C"):
    return SensorMeasurement(station_id=station, group_type=group, measurement_type=mtype,
                             value=value, unit=unit, recorded_at=at)


class LatestRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()
        rows = []
        # Weather: two metrics, three readings each; the newest should win
        for i in range(3):
            rows.append(reading("22051538", "Weather", "Air Temperature", 10 + i, NOW - dt.timedelta(minutes=10 * (2 - i))))
            rows.append(reading("22051538", "Weather", "Wind Speed", 1 + i, NOW - dt.timedelta(minutes=10 * (2 - i)), "m/s"))
        # Same measurement_type at another station is its own series
        rows.append(reading("2577531", "Logger", "Water Temperature", 4.0, NOW - dt.timedelta(minutes=5)))
        rows.append(reading("2577531", "Logger", "Water Temperature", 4.5, NOW))
        # A series whose last reading is a year old must still be returned
        rows.append(reading("2577535", "Logger", "Water Temperature", 7.0, LONG_AGO - dt.timedelta(days=30)))
        rows.append(reading("2577535", "Logger", "Water Temperature", 7.5, LONG_AGO))
        # Rows with no measurement_type were never returned and still aren't
        rows.append(reading("2577535", "Logger", None, 99.0, NOW))
        db.session.add_all(rows)
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.drop_all()
        cls.ctx.pop()

    def test_returns_the_newest_reading_of_every_series(self):
        r = self.client.get("/api/latest")
        self.assertEqual(r.status_code, 200)
        got = {(m["station_id"], m["measurement_type"]): m for m in r.get_json()}
        self.assertEqual(set(got), {
            ("22051538", "Air Temperature"), ("22051538", "Wind Speed"),
            ("2577531", "Water Temperature"), ("2577535", "Water Temperature"),
        })
        self.assertEqual(got[("22051538", "Air Temperature")]["value"], 12)
        self.assertEqual(got[("22051538", "Wind Speed")]["unit"], "m/s")
        self.assertEqual(got[("2577531", "Water Temperature")]["value"], 4.5)
        self.assertEqual(got[("2577535", "Water Temperature")]["recorded_at"], LONG_AGO.isoformat())

    def test_response_shape_is_unchanged(self):
        rows = self.client.get("/api/latest").get_json()
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(set(row), {"station_id", "group_type", "measurement_type", "value", "unit", "recorded_at"})
        self.assertEqual(rows[0], {"station_id": "22051538", "group_type": "Weather", "measurement_type": "Air Temperature",
                                   "value": 12, "unit": "°C", "recorded_at": NOW.isoformat()})


class EmptyTableTests(unittest.TestCase):
    def test_empty_table_returns_an_empty_list(self):
        app = create_app()
        with app.app_context():
            db.create_all()
            try:
                self.assertEqual(app.test_client().get("/api/latest").get_json(), [])
            finally:
                db.drop_all()


class DisabledAnalysisRouteTests(unittest.TestCase):
    def test_recent_analysis_route_still_imports(self):
        # It is switched off, but reuses query_latest_per_series; a rename should fail here, not when it's re-enabled
        import api.routes.analysis.recent  # noqa: F401


if __name__ == "__main__":
    unittest.main()
