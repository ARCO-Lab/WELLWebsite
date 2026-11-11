"""The daily digest: settings, gaps, implausible-value rules and the text (utils/digest.py), and its database
reads (scripts/daily_digest.py) against an in-memory SQLite database.
Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import sys
import unittest
from unittest import mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from utils.digest import (  # noqa: E402
    LOGGER_SENSORS, anomalies, build_digest, find_gaps, parse_alert_emails, smtp_settings,
)
from utils.monitoring import assess_freshness  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402

T0 = dt.datetime(2026, 11, 10, 7, 0)


class AlertEmailTests(unittest.TestCase):
    def test_parsing(self):
        self.assertEqual(parse_alert_emails("a@mcmaster.ca"), (["a@mcmaster.ca"], []))
        self.assertEqual(parse_alert_emails(" a@mcmaster.ca, b@x.org ;c@y.ca  A@mcmaster.ca,,"),
                         (["a@mcmaster.ca", "b@x.org", "c@y.ca"], []))
        self.assertEqual(parse_alert_emails("a@mcmaster.ca,not-an-address,@x.ca"),
                         (["a@mcmaster.ca"], ["not-an-address", "@x.ca"]))
        for empty in (None, "", " , "):
            self.assertEqual(parse_alert_emails(empty), ([], []))


class SmtpSettingsTests(unittest.TestCase):
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


class GapTests(unittest.TestCase):
    def test_gaps_over_30_minutes(self):
        ts = [T0 + dt.timedelta(minutes=m) for m in (0, 10, 20, 60, 70, 80)]
        end = T0 + dt.timedelta(minutes=90)
        self.assertEqual(find_gaps(ts, T0, end), [(T0 + dt.timedelta(minutes=20), T0 + dt.timedelta(minutes=60))])

    def test_edges_count(self):
        ts = [T0 + dt.timedelta(hours=1)]
        end = T0 + dt.timedelta(hours=3)
        self.assertEqual(find_gaps(ts, T0, end), [(T0, ts[0]), (ts[0], end)])
        self.assertEqual(find_gaps([], T0, end), [(T0, end)])

    def test_exactly_30_minutes_is_not_a_gap(self):
        ts = [T0, T0 + dt.timedelta(minutes=30)]
        self.assertEqual(find_gaps(ts, T0, ts[-1]), [])


class AnomalyTests(unittest.TestCase):
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
        found = anomalies("Quality", "4501", "TSS", [0.0] * 12)
        self.assertEqual(len(found), 1)
        self.assertIn("all 12 readings are exactly 0", found[0])
        self.assertEqual(anomalies("Quality", "4501", "TSS", [0.0] * 11), [])        # too few to tell
        self.assertEqual(anomalies("Weather", "22051538", "Pressure", [101.0] * 20), [])

    def test_no_readings(self):
        self.assertEqual(anomalies("Quality", "4501", "ODO", []), [])


class BuildDigestTests(unittest.TestCase):
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
        self.assertEqual(subject, "WELL daily digest 2026-11-10: 2 to check")
        self.assertIn("Logger 2 Water Temperature: newest 2026-11-10T01:00:00 (6.0 h ago; limit 3 h)", body)
        self.assertIn("Weather: 140 rows of 144 expected (1 series), 140 of 144 time slots", body)
        self.assertIn("gap 11-10 05:00 to 11-10 06:00 (60 min)", body)
        self.assertIn("primary power: 12.1 to 13.4 V over 59 readings", body)
        self.assertIn("last contact (newest data point): 2026-11-10 06:50:00 (10 min ago)", body)
        self.assertIn("dissolved oxygen", body)

    def test_all_ok_and_wqdata_error(self):
        now = dt.datetime(2026, 11, 10, 7, 0, tzinfo=EST_TZ)
        latest = [{"group_type": "Weather", "station_id": "22051538", "measurement_type": "Rain",
                   "recorded_at": "2026-11-10T06:50:00"}]
        freshness = assess_freshness(latest, now, env={})
        self.assertEqual(build_digest("2026-11-10", freshness, {}, [], None)[0], "WELL daily digest 2026-11-10: all OK")
        subject, body = build_digest("2026-11-10", freshness, {}, [], {"error": "HTTPError (HTTP 429)"})
        self.assertEqual(subject, "WELL daily digest 2026-11-10: 1 to check")
        self.assertIn("request failed: HTTPError (HTTP 429)", body)


class ReadGroupsTests(unittest.TestCase):
    def test_counts_gaps_and_findings_from_the_database(self):
        import daily_digest
        from server import create_app
        from db.database import db
        from db.models import SensorMeasurement
        app = create_app()
        with app.app_context():
            db.create_all()
            try:
                since, until = T0 - dt.timedelta(hours=24), T0
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
                groups, findings = daily_digest.read_groups(db, freshness, since, until)
            finally:
                db.drop_all()
        self.assertEqual(set(groups), {"Quality"})   # an all-excluded group isn't counted
        self.assertEqual((groups["Quality"]["rows"], groups["Quality"]["series"]), (12, 1))
        self.assertEqual(groups["Quality"]["gaps"], [(since, T0 - dt.timedelta(minutes=110))])
        self.assertEqual(len(findings), 2)   # about 0 mg/L, and stuck at exactly 0


class WqdataTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
