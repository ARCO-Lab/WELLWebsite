"""Heartbeat pings (utils/heartbeat.py) and where the scheduler sends them.
Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import pathlib
import subprocess
import sys
import types
from unittest import TestCase, main, mock

import requests

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))

from utils.heartbeat import HEARTBEAT_TIMEOUT_S, ping_heartbeat  # noqa: E402
import scheduler_temp  # noqa: E402

URL = "https://hc-ping.example/0000-test"


class FakeGet:
    def __init__(self, status=200, error=None):
        self.calls, self.status, self.error = [], status, error

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        if self.error:
            raise self.error
        return types.SimpleNamespace(status_code=self.status)


class PingHeartbeatTests(TestCase):
    def test_unset_is_a_no_op(self):
        get = FakeGet()
        self.assertFalse(ping_heartbeat("ingestion", env={}, get=get))
        self.assertFalse(ping_heartbeat("ingestion", env={"HEALTHCHECK_URL_INGESTION": "  "}, get=get))
        self.assertEqual(get.calls, [])

    def test_success_fail_and_start(self):
        get = FakeGet()
        env = {"HEALTHCHECK_URL_UPLOAD": URL + "/"}
        self.assertTrue(ping_heartbeat("upload", env=env, get=get))
        self.assertTrue(ping_heartbeat("upload", "fail", env=env, get=get))
        self.assertTrue(ping_heartbeat("upload", "start", env=env, get=get))
        self.assertEqual([c[0] for c in get.calls], [URL, URL + "/fail", URL + "/start"])
        self.assertTrue(all(timeout == HEARTBEAT_TIMEOUT_S for _, timeout in get.calls))

    def test_unknown_status_is_never_reported_as_success(self):
        get = FakeGet()
        ping_heartbeat("backup", "maybe", env={"HEALTHCHECK_URL_BACKUP": URL}, get=get)
        self.assertEqual(get.calls[0][0], URL + "/fail")

    def test_timeouts_and_errors_never_raise(self):
        env = {"HEALTHCHECK_URL_INGESTION": URL}
        for error in (requests.exceptions.Timeout("slow"), requests.exceptions.ConnectionError("down"), ValueError()):
            get = FakeGet(error=error)
            self.assertFalse(ping_heartbeat("ingestion", env=env, get=get))
        self.assertFalse(ping_heartbeat("ingestion", env=env, get=FakeGet(status=404)))

    def test_short_timeout_goes_to_requests(self):
        with mock.patch("utils.heartbeat.requests.get", side_effect=requests.exceptions.Timeout()) as get:
            self.assertFalse(ping_heartbeat("ingestion", env={"HEALTHCHECK_URL_INGESTION": URL}, timeout=2))
        get.assert_called_once_with(URL, timeout=2)


class SchedulerHeartbeatTests(TestCase):
    def setUp(self):
        self.pings = []
        for patch in (
            mock.patch.object(scheduler_temp, "ping_heartbeat", lambda name, status: self.pings.append((name, status))),
            mock.patch.object(scheduler_temp, "print", lambda *a, **k: None, create=True),
            mock.patch.object(scheduler_temp, "timestamped_print_upload", lambda *a: None),
            mock.patch.object(scheduler_temp, "timestamped_print_digest", lambda *a: None),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def at(self, hour):
        when = dt.datetime(2026, 11, 1, hour, 0, tzinfo=scheduler_temp.SITE_TZ)

        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return when.astimezone(tz)
        return mock.patch.object(scheduler_temp, "datetime", Clock)

    def test_ingestion_success_and_failure(self):
        with mock.patch.object(scheduler_temp, "alert_check_job") as alerts:
            with mock.patch.object(scheduler_temp, "inject_all_new_data", lambda: None):
                scheduler_temp.api_injection_job()
            with mock.patch.object(scheduler_temp, "inject_all_new_data", side_effect=RuntimeError("ingestion failed for: WQData")):
                scheduler_temp.api_injection_job()
        self.assertEqual(self.pings, [("ingestion", "success"), ("ingestion", "fail")])
        self.assertEqual(alerts.call_count, 2)   # the alert check runs after failed runs too

    def test_alert_check_pings_and_never_raises(self):
        app = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"inject_from_api": types.SimpleNamespace(app=app)}),                 mock.patch.object(scheduler_temp, "timestamped_print_alerts", lambda *a: None),                 mock.patch.object(scheduler_temp, "capture_job_error") as captured:
            for result in ({"email": "sent"}, {"email": None}, {"email": "failed"}, RuntimeError("database down")):
                with mock.patch.object(scheduler_temp.check_alerts, "run", side_effect=[result]):
                    scheduler_temp.alert_check_job()
        self.assertEqual(self.pings, [("alerts", "success"), ("alerts", "success"), ("alerts", "fail"),
                                      ("alerts", "fail")])
        self.assertEqual(captured.call_count, 1)   # only the crash goes to Sentry

    def test_upload_pings_only_when_a_month_was_due(self):
        with self.at(2), mock.patch.object(scheduler_temp, "load_uploaded_months", lambda p: set()), \
                mock.patch.object(scheduler_temp, "UPLOAD_FIRST_MONTH", "2026-10"), \
                mock.patch.object(scheduler_temp, "upload_job", lambda *a: True), \
                mock.patch.object(scheduler_temp, "record_uploaded_month", lambda *a: None):
            scheduler_temp.monthly_upload_check()
        with self.at(2), mock.patch.object(scheduler_temp, "load_uploaded_months", lambda p: set()), \
                mock.patch.object(scheduler_temp, "UPLOAD_FIRST_MONTH", "2026-10"), \
                mock.patch.object(scheduler_temp, "upload_job", lambda *a: False):
            scheduler_temp.monthly_upload_check()
        with self.at(2), mock.patch.object(scheduler_temp, "load_uploaded_months", lambda p: {"2026-10"}), \
                mock.patch.object(scheduler_temp, "UPLOAD_FIRST_MONTH", "2026-10"):
            scheduler_temp.monthly_upload_check()   # nothing due: no ping
        self.assertEqual(self.pings, [("upload", "success"), ("upload", "fail")])

    def test_digest_runs_at_its_hour_and_pings(self):
        ran = []
        ok = lambda cmd, timeout: ran.append(cmd) or subprocess.CompletedProcess(cmd, 0, "sent", "")  # noqa: E731

        def failing(cmd, timeout):
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="boom")

        with mock.patch.object(scheduler_temp, "DIGEST_HOUR", "7"), mock.patch.object(scheduler_temp, "run_bounded", ok):
            with self.at(6):
                scheduler_temp.daily_digest_check()
            with self.at(7):
                scheduler_temp.daily_digest_check()
        with mock.patch.object(scheduler_temp, "DIGEST_HOUR", "7"), mock.patch.object(scheduler_temp, "run_bounded", failing), self.at(7):
            scheduler_temp.daily_digest_check()
        with mock.patch.object(scheduler_temp, "DIGEST_HOUR", "seven"), mock.patch.object(scheduler_temp, "run_bounded", ok), self.at(7):
            scheduler_temp.daily_digest_check()   # a bad DIGEST_HOUR never runs, never raises
        for dst_hour in ("1", "2"):   # clocks change at 02:00, so these hours are refused
            with mock.patch.object(scheduler_temp, "DIGEST_HOUR", dst_hour), \
                    mock.patch.object(scheduler_temp, "run_bounded", ok), self.at(int(dst_hour)):
                scheduler_temp.daily_digest_check()
        self.assertEqual(len(ran), 1)
        self.assertTrue(ran[0][-1].endswith("daily_digest.py"))
        self.assertEqual(self.pings, [("digest", "success"), ("digest", "fail")])


if __name__ == "__main__":
    main()
