"""Freshness rules (utils/monitoring.py) and GET /health/data, against an in-memory SQLite database.
Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from utils.monitoring import (  # noqa: E402
    assess_freshness, group_limit, parse_excluded_series, parse_hours, parse_quiet_hours,
)
from utils.timezone import EST_TZ  # noqa: E402
from config import Config  # noqa: E402

# Config reads DATABASE_URL once, when first imported; another test module may have imported it first.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"


def at(y, mo, d, h, mi=0):
    """An aware site-time datetime."""
    return dt.datetime(y, mo, d, h, mi, tzinfo=EST_TZ)


def row(group, station, mtype, recorded_at):
    return {"group_type": group, "station_id": station, "measurement_type": mtype,
            "recorded_at": recorded_at.replace(tzinfo=None).isoformat()}


class ParsingTests(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(parse_hours("3", "X"), 3.0)
        self.assertEqual(parse_hours(" 1.5 ", "X"), 1.5)
        for bad in ("", "abc", "0", "-2", "inf", "nan"):
            with self.assertRaises(ValueError, msg=bad) as e:
                parse_hours(bad, "HEALTH_MAX_AGE_HOURS_QUALITY")
            self.assertIn("HEALTH_MAX_AGE_HOURS_QUALITY", str(e.exception))

    def test_quiet_hours(self):
        self.assertEqual(parse_quiet_hours("18-12"), (18, 12))
        self.assertEqual(parse_quiet_hours(" 1 - 5 "), (1, 5))
        for off in ("", "off", "None", None):
            self.assertIsNone(parse_quiet_hours(off))
        for bad in ("18", "18-24", "7-7", "evening", "18:00-12:00"):
            with self.assertRaises(ValueError, msg=bad):
                parse_quiet_hours(bad)

    def test_group_limits_from_env(self):
        self.assertEqual(group_limit("Weather", {}).max_age, dt.timedelta(hours=3))
        self.assertIsNone(group_limit("Weather", {}).quiet_hours)
        self.assertEqual(group_limit("Quality", {}).quiet_hours, (18, 12))
        env = {"HEALTH_MAX_AGE_HOURS": "5", "HEALTH_MAX_AGE_HOURS_LOGGER": "2", "HEALTH_QUIET_HOURS_QUALITY": "off"}
        self.assertEqual(group_limit("Weather", env).max_age, dt.timedelta(hours=5))
        self.assertEqual(group_limit("Logger", env).max_age, dt.timedelta(hours=2))
        self.assertIsNone(group_limit("Quality", env).quiet_hours)
        # A blank group setting falls back to the default instead of failing
        self.assertEqual(group_limit("Logger", {"HEALTH_MAX_AGE_HOURS_LOGGER": " "}).max_age, dt.timedelta(hours=3))
        with self.assertRaises(ValueError):
            group_limit("Logger", {"HEALTH_MAX_AGE_HOURS_LOGGER": "three"})

    def test_excluded_series(self):
        self.assertEqual(parse_excluded_series("2577535:*, 4501:TSS ,,"), {("2577535", "*"), ("4501", "TSS")})
        self.assertEqual(parse_excluded_series(""), set())
        self.assertEqual(parse_excluded_series("22051538:Water Content"), {("22051538", "Water Content")})
        for bad in ("2577535", ":*", "2577535:"):
            with self.assertRaises(ValueError, msg=bad):
                parse_excluded_series(bad)


class FreshnessTests(unittest.TestCase):
    def test_fresh_and_stale_series(self):
        now = at(2026, 11, 10, 14)
        report = assess_freshness([
            row("Weather", "22051538", "Air Temperature", now - dt.timedelta(minutes=50)),
            row("Weather", "22051538", "Wind Speed", now - dt.timedelta(hours=3, minutes=1)),
            row("Logger", "2577531", "Water Temperature", now - dt.timedelta(hours=2, minutes=59)),
        ], now, env={})
        self.assertEqual(report["status"], "stale")
        self.assertEqual([(s["group"], s["measurement_type"], s["age_minutes"]) for s in report["stale"]],
                         [("Weather", "Wind Speed", 181)])
        weather = report["groups"]["Weather"]
        self.assertEqual(weather["age_minutes"], 50)   # the group's newest series
        self.assertEqual([s["status"] for s in weather["series"]], ["ok", "stale"])
        self.assertEqual(report["groups"]["Logger"]["series"][0]["status"], "ok")

    def test_everything_fresh_is_ok(self):
        now = at(2026, 11, 10, 14)
        report = assess_freshness([row("Weather", "22051538", "Rain", now - dt.timedelta(minutes=10))], now, env={})
        self.assertEqual((report["status"], report["stale"]), ("ok", []))

    def test_excluded_series_never_stale(self):
        now = at(2026, 11, 10, 14)
        dead = row("Logger", "2577535", "Water Surface Elevation", at(2025, 10, 6, 16, 30))
        live = row("Logger", "2577531", "Water Surface Elevation", now - dt.timedelta(minutes=20))
        report = assess_freshness([dead, live], now, env={})   # 2577535:* is excluded by default
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["groups"]["Logger"]["series"][0]["status"], "excluded")
        self.assertEqual(assess_freshness([dead, live], now, env={"HEALTH_EXCLUDED_SERIES": ""})["status"], "stale")

    def test_nothing_to_check_is_not_ok(self):
        now = at(2026, 11, 10, 14)
        self.assertEqual(assess_freshness([], now, env={})["status"], "stale")
        only_dead = [row("Logger", "2577535", "Water Temperature", at(2025, 10, 6, 16, 30))]
        self.assertIn("error", assess_freshness(only_dead, now, env={}))

    def test_quality_quiet_hours(self):
        # WQData usually stops in the evening and resumes mid-morning (quiet 18-12 by default).
        stopped_at_8pm = row("Quality", "4501", "ODO", at(2026, 11, 9, 20, 0))
        for now, expected in [
            (at(2026, 11, 9, 23), "ok"),        # quiet, and it was reporting when the quiet hours began
            (at(2026, 11, 10, 11, 50), "ok"),   # still quiet
            (at(2026, 11, 10, 12, 0), "stale"),  # quiet hours over, nothing since last night
        ]:
            self.assertEqual(assess_freshness([stopped_at_8pm], now, env={})["status"], expected, now)
        # During quiet hours a reading from up to 1 h (the margin) before they began is enough; one that stopped
        # earlier in the afternoon is stale, even though it is within the 3 h limit when the quiet hours begin.
        for stopped, expected in [((17, 0), "ok"), ((16, 59), "stale"), ((15, 30), "stale")]:
            r = row("Quality", "4501", "ODO", at(2026, 11, 9, *stopped))
            for now in (at(2026, 11, 9, 18, 0), at(2026, 11, 9, 23), at(2026, 11, 10, 9)):
                self.assertEqual(assess_freshness([r], now, env={})["status"], expected, (stopped, now))
        # The margin is configurable
        r = row("Quality", "4501", "ODO", at(2026, 11, 9, 15, 30))
        env = {"HEALTH_QUIET_MARGIN_HOURS_QUALITY": "3"}
        self.assertEqual(assess_freshness([r], at(2026, 11, 9, 23), env=env)["status"], "ok")
        self.assertEqual(assess_freshness([r], at(2026, 11, 9, 23), env=env)["groups"]["Quality"]["quiet_margin_hours"], 3)
        with self.assertRaises(ValueError):
            assess_freshness([r], at(2026, 11, 9, 23), env={"HEALTH_QUIET_MARGIN_HOURS_QUALITY": "soon"})
        # Quiet hours don't apply to the other groups
        weather = row("Weather", "22051538", "Rain", at(2026, 11, 9, 20, 0))
        self.assertEqual(assess_freshness([weather], at(2026, 11, 9, 23, 30), env={})["status"], "stale")

    def test_quiet_hours_that_dont_wrap_midnight(self):
        env = {"HEALTH_QUIET_HOURS_WEATHER": "1-5"}
        r = row("Weather", "22051538", "Rain", at(2026, 11, 10, 0, 30))
        self.assertEqual(assess_freshness([r], at(2026, 11, 10, 4, 59), env=env)["status"], "ok")
        self.assertEqual(assess_freshness([r], at(2026, 11, 10, 5, 0), env=env)["status"], "stale")

    def test_ages_are_real_time_across_dst(self):
        # Clocks fell back at 02:00 on 2026-11-01: 00:30 to 03:30 wall clock is 4 h of real time.
        r = row("Weather", "22051538", "Rain", at(2026, 11, 1, 0, 30))
        report = assess_freshness([r], at(2026, 11, 1, 3, 30), env={})
        self.assertEqual(report["groups"]["Weather"]["series"][0]["age_minutes"], 240)
        self.assertEqual(report["status"], "stale")

    def test_bad_setting_raises(self):
        now = at(2026, 11, 10, 14)
        with self.assertRaises(ValueError):
            assess_freshness([row("Quality", "4501", "ODO", now)], now, env={"HEALTH_QUIET_HOURS_QUALITY": "late"})


class HealthDataRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server import create_app
        from db.database import db
        from db.models import SensorMeasurement
        cls.db, cls.Model = db, SensorMeasurement
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.drop_all()
        cls.ctx.pop()

    def setUp(self):
        self.db.session.query(self.Model).delete()
        self.db.session.commit()
        self.now = dt.datetime.now(EST_TZ).replace(tzinfo=None, microsecond=0)
        os.environ.pop("HEALTH_EXCLUDED_SERIES", None)
        os.environ["HEALTH_QUIET_HOURS_QUALITY"] = "off"   # results mustn't depend on when the tests run
        self.addCleanup(os.environ.pop, "HEALTH_QUIET_HOURS_QUALITY", None)

    def add(self, station, group, mtype, age):
        for minutes in (age + 10, age):
            self.db.session.add(self.Model(station_id=station, group_type=group, measurement_type=mtype, value=1.0,
                                           unit="", recorded_at=self.now - dt.timedelta(minutes=minutes)))
        self.db.session.commit()

    def test_200_when_every_live_series_is_fresh(self):
        self.add("22051538", "Weather", "Air Temperature", 40)
        self.add("4501", "Quality", "ODO", 20)
        self.add("2577535", "Logger", "Water Temperature", 400 * 24 * 60)   # Logger 5, excluded by default
        r = self.client.get("/health/data")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["groups"]["Weather"]["newest"], (self.now - dt.timedelta(minutes=40)).isoformat())
        self.assertIn(body["groups"]["Weather"]["age_minutes"], (40, 41))
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_503_lists_the_stale_series(self):
        self.add("22051538", "Weather", "Air Temperature", 40)
        self.add("2577531", "Logger", "Water Surface Elevation", 5 * 60)
        r = self.client.get("/health/data")
        self.assertEqual(r.status_code, 503)
        body = r.get_json()
        self.assertEqual([(s["station_id"], s["measurement_type"]) for s in body["stale"]],
                         [("2577531", "Water Surface Elevation")])

    def test_503_on_a_bad_setting(self):
        self.add("22051538", "Weather", "Air Temperature", 40)
        os.environ["HEALTH_MAX_AGE_HOURS"] = "soon"
        self.addCleanup(os.environ.pop, "HEALTH_MAX_AGE_HOURS", None)
        r = self.client.get("/health/data")
        self.assertEqual(r.status_code, 503)
        self.assertIn("HEALTH_MAX_AGE_HOURS", r.get_json()["error"])

    def test_503_when_the_table_is_empty(self):
        self.assertEqual(self.client.get("/health/data").status_code, 503)


if __name__ == "__main__":
    unittest.main()
