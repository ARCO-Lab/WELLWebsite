"""The daily digest: settings, gaps, implausible-value rules and the text (utils/digest.py), and its database
reads (scripts/daily_digest.py) against an in-memory SQLite database.
Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import sys
from unittest import TestCase, main, mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from utils.digest import (  # noqa: E402
    LOGGER_SENSORS, anomalies, build_digest, find_gaps, parse_alert_emails, smtp_settings, station_gaps,
)
from utils.monitoring import assess_freshness  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402
from config import Config  # noqa: E402

# Config reads DATABASE_URL once, when first imported; another test module may have imported it first.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"

T0 = dt.datetime(2026, 11, 10, 7, 0)


def utc(naive_site_time):
    return naive_site_time.replace(tzinfo=EST_TZ).astimezone(dt.timezone.utc)


class AlertEmailTests(TestCase):
    def test_parsing(self):
        self.assertEqual(parse_alert_emails("a@mcmaster.ca"), (["a@mcmaster.ca"], []))
        self.assertEqual(parse_alert_emails(" a@mcmaster.ca, b@x.org ;c@y.ca  A@mcmaster.ca,,"),
                         (["a@mcmaster.ca", "b@x.org", "c@y.ca"], []))
        self.assertEqual(parse_alert_emails("a@mcmaster.ca,not-an-address,@x.ca"),
                         (["a@mcmaster.ca"], ["not-an-address", "@x.ca"]))
        for empty in (None, "", " , "):
            self.assertEqual(parse_alert_emails(empty), ([], []))


class SmtpSettingsTests(TestCase):
    def test_needs_host_and_port(self):
        self.assertIsNone(smtp_settings({}))
        self.assertIsNone(smtp_settings({"SMTP_HOST": "smtp.mcmaster.ca"}))
        self.assertIsNone(smtp_settings({"SMTP_PORT": "25"}))

    def test_optional_login_and_sender(self):
        s = smtp_settings({"SMTP_HOST": "relay", "SMTP_PORT": "25", "SMTP_FROM": "well@mcmaster.ca"})
        self.assertEqual((s["host"], s["port"], s["user"], s["password"], s["from"]),
                         ("relay", 25, "", "", "well@mcmaster.ca"))
        s = smtp_settings({"SMTP_HOST": "relay", "SMTP_PORT": "587", "SMTP_USER": "u@x.ca", "SMTP_PASSWORD": "pw"})
        self.assertEqual(s["from"], "u@x.ca")

    def test_bad_settings(self):
        with self.assertRaises(ValueError):
            smtp_settings({"SMTP_HOST": "relay", "SMTP_PORT": "smtp", "SMTP_FROM": "a@b.ca"})
        with self.assertRaises(ValueError):
            smtp_settings({"SMTP_HOST": "relay", "SMTP_PORT": "25"})   # no sender


class GapTests(TestCase):
    def test_gaps_over_30_minutes(self):
        ts = [T0 + dt.timedelta(minutes=m) for m in (0, 10, 20, 60, 70, 80)]
        end = T0 + dt.timedelta(minutes=90)
        self.assertEqual(find_gaps(ts, T0, end), [(T0 + dt.timedelta(minutes=20), T0 + dt.timedelta(minutes=60))])

    def test_start_counts_but_the_time_after_the_newest_reading_doesnt(self):
        # The stretch after the newest reading is LI-COR's usual delay; the newest-reading ages cover it.
        ts = [T0 + dt.timedelta(hours=1)]
        end = T0 + dt.timedelta(hours=3)
        self.assertEqual(find_gaps(ts, T0, end), [(T0, ts[0])])
        self.assertEqual(find_gaps([], T0, end), [(T0, end)])

    def test_exactly_30_minutes_is_not_a_gap(self):
        ts = [T0, T0 + dt.timedelta(minutes=30)]
        self.assertEqual(find_gaps(ts, T0, ts[-1]), [])


class StationGapTests(TestCase):
    def test_one_logger_silent_while_the_others_report(self):
        # The group's time slots are full (logger 2 reports), so only the per-station gaps show logger 3's 2 hours.
        every = [T0 + dt.timedelta(minutes=10 * i) for i in range(30)]
        logger3 = [t for t in every if not T0 + dt.timedelta(hours=1) < t < T0 + dt.timedelta(hours=3)]
        end = every[-1]
        group = find_gaps(sorted(set(every) | set(logger3)), T0, end)
        self.assertEqual(group, [])
        self.assertEqual(station_gaps(group, {"2577532": every, "2577533": logger3}, T0, end),
                         [("Logger 3", T0 + dt.timedelta(hours=1), T0 + dt.timedelta(hours=3))])

    def test_a_gap_of_the_whole_group_isnt_repeated_per_station(self):
        ts = [T0, T0 + dt.timedelta(hours=2)]
        group = find_gaps(ts, T0, ts[-1])
        self.assertEqual(station_gaps(group, {"2577532": ts, "2577533": ts}, T0, ts[-1]), [])
        self.assertEqual(station_gaps([], {"22051538": [T0]}, T0, T0 + dt.timedelta(hours=2)), [])   # one station


class AnomalyTests(TestCase):
    def test_dissolved_oxygen_near_zero(self):
        found = anomalies("Quality", "4501", "ODO", [0.0, 0.01, 0.02, 0.0])
        self.assertEqual(len(found), 1)
        self.assertIn("dissolved oxygen is about 0 mg/L", found[0])
        self.assertEqual(anomalies("Quality", "4501", "ODO", [9.8, 10.1, 10.0, 0.0]), [])
        self.assertIn("saturation", anomalies("Quality", "4501", "ODOSat", [0.0, 0.2, 0.1])[0])

    def test_logger_depth_near_zero(self):
        number, sensor = LOGGER_SENSORS["2577531"]
        self.assertEqual(number, 1)
        dry = anomalies("Logger", "2577531", "Water Surface Elevation", [sensor + 0.01, sensor - 0.01, sensor])
        self.assertEqual(len(dry), 1)
        self.assertIn("Logger 1", dry[0])
        self.assertIn("out of the water", dry[0])
        self.assertEqual(anomalies("Logger", "2577531", "Water Surface Elevation", [sensor + 0.3] * 3), [])
        # Water temperature on a logger isn't a depth
        self.assertEqual(anomalies("Logger", "2577531", "Water Temperature", [8.0, 8.1]), [])

    def test_out_of_range_values(self):
        found = anomalies("Quality", "4501", "Conductivity", [500, -3, 510])
        self.assertEqual(len(found), 1)
        self.assertIn("1 of 3 readings outside", found[0])
        self.assertIn("2 of 3", anomalies("Weather", "22051538", "Relative Humidity", [50, 101, 120])[0])
        self.assertEqual(anomalies("Weather", "22051538", "Rain", [0.0] * 50), [])   # no rule for rain

    def test_stuck_quality_sensor(self):
        found = anomalies("Quality", "4501", "TSS", [3.2] * 12)
        self.assertEqual(len(found), 1)
        self.assertIn("all 12 readings are exactly 3.2", found[0])
        self.assertEqual(anomalies("Quality", "4501", "TSS", [3.2] * 11), [])        # too few to tell
        self.assertIn("exactly 0", anomalies("Quality", "4501", "ODO", [0.0] * 12)[-1])   # only TSS, turbidity exempt
        # Clear water reads exactly 0 on TSS and turbidity all day; that isn't a stuck sensor
        self.assertEqual(anomalies("Quality", "4501", "TSS", [0.0] * 50), [])
        self.assertEqual(anomalies("Quality", "4501", "Turbidity", [0.0] * 50), [])
        # ... and they may read a little below 0
        self.assertEqual(anomalies("Quality", "4501", "Turbidity", [-0.4, 0.1, -0.9]), [])
        self.assertIn("outside the plausible range", anomalies("Quality", "4501", "TSS", [-2.0, 1.0])[0])
        self.assertEqual(anomalies("Quality", "4501", "Salinity", [0.37] * 60), [])  # coarse; can sit still
        self.assertEqual(anomalies("Weather", "22051538", "Pressure", [101.0] * 20), [])

    def test_no_readings(self):
        self.assertEqual(anomalies("Quality", "4501", "ODO", []), [])


class BuildDigestTests(TestCase):
    def test_text(self):
        now = dt.datetime(2026, 11, 10, 7, 0, tzinfo=EST_TZ)
        latest = [
            {"group_type": "Weather", "station_id": "22051538", "measurement_type": "Rain", "recorded_at": "2026-11-10T06:40:00"},
            {"group_type": "Logger", "station_id": "2577532", "measurement_type": "Water Temperature", "recorded_at": "2026-11-10T01:00:00"},
        ]
        freshness = assess_freshness(latest, now, env={})
        groups = {"Weather": {"rows": 140, "series": 1, "timestamps": [T0] * 140,
                              "gaps": [(T0 - dt.timedelta(hours=2), T0 - dt.timedelta(hours=1))]}}
        subject, body = build_digest("2026-11-10", freshness, groups, ["4501 ODO: dissolved oxygen is about 0"],
                                     {"power_min": 12.1, "power_max": 13.4, "power_readings": 59,
                                      "last_point": "2026-11-10 06:50:00", "last_point_age_minutes": 10})
        self.assertEqual(subject, "[WELL] Daily digest 2026-11-10: 2 to check")
        self.assertIn("Logger 2 Water Temperature: newest Tue Nov 10, 01:00 (6.0 h ago; limit 3 h)", body)
        self.assertIn("Weather: 140 rows of 144 expected (1 series), 140 of 144 time slots", body)
        self.assertIn("gap Tue Nov 10, 05:00 → Tue Nov 10, 06:00 (60 min)", body)
        self.assertIn("primary power: 12.1 to 13.4 V over 59 readings", body)
        self.assertIn("last contact (newest data point): Tue Nov 10, 06:50 (10 min ago)", body)
        self.assertIn("dissolved oxygen", body)

    def test_all_ok_and_wqdata_error(self):
        now = dt.datetime(2026, 11, 10, 7, 0, tzinfo=EST_TZ)
        latest = [{"group_type": "Weather", "station_id": "22051538", "measurement_type": "Rain",
                   "recorded_at": "2026-11-10T06:50:00"}]
        freshness = assess_freshness(latest, now, env={})
        self.assertEqual(build_digest("2026-11-10", freshness, {}, [], None)[0],
                         "[WELL] Daily digest 2026-11-10: all OK")
        subject, body = build_digest("2026-11-10", freshness, {}, [], {"error": "HTTPError (HTTP 429)"})
        self.assertEqual(subject, "[WELL] Daily digest 2026-11-10: 1 to check")
        self.assertIn("request failed: HTTPError (HTTP 429)", body)


class ReadGroupsTests(TestCase):
    def test_counts_gaps_and_findings_from_the_database(self):
        import daily_digest
        from server import create_app
        from db.database import db
        from db.models import SensorMeasurement
        app = create_app()
        with app.app_context():
            db.create_all()
            try:
                since = T0 - dt.timedelta(hours=24)
                rows = [SensorMeasurement(station_id="4501", group_type="Quality", measurement_type="ODO", value=0.0,
                                          unit="mg/L", recorded_at=T0 - dt.timedelta(minutes=10 * i)) for i in range(12)]
                rows.append(SensorMeasurement(station_id="4501", group_type="Quality", measurement_type="ODO", value=9.0,
                                              unit="mg/L", recorded_at=since - dt.timedelta(hours=1)))   # too old
                rows.append(SensorMeasurement(station_id="2577535", group_type="Logger", measurement_type="Water Temperature",
                                              value=7.0, unit="°C", recorded_at=T0 - dt.timedelta(days=400)))
                db.session.add_all(rows)
                db.session.commit()
                freshness = {"groups": {
                    "Quality": {"series": [{"station_id": "4501", "measurement_type": "ODO", "status": "ok"}]},
                    "Logger": {"series": [{"station_id": "2577535", "measurement_type": "Water Temperature",
                                           "status": "excluded"}]},
                }}
                groups, findings = daily_digest.read_groups(db, freshness, T0.replace(tzinfo=EST_TZ))
            finally:
                db.drop_all()
        self.assertEqual(set(groups), {"Quality"})   # an all-excluded group isn't counted
        self.assertEqual((groups["Quality"]["rows"], groups["Quality"]["series"]), (12, 1))
        self.assertEqual(groups["Quality"]["gaps"], [(utc(since), utc(T0 - dt.timedelta(minutes=110)))])
        self.assertEqual(len(findings), 2)   # about 0 mg/L, and stuck at exactly 0

    def test_dst_change_makes_no_gap_or_shortfall(self):
        # Clocks sprang forward at 02:00 on 2026-03-08: stored (naive) times go 01:50, 03:00, which is 10 minutes.
        import daily_digest
        from server import create_app
        from db.database import db
        from db.models import SensorMeasurement
        now = dt.datetime(2026, 3, 8, 4, 0, tzinfo=EST_TZ)
        wall = [dt.datetime(2026, 3, 8, h, m) for h in (0, 1, 3) for m in range(0, 60, 10)]
        app = create_app()
        with app.app_context():
            db.create_all()
            try:
                db.session.add_all([SensorMeasurement(station_id="22051538", group_type="Weather", measurement_type="Rain",
                                                      value=0.0, unit="mm", recorded_at=t) for t in wall])
                db.session.commit()
                freshness = {"groups": {"Weather": {"series": [
                    {"station_id": "22051538", "measurement_type": "Rain", "status": "ok"}]}}}
                groups, _ = daily_digest.read_groups(db, freshness, now)
            finally:
                db.drop_all()
        gaps = groups["Weather"]["gaps"]
        self.assertEqual(len(gaps), 1)   # only the stretch before the first reading, none at 02:00
        self.assertEqual(gaps[0][1], utc(wall[0]))
        self.assertEqual(len(groups["Weather"]["timestamps"]), 18)


class WqdataTests(TestCase):
    def test_one_request_power_and_last_point(self):
        import daily_digest
        body = {"data": [
            {"timestamp": "2026-11-10 11:40:00", "values": [{"parameterId": 115219, "value": "12.6"},
                                                            {"parameterId": 125006, "value": "0.01"}]},
            {"timestamp": "2026-11-10 11:50:00", "values": [{"parameterId": 115219, "value": 13.1}]},
        ], "info": {"more": False}}
        config = type("C", (), {"WQ_API_URL": "https://wq.example/api", "WQ_API_KEY": "k", "WQ_DEVICE_ID": "4501"})
        response = mock.Mock(status_code=200, json=lambda: body)
        now = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)
        with mock.patch.object(daily_digest.requests, "get", return_value=response) as get:
            result = daily_digest.read_wqdata(config, now)
        get.assert_called_once()
        self.assertEqual((result["power_min"], result["power_max"], result["power_readings"]), (12.6, 13.1, 2))
        self.assertEqual(result["last_point"], "2026-11-10 06:50:00")   # UTC -> Toronto (EST)
        self.assertEqual(result["last_point_age_minutes"], 10)

    def test_missing_settings_make_no_request(self):
        import daily_digest
        config = type("C", (), {"WQ_API_URL": None, "WQ_API_KEY": None, "WQ_DEVICE_ID": None})
        with mock.patch.object(daily_digest.requests, "get") as get:
            self.assertIn("error", daily_digest.read_wqdata(config, dt.datetime.now(dt.timezone.utc)))
        get.assert_not_called()


class FakeSMTP:
    """Stands in for smtplib.SMTP and records what the digest does with it."""
    instances = []

    def __init__(self, host, port, timeout):
        self.starttls_offered, self.calls = FakeSMTP.offer_starttls, []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        self.calls.append("ehlo")

    def has_extn(self, name):
        return name == "starttls" and self.starttls_offered

    def starttls(self, context):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append("login")

    def send_message(self, message):
        self.calls.append("send")


class SendEmailTests(TestCase):
    def send(self, offer_starttls, user="u@x.ca", password="pw"):
        import daily_digest
        FakeSMTP.offer_starttls, FakeSMTP.instances = offer_starttls, []
        settings = {"host": "relay", "port": 587, "user": user, "password": password, "from": "well@x.ca"}
        with mock.patch.object(daily_digest.smtplib, "SMTP", FakeSMTP):
            daily_digest.send_email(settings, ["a@x.ca"], "subject", "body")
        return FakeSMTP.instances[0].calls

    def test_logs_in_only_after_starttls(self):
        self.assertEqual(self.send(True), ["ehlo", "starttls", "ehlo", "login", "send"])

    def test_refuses_to_log_in_without_encryption(self):
        with self.assertRaises(RuntimeError) as e:
            self.send(False)
        self.assertIn("STARTTLS", str(e.exception))
        self.assertNotIn("login", FakeSMTP.instances[0].calls)
        self.assertNotIn("send", FakeSMTP.instances[0].calls)

    def test_a_relay_without_login_may_be_plain(self):
        self.assertEqual(self.send(False, user="", password=""), ["ehlo", "send"])


class DeliverTests(TestCase):
    SMTP = {"SMTP_HOST": "relay", "SMTP_PORT": "587", "SMTP_FROM": "well@x.ca"}

    def deliver(self, env, dry_run=False, send=None):
        import daily_digest
        sent = []
        with mock.patch("builtins.print"):
            code = daily_digest.deliver("subject", "body", dry_run, env=env,
                                        send=send or (lambda *a: sent.append(a)))
        return code, sent

    def test_prints_when_smtp_isnt_set_up(self):
        self.assertEqual(self.deliver({"ALERT_EMAILS": "a@x.ca"}), (0, []))

    def test_dry_run_never_sends(self):
        self.assertEqual(self.deliver({**self.SMTP, "ALERT_EMAILS": "a@x.ca"}, dry_run=True), (0, []))

    def test_sends_to_the_recipients(self):
        code, sent = self.deliver({**self.SMTP, "ALERT_EMAILS": "a@x.ca, b@x.ca"})
        self.assertEqual(code, 0)
        self.assertEqual(sent[0][1], ["a@x.ca", "b@x.ca"])

    def test_smtp_without_valid_recipients_fails(self):
        for emails in ("", "not-an-address"):
            self.assertEqual(self.deliver({**self.SMTP, "ALERT_EMAILS": emails}), (1, []), emails)

    def test_send_failure_and_bad_settings_fail(self):
        def refuse(*a):
            raise RuntimeError("relay doesn't offer STARTTLS")
        self.assertEqual(self.deliver({**self.SMTP, "ALERT_EMAILS": "a@x.ca"}, send=refuse)[0], 1)
        self.assertEqual(self.deliver({"SMTP_HOST": "relay", "SMTP_PORT": "x", "ALERT_EMAILS": "a@x.ca"})[0], 1)


if __name__ == "__main__":
    main()
