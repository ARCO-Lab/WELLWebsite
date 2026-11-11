"""The email alerts: their rules and text (utils/alerts.py), the alert check against an in-memory SQLite database with a
fake SMTP sender (scripts/check_alerts.py), and how ingestion records each vendor call's outcome from the real HTTP
reply (api/services, scripts/inject_from_api.py). No network, no real email.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import sys
import unittest
from unittest import mock

import requests

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from config import Config  # noqa: E402

Config.SQLALCHEMY_DATABASE_URI = "sqlite://"   # another test module may have imported Config first

from api.services import quality, weather  # noqa: E402
from utils import alerts  # noqa: E402
from utils.alerts import (  # noqa: E402
    STALE_SENSOR, SUSPECT_VALUES, VENDOR_DOWN, Settings, describe_vendor_error, freshness_env, settings_from_env,
    stale_conditions, suspect_conditions, suspect_finding, vendor_conditions,
)
from utils.fetching import BadVendorResponse  # noqa: E402
from utils.monitoring import assess_freshness  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 11, 19, 0, tzinfo=UTC)   # 14:00 in Toronto: outside the water quality quiet hours
WEATHER, WQ = "22051538", "4501"
SMTP = {"SMTP_HOST": "relay.test", "SMTP_PORT": "25", "SMTP_FROM": "well@test.ca", "ALERT_EMAILS": "team@test.ca"}


def site(aware):
    """recorded_at as stored: naive Toronto time."""
    return aware.astimezone(EST_TZ).replace(tzinfo=None)


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.exceptions.HTTPError(f"{status} for url: https://x.test/?apiKey=SECRET", response=response)


def latest_row(group, station, measurement, age):
    return {"station_id": station, "group_type": group, "measurement_type": measurement,
            "recorded_at": site(NOW - age).isoformat()}


def vendor(failures=0, kind=None, status=None, error=None, since=None):
    return {"consecutive_failures": failures, "last_error_kind": kind, "last_http_status": status,
            "last_error": error, "failing_since": since, "last_failure_at": since,
            "last_success_at": NOW - dt.timedelta(hours=2) if failures else NOW - dt.timedelta(minutes=5)}


class SettingsTests(unittest.TestCase):
    def test_defaults_and_env(self):
        s = settings_from_env({})
        self.assertEqual((s.vendor_failures, s.reminder, s.suspect_values), (3, dt.timedelta(hours=24), True))
        s = settings_from_env({"ALERT_VENDOR_FAILURES": "6", "ALERT_REMINDER_HOURS": "12", "ALERT_SUSPECT_VALUES": "off",
                               "ALERT_DASHBOARD_URL": "https://example.test/"})
        self.assertEqual((s.vendor_failures, s.reminder, s.suspect_values, s.dashboard_url),
                         (6, dt.timedelta(hours=12), False, "https://example.test/"))
        for bad in ({"ALERT_VENDOR_FAILURES": "0"}, {"ALERT_REMINDER_HOURS": "soon"}, {"ALERT_SUSPECT_VALUES": "maybe"}):
            with self.assertRaises(ValueError):
                settings_from_env(bad)

    def test_stale_thresholds_from_env(self):
        rows = [latest_row("Quality", WQ, "ODO", dt.timedelta(hours=2.5)),
                latest_row("Weather", WEATHER, "Rain", dt.timedelta(hours=2.5))]
        report = assess_freshness(rows, NOW, freshness_env({}))   # defaults: Quality 2 h, Weather 3 h
        self.assertEqual([s["group"] for s in report["stale"]], ["Quality"])
        report = assess_freshness(rows, NOW, freshness_env({"ALERT_STALE_HOURS_QUALITY": "4",
                                                            "ALERT_STALE_HOURS_WEATHER": "2"}))
        self.assertEqual([s["group"] for s in report["stale"]], ["Weather"])
        report = assess_freshness(rows, NOW, freshness_env({"ALERT_STALE_HOURS": "1"}))   # every group
        self.assertEqual(len(report["stale"]), 2)
        with self.assertRaises(ValueError):
            freshness_env({"ALERT_STALE_HOURS_LOGGER": "-1"})


class VendorErrorTests(unittest.TestCase):
    def test_kinds_and_safe_text(self):
        self.assertEqual(describe_vendor_error(http_error(401))[:2], ("auth", 401))
        self.assertEqual(describe_vendor_error(http_error(403))[:2], ("auth", 403))
        self.assertEqual(describe_vendor_error(http_error(429))[:2], ("quota", 429))
        self.assertEqual(describe_vendor_error(http_error(503)), ("server", 503, "HTTPError (HTTP 503)"))
        self.assertEqual(describe_vendor_error(requests.exceptions.ReadTimeout("https://x/?apiKey=SECRET"))[0], "timeout")
        self.assertEqual(describe_vendor_error(requests.exceptions.ConnectionError("x"))[0], "network")
        self.assertEqual(describe_vendor_error(BadVendorResponse("LI-COR replied without a data list")),
                         ("bad_response", None, "LI-COR replied without a data list"))
        for error in (http_error(503), requests.exceptions.ReadTimeout("https://x/?apiKey=SECRET")):
            self.assertNotIn("SECRET", describe_vendor_error(error)[2])


class VendorDownTests(unittest.TestCase):
    since = NOW - dt.timedelta(hours=1)

    def test_needs_n_failures_in_a_row(self):
        settings = Settings()
        self.assertEqual(vendor_conditions({"LI-COR": vendor(2, "server", 503, "HTTPError (HTTP 503)", self.since)},
                                           NOW, settings), {})
        found = vendor_conditions({"LI-COR": vendor(6, "server", 503, "HTTPError (HTTP 503)", self.since)}, NOW, settings)
        c = found["vendor:LI-COR"]
        self.assertEqual(c.kind, VENDOR_DOWN)
        self.assertIn("LI-COR API not responding since 2026-11-11 13:00 (HTTP 503 ×6)", c.title)
        self.assertIn("our sensors may be fine", c.detail)

    def test_auth_and_quota_have_their_own_advice(self):
        found = vendor_conditions({"WQData": vendor(3, "auth", 401, "HTTPError (HTTP 401)", self.since),
                                   "LI-COR": vendor(3, "timeout", None, "ReadTimeout", self.since)}, NOW, Settings())
        self.assertIn("rejects our credentials (HTTP 401 ×3) — rotate the API key", found["vendor:WQData"].title)
        self.assertIn("WQ_API_KEY", found["vendor:WQData"].detail)
        self.assertIn("ReadTimeout ×3", found["vendor:LI-COR"].title)
        found = vendor_conditions({"WQData": vendor(3, "quota", 429, "HTTPError (HTTP 429)", self.since)}, NOW, Settings())
        self.assertIn("quota exceeded (HTTP 429 ×3)", found["vendor:WQData"].title)


class StaleTests(unittest.TestCase):
    def report(self, rows):
        return assess_freshness(rows, NOW, freshness_env({}))

    def test_station_silent_while_vendor_answers(self):
        rows = [latest_row("Quality", WQ, m, dt.timedelta(hours=3)) for m in ("ODO", "Turbidity")]
        rows += [latest_row("Weather", WEATHER, "Rain", dt.timedelta(minutes=50))]
        found = stale_conditions(self.report(rows), {"WQData": vendor(), "LI-COR": vendor()}, NOW)
        self.assertEqual(list(found), [f"stale:{WQ}"])
        c = found[f"stale:{WQ}"]
        self.assertEqual(c.kind, STALE_SENSOR)
        self.assertEqual(c.title, "Water quality station 4501 silent for 3 h — vendor OK, check the sensor")
        self.assertIn("WQData is responding", c.detail)
        self.assertIn("has sent nothing since 2026-11-11 11:00 (3 h)", c.detail)

    def test_one_sensor_of_a_station(self):
        rows = [latest_row("Weather", WEATHER, "Rain", dt.timedelta(hours=5)),
                latest_row("Weather", WEATHER, "Air Temperature", dt.timedelta(minutes=40))]
        found = stale_conditions(self.report(rows), {"LI-COR": vendor()}, NOW)
        self.assertEqual(list(found), [f"stale:{WEATHER}:Rain"])
        self.assertIn("Weather station 22051538 Rain silent for 5 h", found[f"stale:{WEATHER}:Rain"].title)

    def test_whole_licor_site_is_one_alert(self):
        rows = [latest_row("Weather", WEATHER, "Rain", dt.timedelta(hours=4)),
                latest_row("Logger", "2577531", "Water Surface Elevation", dt.timedelta(hours=4)),
                latest_row("Logger", "2577535", "Water Surface Elevation", dt.timedelta(days=300))]   # excluded
        found = stale_conditions(self.report(rows), {"LI-COR": vendor()}, NOW)
        self.assertEqual(list(found), ["stale:LI-COR"])
        self.assertIn("Water level logger 1", found["stale:LI-COR"].detail)

    def test_not_while_the_vendor_is_failing(self):
        rows = [latest_row("Quality", WQ, "ODO", dt.timedelta(hours=3))]
        self.assertEqual(stale_conditions(self.report(rows), {"WQData": vendor(1, "server", 503)}, NOW), {})
        # No recorded outcome yet: still alerted, but without claiming the vendor is fine.
        found = stale_conditions(self.report(rows), {}, NOW)
        self.assertIn("isn't recorded yet", found[f"stale:{WQ}"].detail)

    def test_quality_quiet_hours(self):
        night = dt.datetime(2026, 11, 12, 3, 0, tzinfo=UTC)   # 22:00 Toronto, sonde silent since 18:10
        rows = [{"station_id": WQ, "group_type": "Quality", "measurement_type": "ODO",
                 "recorded_at": "2026-11-11T18:10:00"}]
        report = assess_freshness(rows, night, freshness_env({}))
        self.assertEqual(stale_conditions(report, {"WQData": vendor()}, night), {})


class SuspectTests(unittest.TestCase):
    window = dt.timedelta(hours=6)

    def readings(self, values):
        return [(site(NOW - dt.timedelta(minutes=10 * (len(values) - i))), v) for i, v in enumerate(values)]

    def test_flatline_and_its_exceptions(self):
        self.assertIn("stuck at exactly 7.2",
                      suspect_finding("Quality", WQ, "ODO", self.readings([7.2] * 36), self.window))
        self.assertIsNone(suspect_finding("Quality", WQ, "Turbidity", self.readings([0.0] * 36), self.window))
        self.assertIsNone(suspect_finding("Quality", WQ, "Salinity", self.readings([0.2] * 36), self.window))
        self.assertIsNone(suspect_finding("Quality", WQ, "ODO", self.readings([7.2] * 5), self.window))  # too few

    def test_one_spike_is_not_an_alert_but_a_pattern_is(self):
        self.assertIsNone(suspect_finding("Quality", WQ, "Water Temperature",
                                          self.readings([8.0 + i / 100 for i in range(35)] + [99.0]), self.window))
        self.assertIn("outside the physical range", suspect_finding(
            "Quality", WQ, "Water Temperature", self.readings([99.0 + i / 100 for i in range(36)]), self.window))
        self.assertIn("dissolved oxygen about 0", suspect_finding(
            "Quality", WQ, "ODO", self.readings([0.01 * (i % 3) for i in range(36)]), self.window))

    def test_only_fresh_series_and_can_be_turned_off(self):
        rows = [latest_row("Quality", WQ, "ODO", dt.timedelta(minutes=10)),
                latest_row("Quality", WQ, "Conductivity", dt.timedelta(hours=5))]
        report = assess_freshness(rows, NOW, freshness_env({}))
        recent = {(WQ, "ODO"): self.readings([7.2] * 36), (WQ, "Conductivity"): self.readings([300.0] * 36)}
        found = suspect_conditions(report, recent, Settings())
        self.assertEqual(list(found), [f"suspect:{WQ}:ODO"])
        self.assertEqual(found[f"suspect:{WQ}:ODO"].kind, SUSPECT_VALUES)
        self.assertEqual(suspect_conditions(report, recent, Settings(suspect_values=False)), {})


class EmailTextTests(unittest.TestCase):
    def test_subjects(self):
        c = alerts.Condition("stale:4501", STALE_SENSOR, "Water quality station 4501 silent for 3 h — vendor OK, check "
                             "the sensor", "detail", NOW - dt.timedelta(hours=3))
        subject, body = alerts.build_email([c], [], [], 1, NOW, Settings())
        self.assertEqual(subject, "[WELL] Water quality station 4501 silent for 3 h — vendor OK, check the sensor")
        self.assertIn("https://welldash.mcmaster.ca/api/health/data", body)
        v = alerts.Condition("vendor:LI-COR", VENDOR_DOWN, "LI-COR API not responding", "d", NOW)
        subject, body = alerts.build_email([c, v], [], [], 2, NOW, Settings())
        self.assertEqual(subject, "[WELL] 2 new alerts: LI-COR API not responding (+1 more)")   # vendor first
        self.assertLess(body.index("LI-COR API"), body.index("Water quality station"))
        self.assertIsNone(alerts.build_email([], [], [], 0, NOW, Settings()))


class DigestTests(unittest.TestCase):
    def test_digest_lists_open_alerts(self):
        from utils.digest import build_digest
        freshness = assess_freshness([latest_row("Quality", WQ, "ODO", dt.timedelta(minutes=10))], NOW, {})
        incident = {"title": "LI-COR API not responding", "started_at": "2026-11-11T13:30:00-05:00"}
        _, body = build_digest("2026-11-11", freshness, {}, [], None, [incident])
        self.assertIn("Open alerts (each was emailed when it began):\n  - LI-COR API not responding (since "
                      "2026-11-11 13:30)", body)
        self.assertIn("Open alerts (each was emailed when it began):\n  none", build_digest(
            "2026-11-11", freshness, {}, [], None, [])[1])
        self.assertIn("could not be read: ProgrammingError", build_digest(
            "2026-11-11", freshness, {}, [], None, {"error": "ProgrammingError"})[1])
        self.assertNotIn("Open alerts", build_digest("2026-11-11", freshness, {}, [], None)[1])


class CheckAlertsTests(unittest.TestCase):
    """scripts/check_alerts.run() end to end on SQLite, with a fake sender."""

    @classmethod
    def setUpClass(cls):
        from server import create_app
        from db.database import db
        cls.app, cls.db = create_app(), db

    def setUp(self):
        import check_alerts
        self.check = check_alerts
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.create_all()
        self.sent = []
        self.logs = []

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def add_readings(self, group, station, measurement, newest, count=6, value=lambda i: 5.0 + i / 10):
        from db.models import SensorMeasurement
        for i in range(count):
            self.db.session.add(SensorMeasurement(
                station_id=station, group_type=group, measurement_type=measurement, unit="u", value=value(i),
                recorded_at=site(newest - dt.timedelta(minutes=10 * i))))
        self.db.session.commit()

    def send(self, settings, recipients, subject, body):
        self.sent.append((recipients, subject, body))

    def run_at(self, now, env=SMTP, send=None):
        return self.check.run(now=now, env=dict(env), send=send or self.send, log=self.logs.append)

    def record(self, source, error=None, now=NOW):
        from utils.alert_state import record_vendor_result
        self.assertTrue(record_vendor_result(source, error, now=now))

    def incidents(self):
        from db.models import AlertIncident
        return AlertIncident.query.order_by(AlertIncident.id).all()

    def test_once_per_incident_reminder_and_recovery(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")

        summary = self.run_at(NOW)
        self.assertEqual((summary["new"], summary["email"]), (1, "sent"))
        self.assertEqual(len(self.sent), 1)
        recipients, subject, body = self.sent[0]
        self.assertEqual(recipients, ["team@test.ca"])
        self.assertEqual(subject, "[WELL] Water quality station 4501 silent for 3 h — vendor OK, check the sensor")

        for minutes in (10, 20, 600):   # still going: no new email until the reminder is due
            self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=minutes))["email"])
        self.assertEqual(len(self.sent), 1)
        self.run_at(NOW + dt.timedelta(hours=24))
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.sent[1][1].startswith("[WELL] Still ongoing: Water quality station 4501 silent for 27 h"))
        self.assertIsNone(self.run_at(NOW + dt.timedelta(hours=25))["email"])

        later = NOW + dt.timedelta(hours=26)
        self.add_readings("Quality", WQ, "ODO", later - dt.timedelta(minutes=5), count=1)
        self.run_at(later)
        self.assertEqual(len(self.sent), 3)
        self.assertTrue(self.sent[2][1].startswith("[WELL] Recovered: Water quality station 4501"))
        self.assertIn("after 29 h", self.sent[2][2])   # from the last reading (NOW - 3 h) to the recovery
        self.assertIsNone(self.run_at(later + dt.timedelta(minutes=10))["email"])
        [incident] = self.incidents()
        self.assertEqual((incident.notifications, incident.resolved_at is not None), (2, True))

    def test_vendor_down_batches_and_holds_back_stale(self):
        self.add_readings("Weather", WEATHER, "Rain", NOW - dt.timedelta(hours=5))
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.add_readings("Quality", WQ, "Turbidity", NOW - dt.timedelta(minutes=10), count=36, value=lambda i: 0.0)
        for minutes in (30, 20, 10):
            self.record("LI-COR", http_error(503), now=NOW - dt.timedelta(minutes=minutes))
        self.record("WQData")
        self.run_at(NOW)
        self.assertEqual(len(self.sent), 1)   # one email for everything new in a run
        _, subject, body = self.sent[0]
        self.assertTrue(subject.startswith("[WELL] 2 new alerts: LI-COR API not responding since 2026-11-11 13:30 "
                                           "(HTTP 503 ×3)"), subject)
        self.assertIn("Water quality station 4501 ODO silent", body)
        self.assertNotIn("Weather station", body)   # LI-COR failing: no "vendor OK, check the sensor" for it

    def test_quiet_without_smtp_then_emails_once_configured(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        for env in ({}, {"ALERT_EMAILS": "team@test.ca"}, {k: v for k, v in SMTP.items() if k != "SMTP_HOST"}):
            self.assertEqual(self.run_at(NOW, env=env)["email"], "off")
        self.assertEqual(self.sent, [])
        self.assertIsNone(self.incidents()[0].last_notified_at)   # recorded, never marked as emailed
        self.assertEqual(self.run_at(NOW, env={**SMTP, "ALERT_EMAILS": ""})["email"], "failed")
        self.run_at(NOW + dt.timedelta(minutes=10))
        self.assertEqual(len(self.sent), 1)

    def test_failed_send_is_retried_next_run(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")

        def broken(*args):
            raise OSError("connection refused")
        self.assertEqual(self.run_at(NOW, send=broken)["email"], "failed")
        self.assertEqual(self.run_at(NOW + dt.timedelta(minutes=10))["email"], "sent")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(len(self.incidents()), 1)

    def test_dry_run_changes_nothing(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        summary = self.check.run(now=NOW, env=dict(SMTP), send=self.send, log=self.logs.append, dry_run=True)
        self.assertEqual((summary["email"], self.sent, self.incidents()), ("dry-run", [], []))

    def test_vendor_status_counts_failures_and_resets(self):
        from utils.alert_state import vendor_statuses
        self.record("WQData", http_error(429), now=NOW - dt.timedelta(minutes=20))
        self.record("WQData", http_error(429), now=NOW - dt.timedelta(minutes=10))
        row = vendor_statuses()["WQData"]
        self.assertEqual((row["consecutive_failures"], row["last_error_kind"], row["last_http_status"]),
                         (2, "quota", 429))
        self.assertEqual(row["failing_since"], NOW - dt.timedelta(minutes=20))
        self.record("WQData")
        row = vendor_statuses()["WQData"]
        self.assertEqual((row["consecutive_failures"], row["failing_since"], row["last_success_at"]), (0, None, NOW))

    def test_health_data_lists_open_alerts(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        self.run_at(NOW)
        with mock.patch("api.routes.health.datetime") as clock:
            clock.now.return_value = NOW
            body = self.app.test_client().get("/health/data").get_json()
        [incident] = body["alerts"]["open"]
        self.assertEqual((incident["kind"], incident["key"]), (STALE_SENSOR, f"stale:{WQ}"))
        self.assertEqual(body["alerts"]["vendors"]["WQData"]["consecutive_failures"], 0)

    def test_record_never_raises(self):
        from utils.alert_state import record_vendor_result
        self.db.drop_all()   # as before the migration has run
        self.assertFalse(record_vendor_result("LI-COR", log=self.logs.append))
        self.assertIn("Couldn't record", self.logs[-1])
        self.db.create_all()


def reply(status=200, body=None):
    response = requests.Response()
    response.status_code = status
    response._content = b"{}" if body is None else __import__("json").dumps(body).encode()
    response.url = "https://vendor.test/?apiKey=SECRET"
    return response


class VendorReplyTests(unittest.TestCase):
    """The services report failures from the HTTP reply itself, not "no data"."""

    def test_wqdata_error_is_kept_not_hidden(self):
        service = quality.QualityService("https://wq.test", "SECRET", WQ)
        with mock.patch.object(quality.requests, "get", return_value=reply(503)), mock.patch("builtins.print"):
            self.assertEqual(service.get_quality_data("2026-11-11 00:00:00", "2026-11-11 01:00:00"), [])
        self.assertEqual(describe_vendor_error(service.last_error)[:2], ("server", 503))
        with mock.patch.object(quality.requests, "get", return_value=reply(200, {"data": [], "info": {}})):
            service.get_quality_data("2026-11-11 00:00:00", "2026-11-11 01:00:00")
        self.assertIsNone(service.last_error)   # reset by a call that succeeds
        with mock.patch.object(quality.requests, "get", return_value=reply(200, ["not", "an", "object"])), \
                mock.patch("builtins.print"):
            service.get_quality_data("2026-11-11 00:00:00", "2026-11-11 01:00:00")
        self.assertIsInstance(service.last_error, BadVendorResponse)

    def test_licor_reply_without_data_is_an_error(self):
        service = weather.WeatherService("https://licor.test", "token", WEATHER)
        start = dt.datetime(2026, 11, 11, tzinfo=UTC)
        with mock.patch.object(weather.requests, "get", return_value=reply(200, {"message": "maintenance"})):
            with self.assertRaises(BadVendorResponse):
                service.get_page(start, start + dt.timedelta(hours=1))
        with mock.patch.object(weather.requests, "get", return_value=reply(200, {"data": []})):
            self.assertEqual(service.get_page(start, start + dt.timedelta(hours=1)), ([], False))
        with mock.patch.object(weather.requests, "get", return_value=reply(401)), self.assertRaises(requests.HTTPError):
            service.get_page(start, start + dt.timedelta(hours=1))


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the alert tables against PostgreSQL")
class PostgresTests(unittest.TestCase):
    """The migration's tables on PostgreSQL 13, and the real ingestion recording vendor outcomes from mocked HTTP."""

    @classmethod
    def setUpClass(cls):
        import importlib
        saved = Config.SQLALCHEMY_DATABASE_URI
        Config.SQLALCHEMY_DATABASE_URI = os.environ["TEST_POSTGRES_URL"]
        try:
            from server import create_app
            cls.app = create_app()
        finally:
            Config.SQLALCHEMY_DATABASE_URI = saved
        from db.database import db
        from db.models import SensorMeasurement
        cls.db = db
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        with db.engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS alert_incidents, vendor_status")
        SensorMeasurement.__table__.create(db.engine, checkfirst=True)
        sql = (APP / "db" / "migrations" / "0003_monitoring_alerts.sql").read_text(encoding="utf-8")
        with db.engine.begin() as conn:   # the tables as the migration makes them, not as create_all would
            conn.exec_driver_sql(sql)
        with mock.patch.object(Config, "HOBO_LOGGERS", WEATHER):   # unset in tests; the module builds its services
            cls.ingest = importlib.import_module("scripts.inject_from_api")

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        with cls.db.engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS alert_incidents, vendor_status, sensor_measurements")
        cls.ctx.pop()

    def setUp(self):
        with self.db.engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE alert_incidents, vendor_status, sensor_measurements")

    def ingest_with(self, licor, wqdata):
        """Run the real inject_all_new_data with the vendors' HTTP replies mocked. Both services call the same
        requests.get, so one mock answers each by its URL."""
        ingest = self.ingest
        services = {"weather_service": weather.WeatherService("https://licor.test", "token", WEATHER),
                    "quality_service": quality.QualityService("https://wq.test", "SECRET", WQ)}
        with mock.patch.object(ingest, "app", self.app), \
                mock.patch.multiple(ingest, **services), \
                mock.patch.object(ingest.Config, "WQ_DEVICE_ID", WQ), \
                mock.patch.object(weather.requests, "get", return_value=licor), \
                mock.patch.object(weather.time, "sleep"), \
                mock.patch.object(quality.requests, "get", return_value=wqdata), \
                mock.patch("builtins.print"):
            ingest.inject_all_new_data()

    def test_ingestion_records_real_outcomes(self):
        from utils.alert_state import vendor_statuses
        ok_licor, ok_wq = reply(200, {"data": []}), reply(200, {"data": [], "info": {}})
        self.ingest_with(ok_licor, ok_wq)
        rows = vendor_statuses()
        self.assertEqual((rows["LI-COR"]["consecutive_failures"], rows["WQData"]["consecutive_failures"]), (0, 0))
        self.assertIsNotNone(rows["WQData"]["last_success_at"].tzinfo)
        for _ in range(3):
            with self.assertRaisesRegex(RuntimeError, "WQData") as caught:
                self.ingest_with(ok_licor, reply(503))   # WQData's failure now fails the run
            self.assertNotIn("SECRET", str(caught.exception))
        with self.assertRaisesRegex(RuntimeError, "LI-COR, WQData"):
            self.ingest_with(reply(200, {"message": "no data key"}), reply(503))
        self.db.session.remove()
        rows = vendor_statuses()
        self.assertEqual((rows["WQData"]["consecutive_failures"], rows["WQData"]["last_error_kind"]), (4, "server"))
        self.assertEqual((rows["LI-COR"]["consecutive_failures"], rows["LI-COR"]["last_error_kind"]),
                         (1, "bad_response"))

        import check_alerts
        sent = []
        check_alerts.run(env=dict(SMTP), send=lambda *a: sent.append(a), log=lambda *a: None)
        self.assertEqual(len(sent), 1)
        self.assertIn("WQData API not responding", sent[0][2])
        check_alerts.run(env=dict(SMTP), send=lambda *a: sent.append(a), log=lambda *a: None)
        self.assertEqual(len(sent), 1)   # the open-incident index and timestamptz columns work as intended


if __name__ == "__main__":
    unittest.main()
