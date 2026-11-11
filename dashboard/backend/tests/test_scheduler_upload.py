"""The scheduler's monthly Borealis upload check. Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
# The real module needs the database; the upload check doesn't use it.
sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
import scheduler_temp  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    ZoneInfo("America/Toronto")
except Exception:  # pragma: no cover
    raise unittest.SkipTest("no time zone database on this machine")


def finished(stdout, code=0):
    def run(cmd, timeout):
        if code:
            raise subprocess.CalledProcessError(code, cmd, output=stdout, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout, "")
    return run


class MonthlyUploadCheckTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.record = os.path.join(self.dir.name, "uploaded_months.json")
        self.logs, self.cmds = [], []
        for patch in (
            mock.patch.object(scheduler_temp, "uploaded_months_path", self.record),
            mock.patch.object(scheduler_temp, "UPLOAD_FIRST_MONTH", "2026-10"),
            mock.patch.object(scheduler_temp, "timestamped_print_upload", lambda *a: self.logs.append(" ".join(map(str, a)))),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def check(self, when_utc, run):
        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return when_utc.astimezone(tz)

        def recording(cmd, timeout):
            self.cmds.append(cmd[-3:])
            return run(cmd, timeout)

        with mock.patch.object(scheduler_temp, "datetime", Clock), mock.patch.object(scheduler_temp, "run_bounded", recording):
            scheduler_temp.monthly_upload_check()

    def recorded(self):
        return scheduler_temp.load_uploaded_months(self.record)

    def test_a_successful_upload_is_recorded(self):
        self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), finished("Successfully uploaded WELLWestCampus_Oct2026.csv to Borealis\n"))
        self.assertEqual(self.cmds, [["2026", "--month", "10"]])
        self.assertEqual(self.recorded(), {"2026-10"})

    def test_an_empty_month_is_not_recorded(self):
        self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), finished("ERROR: No sensor data found\n", code=2))
        self.assertEqual(self.recorded(), set())

    def test_exit_0_without_an_upload_is_not_recorded(self):
        self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), finished("DEBUG: Export process completed!\n"))
        self.assertEqual(self.recorded(), set())
        self.assertTrue(any("didn't report an upload" in line for line in self.logs))

    def test_a_month_still_failing_does_not_hold_up_the_next(self):
        def run(cmd, timeout):
            if cmd[-1] == "10":
                raise subprocess.CalledProcessError(1, cmd, output="Error uploading to Borealis: HTTPError", stderr="")
            return subprocess.CompletedProcess(cmd, 0, "Successfully uploaded x.csv to Borealis\n", "")
        self.check(dt.datetime(2026, 12, 1, 7, tzinfo=dt.timezone.utc), run)
        self.assertEqual(self.cmds, [["2026", "--month", "10"], ["2026", "--month", "11"]])
        self.assertEqual(self.recorded(), {"2026-11"})

    def test_an_unreadable_record_is_logged_only_in_the_upload_hour(self):
        with open(self.record, "w") as f:
            f.write("{not json")
        for hour in range(24):  # every hourly check of a day, Toronto time = UTC-5 in November
            self.check(dt.datetime(2026, 11, 2, hour, tzinfo=dt.timezone.utc), finished("Successfully uploaded"))
        self.assertEqual(self.cmds, [])
        self.assertEqual(len([line for line in self.logs if "[ERROR]" in line]), 1)

    def test_nothing_runs_outside_the_upload_hour(self):
        self.check(dt.datetime(2026, 11, 1, 2, tzinfo=dt.timezone.utc), finished("Successfully uploaded"))
        self.assertEqual(self.cmds, [])
        self.assertEqual(self.logs, [])


if __name__ == "__main__":
    unittest.main()
