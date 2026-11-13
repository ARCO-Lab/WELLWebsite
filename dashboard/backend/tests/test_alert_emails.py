"""The text of the WELL emails: the subjects and both bodies (Markdown text and the HTML rendered from it) of each
kind of alert email and of a mixed one, and of the daily digest (utils/alerts.py, utils/digest.py,
utils/email_format.py), compared with snapshots in tests/golden/emails/; plus the ALERT_QUIET_KINDS rule.
UPDATE_GOLDEN=1 rewrites the snapshots instead of comparing (see tests/golden/README.md).
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import sys
import unittest
from types import SimpleNamespace

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from utils import email_format  # noqa: E402
from utils.alerts import (  # noqa: E402
    DEFAULT_QUIET_KINDS, STALE_SENSOR, SUSPECT_VALUES, VENDOR_DOWN, Settings, build_email, needs_email,
    parse_quiet_kinds, settings_from_env,
)
from utils.digest import build_digest  # noqa: E402
from utils.monitoring import assess_freshness  # noqa: E402

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden" / "emails"
UPDATE = os.getenv("UPDATE_GOLDEN") == "1"

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 13, 3, tzinfo=UTC)   # Thu Nov 12, 08:03 in Toronto


def toronto(day, hour, minute=0):
    """A November 2026 Toronto time (EST, UTC-5) as aware UTC."""
    return dt.datetime(2026, 11, day, hour + 5, minute, tzinfo=UTC)


def incident(key, kind, title, detail, started, resolved=None, reopened=None):
    return SimpleNamespace(incident_key=key, kind=kind, title=title, detail=detail, started_at=started,
                           resolved_at=resolved, reopened_at=reopened)


LOGGER4_SILENT = incident(
    "stale:LI-COR:2577534", STALE_SENSOR, "Water level logger 4 silent for 4 h — vendor OK, check the sensor",
    "LI-COR is responding (latest call 2026-11-12 08:00); Water level logger 4 has sent nothing since "
    "2026-11-12 04:00 (4 h). Check the sensor, its power and its telemetry in the field.", toronto(12, 4))
LOGGER1_LEVEL = incident(
    "suspect:LI-COR:2577531:Water Surface Elevation", SUSPECT_VALUES,
    "Water level logger 1 Water Surface Elevation looks wrong — check the probe",
    "Readings are arriving, but Water level logger 1 Water Surface Elevation: about 0.01 m of water over the "
    "sensor for 6 h (median); the logger may be out of the water, buried or the creek dry there. Look at the chart "
    "on the dashboard, then check and clean the sensor in the field if it isn't a real event.",
    toronto(11, 12), resolved=toronto(12, 8, 3))
WQ_ODO = incident(
    "suspect:WQData:4501:ODO", SUSPECT_VALUES, "Water quality station 4501 ODO looks wrong — check the probe",
    "Readings are arriving, but Water quality station 4501 ODO: dissolved oxygen about 0 mg/L for 6 h (median "
    "0.02); the probe may be fouled or out of the water. Look at the chart on the dashboard, then check and clean "
    "the sensor in the field if it isn't a real event.", toronto(11, 6, 30))
WQDATA_DOWN = incident(
    "vendor:WQData", VENDOR_DOWN,
    "WQData API not responding since 2026-11-12 07:20 (HTTP 503 ×3) — check vendor status",
    "The WQData API call has failed on the last 3 ingestion runs, since 2026-11-12 07:20 (last error: HTTPError "
    "(HTTP 503)). The last successful call was at 2026-11-12 07:10. Check the vendor's status page or support; our "
    "sensors may be fine. Ingestion catches up on missed readings by itself once the API answers (up to 14 days "
    "back).", toronto(12, 7, 20))
LICOR_AUTH = incident(
    "vendor:LI-COR", VENDOR_DOWN, "LI-COR rejects our credentials (HTTP 401 ×3) — rotate the API key",
    "LI-COR has refused the API credentials on the last 3 ingestion runs, since 2026-11-12 07:30. The last "
    "successful call was at 2026-11-12 07:20. Get a new key from LI-COR, set HOBOLINK_API_TOKEN in "
    "dashboard/backend/app/.env on the VM and in the repository secret of the same name, then recreate the "
    "worker. No LI-COR data is being stored until then; the sensors may be fine.", toronto(12, 7, 30))
WEATHER_RAIN_RECOVERED = incident(
    "stale:LI-COR:22051538:Rain", STALE_SENSOR,
    "Weather station 22051538 Rain silent for 5 h — vendor OK, check the sensor", "detail",
    toronto(12, 1, 40), resolved=toronto(12, 7, 50))


def flap(item, reopened):
    return SimpleNamespace(**{**vars(item), "reopened_at": reopened})


def check_golden(test, name, actual):
    """Compare `actual` with tests/golden/emails/<name>, or write it there with UPDATE_GOLDEN=1."""
    path = GOLDEN / name
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(actual.encode("utf-8"))
        return
    test.assertTrue(path.exists(), f"{path} is missing; create it with UPDATE_GOLDEN=1 (tests/golden/README.md)")
    test.maxDiff = None
    test.assertEqual(path.read_bytes().decode("utf-8"), actual, f"golden/emails/{name} differs")


class AlertEmailSnapshots(unittest.TestCase):
    def check(self, name, email):
        check_golden(self, f"{name}.txt", f"Subject: {email.subject}\n\n{email.text}")
        check_golden(self, f"{name}.html", email.html)

    def test_new(self):
        email = build_email([LOGGER4_SILENT], [], [], [LOGGER4_SILENT], NOW, Settings())
        self.assertEqual(email.subject, "[WELL] New: Logger 4 silent 4 h — check the sensor")
        self.check("new", email)

    def test_reminder(self):
        email = build_email([], [WQ_ODO], [], [WQ_ODO], NOW, Settings())
        self.assertEqual(email.subject, "[WELL] Still open: Water quality station 4501 dissolved oxygen readings "
                                        "look wrong (26 h)")
        self.check("reminder", email)

    def test_back_again(self):
        back = flap(WQDATA_DOWN, toronto(12, 7, 30))
        email = build_email([], [], [], [back], NOW, Settings(), back_again=[back])
        self.assertEqual(email.subject, "[WELL] Back again: WQData API not responding — check vendor status")
        self.check("back_again", email)

    def test_recovered(self):
        email = build_email([], [], [WEATHER_RAIN_RECOVERED], [], NOW, Settings())
        self.assertEqual(email.subject, "[WELL] Recovered: Weather station 22051538 rain (6 h)")
        self.check("recovered", email)

    def test_quiet_recovery_alone_is_not_sent_but_can_be(self):
        self.assertIsNone(build_email([], [], [LOGGER1_LEVEL], [], NOW, Settings()))
        email = build_email([], [], [LOGGER1_LEVEL], [], NOW, Settings(quiet_kinds=frozenset()))
        self.assertEqual(email.subject, "[WELL] Recovered: Logger 1 water level (20 h)")   # the owner's example
        self.check("recovered_quiet_kind", email)

    def test_mixed(self):
        """Every section at once, plus a quiet recovery folded in: one email that shows the whole state."""
        back = flap(WQDATA_DOWN, toronto(12, 7, 30))
        email = build_email([LOGGER4_SILENT, LICOR_AUTH], [WQ_ODO], [LOGGER1_LEVEL, WEATHER_RAIN_RECOVERED],
                            [LOGGER4_SILENT, LICOR_AUTH, WQ_ODO, back], NOW, Settings(), back_again=[back])
        self.assertEqual(email.subject, "[WELL] 2 new, 1 still open, 1 back again, 2 recovered")
        text = email.text
        order = [text.index(h) for h in ("## New problems", "## Still open (reminder)", "## Back again",
                                         "## Recovered", "## Open right now", "\n---\n")]
        self.assertEqual(order, sorted(order))
        self.assertLess(text.index("**LI-COR API**"), text.index("**Logger 4**"))   # vendor problems first
        self.check("mixed", email)

    def test_other_subjects(self):
        self.assertEqual(build_email([LICOR_AUTH], [], [], [LICOR_AUTH], NOW, Settings()).subject,
                         "[WELL] New: LI-COR API rejects our credentials — rotate the API key")
        self.assertEqual(build_email([], [LOGGER4_SILENT], [], [LOGGER4_SILENT], NOW, Settings()).subject,
                         "[WELL] Still open: Logger 4 silent 4 h")   # a silence already says how long
        self.assertEqual(build_email([], [], [WEATHER_RAIN_RECOVERED, LOGGER1_LEVEL], [], NOW, Settings()).subject,
                         "[WELL] 2 recovered")
        self.assertIsNone(build_email([], [], [], [LOGGER4_SILENT], NOW, Settings()))

    def test_no_emoji_and_same_content_in_both_parts(self):
        back = flap(WQDATA_DOWN, toronto(12, 7, 30))
        email = build_email([LOGGER4_SILENT, LICOR_AUTH], [WQ_ODO], [LOGGER1_LEVEL], [LOGGER4_SILENT], NOW,
                            Settings(), back_again=[back])
        for part in (email.subject, email.text, email.html):
            self.assertFalse([c for c in part if ord(c) >= 0x2600 and c != "→"], part[:80])
        # The HTML, without its tags, reads line for line like the text without its Markdown marks.
        import html
        import re
        shown = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br>|</li>|</h2>|</p>", "\n", email.html)))
        for line in email.text.splitlines():
            plain = line.strip().removeprefix("## ").removeprefix("- ").replace("**", "")
            if plain and plain != "---":
                self.assertIn(plain, shown)

    def test_every_value_is_escaped_in_the_html(self):
        evil = incident("stale:LI-COR:<b>", STALE_SENSOR, "x silent for 1 h — <script>alert(1)</script> & y",
                        'detail "quoted" <img src=x onerror=alert(1)>', toronto(12, 7))
        email = build_email([evil], [], [], [evil], NOW, Settings(dashboard_url='https://x.test/?a=1&b="2"'))
        for raw in ("<script>", "<img", "<b>", '"2"', '"quoted"'):
            self.assertNotIn(raw, email.html)
        for escaped in ("&lt;script&gt;alert(1)&lt;/script&gt; &amp; y", "&lt;img src=x", "Weather station &lt;b&gt;",
                        "&quot;quoted&quot;", "b=&quot;2&quot;"):
            self.assertIn(escaped, email.html)


class DigestSnapshot(unittest.TestCase):
    def test_digest(self):
        latest = [
            {"group_type": "Weather", "station_id": "22051538", "measurement_type": "Rain",
             "recorded_at": "2026-11-12T06:40:00"},
            {"group_type": "Logger", "station_id": "2577534", "measurement_type": "Water Temperature",
             "recorded_at": "2026-11-12T04:00:00"},
        ]
        freshness = assess_freshness(latest, NOW.replace(minute=0), env={})
        start = dt.datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
        groups = {"Weather": {"rows": 140, "series": 1, "timestamps": [start] * 140,
                              "gaps": [(toronto(12, 2), toronto(12, 3))]}}
        incidents = [{"kind": STALE_SENSOR, "key": "stale:LI-COR:2577534", "title": LOGGER4_SILENT.title,
                      "started_at": "2026-11-12T04:00:00-05:00"}]
        recoveries = [{"kind": SUSPECT_VALUES, "key": LOGGER1_LEVEL.incident_key, "title": LOGGER1_LEVEL.title,
                       "started_at": "2026-11-11T12:00:00-05:00", "resolved_at": "2026-11-12T06:03:00-05:00",
                       "recovery_emailed": False},
                      {"kind": STALE_SENSOR, "key": WEATHER_RAIN_RECOVERED.incident_key,
                       "title": WEATHER_RAIN_RECOVERED.title, "started_at": "2026-11-12T01:40:00-05:00",
                       "resolved_at": "2026-11-12T05:50:00-05:00", "recovery_emailed": True}]
        subject, body = build_digest("2026-11-12", freshness, groups, ["Logger 1 Water Surface Elevation: about 0.01 m"],
                                     {"power_min": 12.1, "power_max": 13.4, "power_readings": 59,
                                      "last_point": "2026-11-12 07:50:00", "last_point_age_minutes": 10},
                                     incidents, None, recoveries)
        self.assertEqual(subject, "[WELL] Daily digest 2026-11-12: 2 to check")
        self.assertIn("- **Logger 1 water level**: readings back to normal. Wed Nov 11, 12:00 → Thu Nov 12, 06:03 "
                      "(18 h). Low priority, so not emailed on its own", body)
        check_golden(self, "digest.txt", f"Subject: {subject}\n\n{body}")
        check_golden(self, "digest.html", email_format.markdown_to_html(body, subject))


class QuietKindsTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_quiet_kinds(None), DEFAULT_QUIET_KINDS)
        self.assertEqual(DEFAULT_QUIET_KINDS, {SUSPECT_VALUES})
        self.assertEqual(parse_quiet_kinds("  "), DEFAULT_QUIET_KINDS)
        self.assertEqual(parse_quiet_kinds("none"), frozenset())
        self.assertEqual(parse_quiet_kinds("NONE"), frozenset())
        self.assertEqual(parse_quiet_kinds("suspect_values, stale_sensor"), {SUSPECT_VALUES, STALE_SENSOR})
        with self.assertRaises(ValueError) as e:
            parse_quiet_kinds("SUSPECT_VALUES,TYPO")
        self.assertIn("ALERT_QUIET_KINDS", str(e.exception))

    def test_from_env(self):
        self.assertEqual(settings_from_env({}).quiet_kinds, {SUSPECT_VALUES})
        self.assertEqual(settings_from_env({"ALERT_QUIET_KINDS": "none"}).quiet_kinds, frozenset())
        with self.assertRaises(ValueError):
            settings_from_env({"ALERT_QUIET_KINDS": "everything"})

    def test_which_checks_send_an_email(self):
        quiet, loud = LOGGER1_LEVEL, WEATHER_RAIN_RECOVERED
        s = Settings()
        self.assertFalse(needs_email([], [], [quiet], [], s))          # a quiet recovery alone waits
        self.assertTrue(needs_email([], [], [loud], [], s))            # a sensor back is emailed at once
        self.assertTrue(needs_email([], [], [quiet, loud], [], s))
        self.assertTrue(needs_email([LOGGER4_SILENT], [], [quiet], [], s))   # rides along with a new alert
        self.assertTrue(needs_email([], [WQ_ODO], [quiet], [], s))
        self.assertTrue(needs_email([], [], [quiet], [WQDATA_DOWN], s))
        self.assertTrue(needs_email([], [], [quiet], [], Settings(quiet_kinds=frozenset())))
        self.assertFalse(needs_email([], [], [loud], [], Settings(quiet_kinds=frozenset({STALE_SENSOR}))))
        # Only recoveries are ever quiet: a new problem of a quiet kind is emailed straight away.
        self.assertTrue(needs_email([WQ_ODO], [], [], [], s))
        self.assertFalse(needs_email([], [], [], [], s))


class FormatTests(unittest.TestCase):
    def test_times_and_names(self):
        self.assertEqual(email_format.when(toronto(11, 12)), "Wed Nov 11, 12:00")
        self.assertEqual(email_format.when("2026-11-12T08:03:00-05:00"), "Thu Nov 12, 08:03")
        self.assertEqual(email_format.span(toronto(11, 12), toronto(12, 8, 3)),
                         "Wed Nov 11, 12:00 → Thu Nov 12, 08:03 (20 h)")
        self.assertEqual(email_format.since(toronto(12, 7, 20), NOW), "Since Thu Nov 12, 07:20 (43 min)")
        self.assertEqual(email_format.what("vendor:LI-COR"), "LI-COR API")
        self.assertEqual(email_format.what("stale:LI-COR"), "All LI-COR stations")
        self.assertEqual(email_format.what("stale:WQData:4501"), "Water quality station 4501")
        self.assertEqual(email_format.what("stale:LI-COR:2577535:Water Temperature"), "Logger 5 water temperature")
        self.assertEqual(email_format.what("odd"), "odd")

    def test_html_structure(self):
        out = email_format.markdown_to_html("Top line.\n\n## Head\n\n- **A**: b\n  more\n  - nested\n\n---\n\n"
                                            "See https://x.test/a?b=1&c=2.\n")
        self.assertIn("<h2", out)
        self.assertIn("<strong>A</strong>: b<br>more", out)
        self.assertIn('<a href="https://x.test/a?b=1&amp;c=2"', out)   # the full stop isn't part of the link
        self.assertIn("<hr", out)
        self.assertNotIn("**", out)


if __name__ == "__main__":
    unittest.main()
