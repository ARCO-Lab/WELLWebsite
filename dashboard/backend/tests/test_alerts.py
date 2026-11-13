"""The email alerts: their rules and text (utils/alerts.py), the alert check against an in-memory SQLite database with a
fake SMTP sender (scripts/check_alerts.py), and how ingestion records each vendor call's outcome from the real HTTP
reply (api/services, scripts/inject_from_api.py). No network, no real email.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import sys
import unittest.mock

import requests

mock = unittest.mock

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
        self.assertEqual(settings_from_env({"ALERT_CLEAR_MINUTES": "45"}).clear_after, dt.timedelta(minutes=45))
        with self.assertRaisesRegex(ValueError, "ALERT_CLEAR_MINUTES must be a number of minutes"):
            settings_from_env({"ALERT_CLEAR_MINUTES": "half an hour"})
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
        # Failing, but not yet N times: nothing new, and an open incident is held as it is.
        self.assertEqual(vendor_conditions({"LI-COR": vendor(2, "server", 503, "HTTPError (HTTP 503)", self.since)},
                                           NOW, settings), ({}, {"vendor:LI-COR"}))
        found, held = vendor_conditions({"LI-COR": vendor(6, "server", 503, "HTTPError (HTTP 503)", self.since)},
                                        NOW, settings)
        self.assertEqual(held, set())
        c = found["vendor:LI-COR"]
        self.assertEqual(c.kind, VENDOR_DOWN)
        self.assertIn("LI-COR API not responding since Wed Nov 11, 13:00 (HTTP 503 ×6)", c.title)
        self.assertIn("our sensors may be fine", c.detail)

    def test_auth_and_quota_have_their_own_advice(self):
        found, _ = vendor_conditions({"WQData": vendor(3, "auth", 401, "HTTPError (HTTP 401)", self.since),
                                      "LI-COR": vendor(3, "timeout", None, "ReadTimeout", self.since)}, NOW, Settings())
        self.assertIn("rejects our credentials (HTTP 401 ×3) — rotate the API key", found["vendor:WQData"].title)
        self.assertIn("WQ_API_KEY", found["vendor:WQData"].detail)
        self.assertIn("ReadTimeout ×3", found["vendor:LI-COR"].title)
        found, _ = vendor_conditions({"WQData": vendor(3, "quota", 429, "HTTPError (HTTP 429)", self.since)}, NOW,
                                     Settings())
        self.assertIn("quota exceeded (HTTP 429 ×3)", found["vendor:WQData"].title)


class StaleTests(unittest.TestCase):
    def report(self, rows):
        return assess_freshness(rows, NOW, freshness_env({}))

    def test_station_silent_while_vendor_answers(self):
        rows = [latest_row("Quality", WQ, m, dt.timedelta(hours=3)) for m in ("ODO", "Turbidity")]
        rows += [latest_row("Weather", WEATHER, "Rain", dt.timedelta(minutes=50))]
        found, held = stale_conditions(self.report(rows), {"WQData": vendor(), "LI-COR": vendor()}, NOW)
        self.assertEqual((list(found), held), ([f"stale:WQData:{WQ}"], set()))
        c = found[f"stale:WQData:{WQ}"]
        self.assertEqual(c.kind, STALE_SENSOR)
        self.assertEqual(c.title, "Water quality station 4501 silent for 3 h — vendor OK, check the sensor")
        self.assertIn("WQData is responding", c.detail)
        self.assertIn("has sent nothing since Wed Nov 11, 11:00 (3 h)", c.detail)

    def test_one_sensor_of_a_station(self):
        rows = [latest_row("Weather", WEATHER, "Rain", dt.timedelta(hours=5)),
                latest_row("Weather", WEATHER, "Air Temperature", dt.timedelta(minutes=40))]
        found, _ = stale_conditions(self.report(rows), {"LI-COR": vendor()}, NOW)
        self.assertEqual(list(found), [f"stale:LI-COR:{WEATHER}:Rain"])
        self.assertIn("Weather station 22051538 Rain silent for 5 h", found[f"stale:LI-COR:{WEATHER}:Rain"].title)

    def test_whole_licor_site_is_one_alert(self):
        rows = [latest_row("Weather", WEATHER, "Rain", dt.timedelta(hours=4)),
                latest_row("Logger", "2577531", "Water Surface Elevation", dt.timedelta(hours=4)),
                latest_row("Logger", "2577535", "Water Surface Elevation", dt.timedelta(days=300))]   # excluded
        found, _ = stale_conditions(self.report(rows), {"LI-COR": vendor()}, NOW)
        self.assertEqual(list(found), ["stale:LI-COR"])
        self.assertIn("Water level logger 1", found["stale:LI-COR"].detail)

    def test_not_while_the_vendor_is_failing(self):
        rows = [latest_row("Quality", WQ, "ODO", dt.timedelta(hours=3))]
        # The latest call failed: no verdict, and the vendor's open stale incidents are held as they are.
        self.assertEqual(stale_conditions(self.report(rows), {"WQData": vendor(1, "server", 503)}, NOW),
                         ({}, {"stale:WQData"}))
        # No recorded outcome yet: still alerted, but without claiming the vendor is fine.
        found, _ = stale_conditions(self.report(rows), {}, NOW)
        self.assertIn("isn't recorded yet", found[f"stale:WQData:{WQ}"].detail)

    def test_quality_quiet_hours(self):
        night = dt.datetime(2026, 11, 12, 3, 0, tzinfo=UTC)   # 22:00 Toronto, sonde silent since 18:10
        rows = [{"station_id": WQ, "group_type": "Quality", "measurement_type": "ODO",
                 "recorded_at": "2026-11-11T18:10:00"}]
        report = assess_freshness(rows, night, freshness_env({}))
        self.assertEqual(stale_conditions(report, {"WQData": vendor()}, night), ({}, set()))


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
        found, held = suspect_conditions(report, recent, Settings())
        self.assertEqual(list(found), [f"suspect:WQData:{WQ}:ODO"])
        self.assertEqual(found[f"suspect:WQData:{WQ}:ODO"].kind, SUSPECT_VALUES)
        self.assertEqual(held, {f"suspect:WQData:{WQ}:Conductivity"})   # stale: no verdict on its values
        self.assertEqual(suspect_conditions(report, recent, Settings(suspect_values=False)), ({}, set()))

    def test_too_few_readings_is_no_verdict(self):
        rows = [latest_row("Quality", WQ, "ODO", dt.timedelta(minutes=10))]
        report = assess_freshness(rows, NOW, freshness_env({}))
        found, held = suspect_conditions(report, {(WQ, "ODO"): self.readings([7.2] * 5)}, Settings())
        self.assertEqual((found, held), ({}, {f"suspect:WQData:{WQ}:ODO"}))


class EmailTextTests(unittest.TestCase):
    # The full text of every email is pinned by tests/test_alert_emails.py; this checks real conditions fit it.
    def test_subjects(self):
        c = alerts.Condition("stale:WQData:4501", STALE_SENSOR, "Water quality station 4501 silent for 3 h — vendor "
                             "OK, check the sensor", "detail", NOW - dt.timedelta(hours=3))
        email = alerts.build_email([c], [], [], [c], NOW, Settings())
        self.assertEqual(email.subject, "[WELL] New: Water quality station 4501 silent 3 h — check the sensor")
        self.assertIn("https://welldash.mcmaster.ca/api/health/data", email.text)
        v = alerts.Condition("vendor:LI-COR", VENDOR_DOWN, "LI-COR API not responding — check vendor status", "d",
                             NOW)
        email = alerts.build_email([c, v], [], [], [c, v], NOW, Settings())
        self.assertEqual(email.subject, "[WELL] 2 new")
        self.assertLess(email.text.index("LI-COR API"), email.text.index("Water quality station"))   # vendor first
        self.assertIsNone(alerts.build_email([], [], [], [c], NOW, Settings()))


class DigestTests(unittest.TestCase):
    def test_digest_lists_open_alerts(self):
        from utils.digest import build_digest
        freshness = assess_freshness([latest_row("Quality", WQ, "ODO", dt.timedelta(minutes=10))], NOW, {})
        incident = {"kind": VENDOR_DOWN, "key": "vendor:LI-COR", "title": "LI-COR API not responding",
                    "started_at": "2026-11-11T13:30:00-05:00"}
        _, body = build_digest("2026-11-11", freshness, {}, [], None, [incident])
        self.assertIn("## Open alerts (each was emailed when it began)\n\n- **LI-COR API**: not responding. Since "
                      "Wed Nov 11, 13:30 (30 min)", body)
        self.assertIn("## Open alerts (each was emailed when it began)\n\n- none", build_digest(
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
        self.html = []
        self.logs = []
        check_alerts._last_unsent["signature"] = None
        check_alerts._send_failures.update(count=0, signature=frozenset(), next_try=None)
        self.message_ids = []

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

    def send(self, settings, recipients, subject, body, html=None, message_id=None):
        self.sent.append((recipients, subject, body))
        self.html.append(html)
        self.message_ids.append(message_id)

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
        self.assertEqual(subject, "[WELL] New: Water quality station 4501 silent 3 h — check the sensor")

        for minutes in (10, 20, 600):   # still going: no new email until the reminder is due
            self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=minutes))["email"])
        self.assertEqual(len(self.sent), 1)
        self.run_at(NOW + dt.timedelta(hours=24))
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.sent[1][1].startswith("[WELL] Still open: Water quality station 4501 silent 27 h"))
        self.assertIsNone(self.run_at(NOW + dt.timedelta(hours=25))["email"])

        later = NOW + dt.timedelta(hours=26)
        self.add_readings("Quality", WQ, "ODO", later - dt.timedelta(minutes=5), count=1)
        self.run_at(later)
        self.assertEqual(len(self.sent), 3)
        self.assertTrue(self.sent[2][1].startswith("[WELL] Recovered: Water quality station 4501"))
        self.assertEqual(self.sent[2][1], "[WELL] Recovered: Water quality station 4501 (29 h)")   # from the last
        self.assertIn("Wed Nov 11, 11:00 → Thu Nov 12, 16:00 (29 h)", self.sent[2][2])   # reading to the recovery
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
        self.assertEqual(subject, "[WELL] 2 new")
        self.assertLess(body.index("**LI-COR API**: not responding"), body.index("**Water quality station 4501 "
                                                                                 "dissolved oxygen**: silent 3 h"))
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
        self.assertEqual((incident["kind"], incident["key"]), (STALE_SENSOR, f"stale:WQData:{WQ}"))
        self.assertNotIn("detail", incident)   # public: the advice and setting names are for the emails only
        self.assertEqual(body["alerts"]["vendors"]["WQData"]["consecutive_failures"], 0)

    def open_keys(self):
        return sorted(i.incident_key for i in self.incidents() if i.resolved_at is None)

    def test_a_failed_vendor_call_holds_open_stale_incidents(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        self.run_at(NOW)
        self.record("WQData", http_error(503), now=NOW + dt.timedelta(minutes=10))
        self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=50))["email"])   # no false "Recovered"
        self.assertEqual(self.open_keys(), [f"stale:WQData:{WQ}"])
        self.record("WQData", now=NOW + dt.timedelta(minutes=60))
        self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=60))["email"])   # and no "new" again
        self.assertEqual((len(self.sent), len(self.incidents())), (1, 1))

    def test_flicker_clears_after_a_delay_and_reopens_quietly(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        self.run_at(NOW)                                                      # 1: new
        self.add_readings("Quality", WQ, "ODO", NOW + dt.timedelta(minutes=5), count=1)
        self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=10))["email"])   # gone 10 min: still open
        self.assertEqual(self.open_keys(), [f"stale:WQData:{WQ}"])
        self.run_at(NOW + dt.timedelta(minutes=40))                           # gone 40 min: 2: recovered
        self.assertTrue(self.sent[1][1].startswith("[WELL] Recovered: Water quality station 4501"))
        self.assertEqual(self.open_keys(), [])
        # Silent again 2.5 h later: the same incident reopens, no "new" email.
        self.assertIsNone(self.run_at(NOW + dt.timedelta(hours=2, minutes=30))["email"])
        self.assertEqual((self.open_keys(), len(self.incidents()), len(self.sent)), ([f"stale:WQData:{WQ}"], 1, 2))

    DAY = dt.datetime(2026, 11, 11, 13, 0, tzinfo=UTC)   # 08:00 in Toronto

    def at(self, hour, minute=0, days=0):
        return self.DAY + dt.timedelta(days=days, hours=hour - 8, minutes=minute)

    def down(self, when):
        for minutes in (30, 20, 10):
            self.record("WQData", http_error(503), now=when - dt.timedelta(minutes=minutes))

    def emails_at(self, *times):
        return [self.run_at(t)["email"] for t in times]

    def kinds(self):
        """The kind of each email sent so far: new, recovered, back again or reminder."""
        names = {"[WELL] Recovered:": "recovered", "[WELL] Back again:": "back again", "[WELL] Still open:": "reminder"}
        return [next((v for k, v in names.items() if subject.startswith(k)), "new") for _, subject, _ in self.sent]

    def test_timeline_with_flap_damping(self):
        """08:00 down, 11:00 up, 11:40 down, 14:00 up, 17:00 down, 17:35 up: every change the team should hear about
        is emailed, and after a "back again" the clear takes longer (3 h, then 6 h)."""
        at, emails_at = self.at, self.emails_at
        self.down(at(8))
        self.assertEqual(emails_at(at(8), at(11)), ["sent", None])                     # new
        self.record("WQData", now=at(11, 5))
        self.assertEqual(emails_at(at(11, 10), at(11, 20), at(11, 30)), [None, None, "sent"])   # recovered
        self.down(at(11, 40))
        self.assertEqual(emails_at(at(11, 40), at(12, 0), at(12, 10)), [None, None, "sent"])    # back again
        self.assertIn("## Back again", self.sent[2][2])
        self.assertEqual(emails_at(at(13, 50)), [None])
        self.record("WQData", now=at(13, 55))
        # Gone since 13:50: with one "back again" it must stay gone 3 h, so it clears at 16:50.
        self.assertEqual(emails_at(at(14), at(15), at(16, 40)), [None, None, None])
        self.assertEqual(self.open_keys(), ["vendor:WQData"])
        self.assertEqual(emails_at(at(16, 50)), ["sent"])                              # recovered
        self.down(at(17))
        self.assertEqual(emails_at(at(17), at(17, 20), at(17, 30)), [None, None, "sent"])       # back again
        self.record("WQData", now=at(17, 35))
        # Two "back again"s: 6 h this time, from 17:30.
        self.assertEqual(emails_at(at(18), at(23, 20)), [None, None])
        self.assertEqual(emails_at(at(23, 30)), ["sent"])                              # recovered
        self.assertEqual(self.kinds(), ["new", "recovered", "back again", "recovered", "back again", "recovered"])
        self.assertEqual(len(self.incidents()), 1)

    def test_flapping_for_12_hours_on_an_off_grid_schedule(self):
        """WQData down for an hour, up for an hour, over and over, with checks at :03, :13, ... as the worker's
        10-minute schedule would land: three emails in 12 h, then one "recovered" once it has stayed up 3 h."""
        start = self.at(8)

        def down_at(minutes):
            return minutes % 120 < 60

        for minutes in range(3, 12 * 60, 10):
            when = start + dt.timedelta(minutes=minutes)
            self.record("WQData", None if not down_at(minutes) else http_error(503), now=when)
            self.run_at(when)
        self.assertEqual(self.kinds(), ["new", "recovered", "back again"])
        last_down = max(m for m in range(3, 12 * 60, 10) if down_at(m))
        for minutes in range(12 * 60 + 3, 12 * 60 + 4 * 60, 10):   # now it stays up
            when = start + dt.timedelta(minutes=minutes)
            self.record("WQData", now=when)
            self.run_at(when)
            if self.kinds()[-1] == "recovered":
                self.assertGreaterEqual(minutes - last_down, 180)
                break
        self.assertEqual(self.kinds(), ["new", "recovered", "back again", "recovered"])

    def test_a_return_after_the_reopen_window_is_a_new_incident(self):
        at, emails_at = self.at, self.emails_at
        self.down(at(8))
        self.assertEqual(emails_at(at(8)), ["sent"])
        self.record("WQData", now=at(8, 5))
        self.assertEqual(emails_at(at(8, 30)), ["sent"])                               # recovered
        self.down(at(15))                                                              # more than 6 h later
        self.assertEqual(emails_at(at(15)), ["sent"])
        self.assertEqual(self.kinds(), ["new", "recovered", "new"])
        self.assertEqual((len(self.incidents()), self.open_keys()), (2, ["vendor:WQData"]))

    def test_a_reopened_incident_gets_back_again_not_a_reminder(self):
        at, emails_at = self.at, self.emails_at
        self.down(at(8))
        self.assertEqual(emails_at(at(8), at(1, 50, days=1)), ["sent", None])         # new; no reminder yet
        self.record("WQData", now=at(2, 0, days=1))
        self.assertEqual(emails_at(at(2, 20, days=1)), ["sent"])                       # recovered
        self.down(at(8, 10, days=1))   # within 6 h, but over 24 h since the last email: still "back again"
        self.assertEqual(emails_at(at(8, 10, days=1), at(8, 30, days=1), at(8, 40, days=1)), [None, None, "sent"])
        self.assertEqual(self.kinds(), ["new", "recovered", "back again"])

    def test_steady_again_after_flapping(self):
        at, emails_at = self.at, self.emails_at
        self.down(at(8))
        emails_at(at(8), at(11))
        self.record("WQData", now=at(11, 5))
        emails_at(at(11, 10), at(11, 40))                                              # recovered
        self.down(at(11, 50))
        emails_at(at(11, 50), at(12, 20))                                              # back again: damped
        for hour in range(13, 19):   # down without a break until 18:10
            emails_at(at(hour, 10))
        self.record("WQData", now=at(18, 15))
        # Steady for over 6 h, so the usual 30 min applies again: recovered at 18:40, not 21:10.
        self.assertEqual(emails_at(at(18, 20), at(18, 30), at(18, 40)), [None, None, "sent"])
        self.assertEqual(self.kinds(), ["new", "recovered", "back again", "recovered"])

    def test_a_sensor_back_after_its_station_recovered_is_new(self):
        env = {**SMTP, "ALERT_STALE_HOURS_WEATHER": "1"}
        self.add_readings("Weather", WEATHER, "Rain", NOW - dt.timedelta(hours=2))
        self.add_readings("Weather", WEATHER, "Air Temperature", NOW - dt.timedelta(minutes=10))
        self.record("LI-COR")
        self.run_at(NOW, env=env)                                                       # 1: Rain
        self.run_at(NOW + dt.timedelta(hours=1), env=env)                               # 2: the station
        self.assertTrue(self.sent[1][1].startswith("[WELL] New: Weather station 22051538 silent"), self.sent[1][1])
        for measurement in ("Rain", "Air Temperature"):
            self.add_readings("Weather", WEATHER, measurement, NOW + dt.timedelta(hours=1, minutes=5), count=1)
        self.run_at(NOW + dt.timedelta(hours=1, minutes=10), env=env)
        self.run_at(NOW + dt.timedelta(hours=1, minutes=40), env=env)                   # 3: station recovered
        self.assertTrue(self.sent[2][1].startswith("[WELL] Recovered: Weather station 22051538 ("))
        self.add_readings("Weather", WEATHER, "Air Temperature", NOW + dt.timedelta(hours=2, minutes=55), count=1)
        self.run_at(NOW + dt.timedelta(hours=3), env=env)    # 4: Rain alone again: new, not its superseded row
        self.assertEqual(len(self.sent), 4)
        self.assertTrue(self.sent[3][1].startswith("[WELL] New: Weather station 22051538 rain silent"), self.sent[3][1])

    def test_a_pending_back_again_survives_narrowing_to_a_key_closed_before(self):
        env = {**SMTP, "ALERT_STALE_HOURS_WEATHER": "1"}
        self.add_readings("Weather", WEATHER, "Rain", NOW - dt.timedelta(hours=2))
        self.add_readings("Weather", WEATHER, "Air Temperature", NOW - dt.timedelta(minutes=10))
        self.record("LI-COR")
        self.run_at(NOW, env=env)                                                       # 1: Rain
        self.run_at(NOW + dt.timedelta(hours=1), env=env)                               # 2: the station
        for measurement in ("Rain", "Air Temperature"):
            self.add_readings("Weather", WEATHER, measurement, NOW + dt.timedelta(hours=1, minutes=5), count=1)
        self.run_at(NOW + dt.timedelta(hours=1, minutes=10), env=env)
        self.run_at(NOW + dt.timedelta(hours=1, minutes=40), env=env)                   # 3: station recovered
        self.assertIsNone(self.run_at(NOW + dt.timedelta(hours=2, minutes=10), env=env)["email"])   # reopened
        self.add_readings("Weather", WEATHER, "Air Temperature", NOW + dt.timedelta(hours=2, minutes=15), count=1)
        self.assertIsNone(self.run_at(NOW + dt.timedelta(hours=2, minutes=20), env=env)["email"])   # narrowed
        self.run_at(NOW + dt.timedelta(hours=2, minutes=40), env=env)                   # 4: back again, for Rain
        self.assertEqual(len(self.sent), 4)
        self.assertTrue(self.sent[3][1].startswith("[WELL] Back again: Weather station 22051538 rain silent"),
                        self.sent[3][1])

    def test_a_reopened_incident_keeps_its_flap_damping(self):
        """Cleared without any run seeing it absent first (missed runs), then back: the old stretch of presence
        mustn't count as steady, so the flap count, and with it the longer clear time, stays."""
        at, emails_at = self.at, self.emails_at
        self.down(at(8))
        emails_at(at(8), at(11))
        self.record("WQData", now=at(11, 5))
        emails_at(at(11, 10), at(11, 40))                                              # recovered
        self.down(at(11, 50))
        emails_at(at(11, 50), at(12, 20))                                              # back again: flaps 1
        for hour in range(13, 19):   # present without a break until 18:10: steady, flaps reset
            emails_at(at(hour, 10))
        self.down(at(18, 40))
        emails_at(at(18, 40))
        from db.models import AlertIncident
        incident = AlertIncident.query.one()
        incident.flaps = 2   # as if it had flapped again since
        self.db.session.commit()
        self.record("WQData", now=at(18, 45))
        # No run sees it gone (the worker was down) until 00:50, when it has been gone over 6 h: recovered.
        self.assertEqual(emails_at(at(0, 50, days=1)), ["sent"])
        self.down(at(1, 0, days=1))                                                    # back within 6 h
        self.assertEqual(emails_at(at(1, 0, days=1)), [None])
        incident = AlertIncident.query.one()
        self.assertEqual((incident.resolved_at, incident.flaps), (None, 2))   # reopened, damping kept

    def test_flap_window_settings(self):
        from utils.alerts import clear_window
        settings = settings_from_env({"ALERT_FLAP_CLEAR_MINUTES": "120"})

        class Incident:
            def __init__(self, flaps):
                self.flaps = flaps
        self.assertEqual([clear_window(Incident(n), settings) for n in (0, 1, 2, 3, 4, 40)],
                         [dt.timedelta(minutes=m) for m in (30, 120, 240, 480, 720, 720)])
        with self.assertRaisesRegex(ValueError, "ALERT_FLAP_CLEAR_MINUTES must be a number of minutes"):
            settings_from_env({"ALERT_FLAP_CLEAR_MINUTES": "3h"})

    def test_a_pending_back_again_survives_narrowing(self):
        for measurement in ("Rain", "Air Temperature"):
            self.add_readings("Weather", WEATHER, measurement, NOW - dt.timedelta(hours=4))
        self.record("LI-COR")
        self.run_at(NOW)                                                    # 1: the station is silent
        self.assertIn("Weather station 22051538 silent", self.sent[0][1])
        for measurement in ("Rain", "Air Temperature"):
            self.add_readings("Weather", WEATHER, measurement, NOW + dt.timedelta(minutes=5), count=1)
        self.run_at(NOW + dt.timedelta(minutes=10))
        self.run_at(NOW + dt.timedelta(minutes=40))                         # 2: recovered
        self.assertTrue(self.sent[1][1].startswith("[WELL] Recovered: Weather station"), self.sent[1][1])
        back = NOW + dt.timedelta(hours=3, minutes=10)                      # both silent again: reopened
        self.record("LI-COR", now=back)
        self.assertIsNone(self.run_at(back)["email"])
        self.add_readings("Weather", WEATHER, "Air Temperature", back + dt.timedelta(minutes=5), count=1)
        self.assertIsNone(self.run_at(back + dt.timedelta(minutes=10))["email"])   # narrowed to Rain: quiet
        self.assertEqual(self.open_keys(), [f"stale:LI-COR:{WEATHER}:Rain"])
        self.run_at(back + dt.timedelta(minutes=30))                        # 3: back again, for the sensor
        self.assertEqual(len(self.sent), 3)
        self.assertTrue(self.sent[2][1].startswith("[WELL] Back again: Weather station 22051538 rain silent"),
                        self.sent[2][1])

    def test_a_stuck_probe_doesnt_recover_overnight(self):
        stuck = lambda i: 7.2   # noqa: E731
        self.add_readings("Quality", WQ, "ODO", NOW, count=36, value=stuck)
        self.record("WQData")
        self.run_at(NOW)
        self.assertIn("dissolved oxygen readings look wrong", self.sent[0][1])
        evening = NOW + dt.timedelta(hours=4, minutes=10)   # 18:10 Toronto, the sonde's last reading of the day
        self.add_readings("Quality", WQ, "ODO", evening, count=25, value=stuck)
        self.record("WQData", now=NOW + dt.timedelta(hours=9))
        self.assertIsNone(self.run_at(NOW + dt.timedelta(hours=9))["email"])   # 23:00: 8 readings in the window
        self.assertEqual(self.open_keys(), [f"suspect:WQData:{WQ}:ODO"])

    def test_a_quiet_recovery_waits_for_the_next_email(self):
        """ALERT_QUIET_KINDS (default SUSPECT_VALUES): a stuck probe's recovery sends no email of its own; it goes in
        the next email sent anyway (here a new silent station), once."""
        varied = lambda i: 7.0 + i / 10   # noqa: E731
        self.add_readings("Quality", WQ, "ODO", NOW, count=36, value=lambda i: 7.2)
        self.add_readings("Weather", WEATHER, "Rain", NOW)
        self.record("WQData")
        self.record("LI-COR")
        self.run_at(NOW)
        self.assertEqual(self.sent[0][1], "[WELL] New: Water quality station 4501 dissolved oxygen readings look "
                                          "wrong — check the probe")
        self.add_readings("Quality", WQ, "ODO", NOW + dt.timedelta(minutes=50), count=5, value=varied)
        self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=20))["email"])
        summary = self.run_at(NOW + dt.timedelta(minutes=50))   # cleared: recovered, but not emailed on its own
        self.assertEqual((summary["recovered"], summary["quiet_waiting"], summary["email"]), (1, 1, None))
        self.assertIn("1 low-priority, kept for the next email or the digest", self.logs[-1])
        self.assertEqual((self.open_keys(), len(self.sent)), ([], 1))
        [odo] = self.incidents()
        self.assertIsNone(odo.recovery_notified_at)

        later = NOW + dt.timedelta(hours=3, minutes=30)   # the weather station has gone silent meanwhile
        self.add_readings("Quality", WQ, "ODO", later, count=16, value=varied)
        self.record("WQData", now=later)
        self.record("LI-COR", now=later)
        self.assertEqual(self.run_at(later)["email"], "sent")
        _, subject, body = self.sent[1]
        self.assertEqual(subject, "[WELL] 1 new, 1 recovered")
        self.assertIn("## Recovered\n\n- **Water quality station 4501 dissolved oxygen**: readings back to normal\n",
                      body)
        self.assertIn("**Weather station 22051538**: silent", body)
        self.assertTrue(self.html[1].startswith("<!DOCTYPE html>"))   # sent as text and HTML
        self.assertIsNotNone(self.incidents()[0].recovery_notified_at)
        self.assertIsNone(self.run_at(later + dt.timedelta(minutes=10))["email"])   # and only once

    def test_widening_and_narrowing_send_no_false_recovery(self):
        self.add_readings("Weather", WEATHER, "Rain", NOW - dt.timedelta(hours=5))
        self.add_readings("Weather", WEATHER, "Air Temperature", NOW - dt.timedelta(minutes=40))
        self.record("LI-COR")
        self.run_at(NOW)
        self.assertIn("Weather station 22051538 rain silent", self.sent[0][1])
        later = NOW + dt.timedelta(hours=3)                 # now the whole station is silent
        self.record("LI-COR", now=later)
        self.run_at(later)
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.sent[1][1].startswith("[WELL] New: Weather station 22051538 silent"), self.sent[1][1])
        self.assertNotIn("## Recovered", self.sent[1][2])     # the Rain incident was superseded, not recovered
        self.assertEqual(self.open_keys(), [f"stale:LI-COR:{WEATHER}"])
        self.add_readings("Weather", WEATHER, "Air Temperature", later + dt.timedelta(minutes=5), count=1)
        self.assertIsNone(self.run_at(later + dt.timedelta(minutes=10))["email"])   # back to just Rain: quiet
        self.assertEqual(self.open_keys(), [f"stale:LI-COR:{WEATHER}:Rain"])

    def test_without_smtp_the_email_is_logged_once(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        for minutes in (0, 10, 20):
            self.run_at(NOW + dt.timedelta(minutes=minutes), env={})
        self.assertEqual(sum("would be:" in line for line in self.logs), 1)
        self.assertEqual(sum("same alerts as already logged" in line for line in self.logs), 2)

    def test_muted_series(self):
        muted = {**SMTP, "ALERT_EXCLUDED_SERIES": f"{WQ}:*"}
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        self.run_at(NOW)
        self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=10), env=muted)["email"])   # closed, no "Recovered"
        self.assertEqual((self.open_keys(), self.incidents()[0].close_reason), ([], "superseded"))
        with self.assertRaisesRegex(ValueError, "ALERT_EXCLUDED_SERIES"):
            self.run_at(NOW, env={**SMTP, "ALERT_EXCLUDED_SERIES": "4501"})

    def test_winter_weather_hiccups_reopen_the_site_alert(self):
        """Winter: a logger silent for days, not muted, and the weather station missing its uploads now and then.
        The first miss is "every LI-COR station silent", once. Later misses reopen that incident, hours apart and long
        after ALERT_REOPEN_HOURS, instead of emailing it as new; it gets its daily reminder like any open incident."""
        from utils.digest import LOGGER_SENSORS
        logger = next(iter(LOGGER_SENSORS))

        def h(hours, minutes=0):
            return NOW + dt.timedelta(hours=hours, minutes=minutes)
        self.add_readings("Logger", logger, "Water Surface Elevation", NOW - dt.timedelta(days=2))
        self.add_readings("Weather", WEATHER, "Rain", NOW - dt.timedelta(minutes=10))
        self.record("LI-COR")
        self.assertEqual(self.emails_at(NOW), ["sent"])                                 # 1: the logger
        self.assertEqual(self.emails_at(h(4)), ["sent"])                                # 2: the whole site
        self.assertTrue(self.sent[1][1].startswith("[WELL] New: All LI-COR stations silent"), self.sent[1][1])
        self.add_readings("Weather", WEATHER, "Rain", h(8), count=19)                   # back 4:50 to 8:00
        self.assertEqual(self.emails_at(h(5), h(8)), [None, None])                      # narrowed: quiet
        self.assertEqual(self.open_keys(), [f"stale:LI-COR:{logger}"])
        self.assertEqual(self.emails_at(h(11, 10)), [None])                             # missed again: reopened
        self.assertEqual(self.open_keys(), ["stale:LI-COR"])
        self.add_readings("Weather", WEATHER, "Rain", h(11, 15), count=1)
        self.assertEqual(self.emails_at(h(11, 20), h(20)), [None, None])                # and again, 8 h later
        self.assertEqual(self.open_keys(), ["stale:LI-COR"])
        self.assertEqual(self.emails_at(h(28, 10)), ["sent"])                           # 3: its daily reminder
        self.assertEqual(self.kinds(), ["new", "new", "reminder"])
        self.assertTrue(self.sent[2][1].startswith("[WELL] Still open: All LI-COR stations silent"), self.sent[2][1])
        self.assertEqual(sum(i.incident_key == "stale:LI-COR" for i in self.incidents()), 1)

    def test_a_suspect_series_that_goes_silent_hands_over_to_the_silence_alert(self):
        self.add_readings("Quality", WQ, "ODO", NOW, count=36, value=lambda i: 7.2)
        self.record("WQData")
        self.run_at(NOW)
        self.assertIn("dissolved oxygen readings look wrong", self.sent[0][1])
        later = NOW + dt.timedelta(hours=2, minutes=30)   # 16:30 Toronto: the sonde should be reporting
        self.record("WQData", now=later)
        self.assertEqual(self.run_at(later)["email"], "sent")
        _, subject, body = self.sent[1]
        self.assertTrue(subject.startswith("[WELL] New: Water quality station 4501 silent"), subject)
        self.assertNotIn("## Recovered", body)
        self.assertEqual(self.open_keys(), [f"stale:WQData:{WQ}"])
        suspect = next(i for i in self.incidents() if i.kind == SUSPECT_VALUES)
        self.assertEqual(suspect.close_reason, "superseded")
        self.assertIsNone(self.run_at(later + dt.timedelta(hours=3))["email"])
        self.assertEqual(len(self.sent), 2)

    def test_failed_sends_back_off_up_to_an_hour(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")

        def broken(*args):
            raise OSError("timed out")
        outcomes = {m: self.run_at(NOW + dt.timedelta(minutes=m), send=broken)["email"] for m in range(0, 140, 10)}
        self.assertEqual([m for m, outcome in outcomes.items() if outcome == "failed"], [0, 10, 30, 70, 130])
        self.assertEqual(set(outcomes.values()), {"failed", "waiting"})
        self.assertTrue(any("trying again in 60 min" in line for line in self.logs))
        # Something new is tried at once, even while waiting.
        self.add_readings("Weather", WEATHER, "Rain", NOW - dt.timedelta(hours=5))
        self.record("LI-COR", now=NOW + dt.timedelta(minutes=140))
        self.assertEqual(self.run_at(NOW + dt.timedelta(minutes=140), send=broken)["email"], "failed")
        self.assertEqual(self.run_at(NOW + dt.timedelta(minutes=150))["email"], "waiting")
        self.assertEqual(self.run_at(NOW + dt.timedelta(minutes=200))["email"], "sent")   # 1 h after 140
        self.assertEqual(self.sent[0][1], "[WELL] 2 new")
        self.assertIsNone(self.run_at(NOW + dt.timedelta(minutes=210))["email"])

    def test_a_retried_email_keeps_its_message_id(self):
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        tried = []

        def accepted_then_timed_out(settings, recipients, subject, body, html=None, message_id=None):
            tried.append(message_id)
            raise TimeoutError("timed out waiting for the relay to answer")
        self.run_at(NOW, send=accepted_then_timed_out)
        self.run_at(NOW + dt.timedelta(minutes=10))
        self.assertRegex(tried[0], r"^<well-alert\.[0-9a-f]{32}@test\.ca>$")
        self.assertEqual(self.message_ids, tried)                  # the retry: the same Message-ID
        self.run_at(NOW + dt.timedelta(hours=25))                  # the reminder is another email
        self.assertNotEqual(self.message_ids[1], tried[0])

    def test_a_recovery_never_emailed_goes_to_the_digest(self):
        from utils.alert_state import mark_recoveries_reported, missed_recoveries
        from utils.digest import build_digest
        self.add_readings("Quality", WQ, "ODO", NOW - dt.timedelta(hours=3))
        self.record("WQData")
        self.run_at(NOW)

        def broken(*args):
            raise OSError("connection refused")
        self.add_readings("Quality", WQ, "ODO", NOW + dt.timedelta(minutes=5), count=1)
        for hours in range(1, 28):   # the relay is down for a day and more, while the station reports
            self.add_readings("Quality", WQ, "ODO", NOW + dt.timedelta(hours=hours, minutes=-5), count=1)
            self.run_at(NOW + dt.timedelta(hours=hours), send=broken if hours < 27 else None)
        later = NOW + dt.timedelta(hours=27)
        self.assertEqual(len(self.sent), 1)                        # the alert check has stopped retrying it
        missed = missed_recoveries(later - dt.timedelta(days=14), later - alerts.RECOVERY_WINDOW)
        self.assertEqual([r["key"] for r in missed], [f"stale:WQData:{WQ}"])
        freshness = assess_freshness([latest_row("Quality", WQ, "ODO", dt.timedelta(minutes=10))], later, {})
        _, body = build_digest("2026-11-12", freshness, {}, [], None, missed=missed)
        self.assertIn("## Older recoveries that could not be emailed\n\n- **Water quality station 4501**: reporting "
                      "again. Wed Nov 11, 11:00 → Wed Nov 11, 15:00 (4 h)", body)
        mark_recoveries_reported([r["id"] for r in missed], later)
        self.assertEqual(missed_recoveries(later - dt.timedelta(days=14), later - alerts.RECOVERY_WINDOW), [])

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
        # Strict: only a data list is a reply. Anything else is a vendor problem, never "vendor OK".
        messages = []
        for body in ({"max_results": False}, {"max_results": False, "data": None}, {"data": "x"}, []):
            with mock.patch.object(weather.requests, "get", return_value=reply(200, body)), \
                    self.assertRaises(BadVendorResponse) as caught:
                service.get_page(start, start + dt.timedelta(hours=1))
            messages.append(str(caught.exception))
        self.assertEqual(messages, ["LI-COR reply has no 'data' list (got ['max_results'])",
                                    "LI-COR reply has no 'data' list (got ['data', 'max_results'])",
                                    "LI-COR reply has no 'data' list (got ['data'])",
                                    "LI-COR reply has no 'data' list (got list)"])
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
        services["quality_service"].sleep = lambda seconds: None
        wq_replies = iter(wqdata if isinstance(wqdata, list) else [wqdata] * 100)
        with mock.patch.object(ingest, "app", self.app), \
                mock.patch.multiple(ingest, **services), \
                mock.patch.object(ingest.Config, "WQ_DEVICE_ID", WQ), \
                mock.patch.object(requests, "get",
                                  side_effect=lambda url, **kw: licor if "licor" in url else next(wq_replies)), \
                mock.patch.object(weather.time, "sleep"), \
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
        self.assertEqual(sent[0][2], "[WELL] New: WQData API not responding — check vendor status")
        self.assertIn("**WQData API**: not responding", sent[0][3])   # the text part; sent[0][4] is the HTML
        check_alerts.run(env=dict(SMTP), send=lambda *a: sent.append(a), log=lambda *a: None)
        self.assertEqual(len(sent), 1)   # the open-incident index and timestamptz columns work as intended


if __name__ == "__main__":
    unittest.main()

    def test_wqdata_failing_on_page_two_keeps_page_one_and_fails_the_run(self):
        from utils.alert_state import vendor_statuses
        stamp = (dt.datetime.now(UTC) - dt.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        page_one = reply(200, {"data": [{"timestamp": stamp, "values": [{"parameterId": 125001, "value": "8.5"}]}],
                               "info": {"more": True, "lastDataPointTimestamp": stamp, "count": 1, "total": 2}})
        with self.assertRaisesRegex(RuntimeError, "WQData request failed: HTTPError \\(HTTP 503\\)"):
            self.ingest_with(reply(200, {"data": []}), [page_one, reply(503)])
        self.db.session.remove()
        stored = self.db.session.execute(self.db.text(
            "SELECT measurement_type, value FROM sensor_measurements WHERE station_id = :s"), {"s": WQ}).all()
        self.assertEqual([tuple(r) for r in stored], [("Water Temperature", 8.5)])
        self.assertEqual(vendor_statuses()["WQData"]["consecutive_failures"], 1)
