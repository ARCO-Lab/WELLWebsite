"""The scheduler's monthly Borealis upload check. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import subprocess
import sys
import tempfile
import types
from unittest import SkipTest, TestCase, main, mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
# The real module needs the database; the upload check doesn't use it.
sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
import scheduler_temp  # noqa: E402
from utils.jobs import SettingsError, settings_error  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    ZoneInfo("America/Toronto")
except Exception:  # pragma: no cover
    raise SkipTest("no time zone database on this machine")


def finished(stdout, code=0):
    def run(cmd, timeout):
        if code:
            raise subprocess.CalledProcessError(code, cmd, output=stdout, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout, "")
    return run


class MonthlyUploadCheckTests(TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.record = os.path.join(self.dir.name, "uploaded_months.json")
        self.sharepoint_record = os.path.join(self.dir.name, "sharepoint_uploaded_months.json")
        self.logs, self.cmds, self.pings = [], [], []
        no_sharepoint = {k: v for k, v in os.environ.items() if not k.startswith(("SHAREPOINT_", "BOREALIS_", "DEMO_"))}
        no_sharepoint["BOREALIS_UPLOAD_PERSISTENT_ID"] = "doi:10.5683/SP3/WELLUP"   # the Borealis upload is on
        for patch in (
            mock.patch.object(scheduler_temp, "uploaded_months_path", self.record),
            mock.patch.object(scheduler_temp, "UPLOAD_FIRST_MONTH", "2026-10"),
            mock.patch.object(scheduler_temp, "sharepoint_uploaded_months_path", self.sharepoint_record),
            mock.patch.object(scheduler_temp, "SHAREPOINT_FIRST_MONTH", "2026-10"),
            mock.patch.object(scheduler_temp, "timestamped_print_upload", lambda *a: self.logs.append(" ".join(map(str, a)))),
            mock.patch.object(scheduler_temp, "ping_heartbeat", lambda *a: self.pings.append(a)),
            mock.patch.dict(os.environ, no_sharepoint, clear=True),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    scripts = None

    def check(self, when_utc, run):
        self.scripts = self.scripts if self.scripts is not None else []
        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return when_utc.astimezone(tz)

        def recording(cmd, timeout):
            self.cmds.append(cmd[-3:])
            self.scripts.append(os.path.basename(cmd[1]))
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

    def test_a_record_that_cant_be_written_pings_fail(self):
        # The month went up, but logs/ is full or read-only: the run must still reach someone
        with mock.patch.object(scheduler_temp, "record_uploaded_month", side_effect=OSError(28, "No space left")), \
                mock.patch.object(scheduler_temp, "capture_job_error") as captured:
            self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), finished("Successfully uploaded x.csv\n"))
        self.assertEqual(self.pings, [("upload", "fail")])
        captured.assert_called_once()
        self.assertTrue(any("recording it in" in line and "No space left" in line for line in self.logs), self.logs)
        self.assertEqual(self.recorded(), set())

    def test_nothing_runs_outside_the_upload_hour(self):
        self.check(dt.datetime(2026, 11, 1, 2, tzinfo=dt.timezone.utc), finished("Successfully uploaded"))
        self.assertEqual(self.cmds, [])
        self.assertEqual(self.logs, [])


    def test_sharepoint_is_off_without_its_settings(self):
        self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), finished("Successfully uploaded x to Borealis\n"))
        self.assertEqual(self.scripts, ["upload_data.py"])
        self.assertEqual(self.pings, [("upload", "success")])

    def test_sharepoint_runs_after_borealis_with_its_own_record(self):
        def run(cmd, timeout):
            if cmd[1].endswith("upload_data.py"):   # Borealis fails; the SharePoint copy still goes up
                raise subprocess.CalledProcessError(1, cmd, output="ERROR: HTTP 401", stderr="")
            return subprocess.CompletedProcess(cmd, 0, "Successfully uploaded x.csv to SharePoint (added)\n", "")
        with mock.patch.dict(os.environ, {"SHAREPOINT_TENANT_ID": "t", "SHAREPOINT_CLIENT_ID": "c",
                                          "SHAREPOINT_CLIENT_SECRET": "s", "SHAREPOINT_SITE": "https://x/sites/W"}):
            self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), run)
        self.assertEqual(self.scripts, ["upload_data.py", "sharepoint_upload.py"])
        self.assertEqual(self.recorded(), set())
        self.assertEqual(scheduler_temp.load_uploaded_months(self.sharepoint_record), {"2026-10"})
        self.assertEqual(self.pings, [("upload", "fail"), ("sharepoint", "success")])

    def test_incomplete_sharepoint_settings_are_reported_once_a_day(self):
        with mock.patch.dict(os.environ, {"SHAREPOINT_SITE": "https://x/sites/W"}):
            for hour in range(24):
                self.check(dt.datetime(2026, 11, 2, hour, tzinfo=dt.timezone.utc), finished("Successfully uploaded"))
        errors = [line for line in self.logs if "[ERROR]" in line]
        self.assertEqual(len(errors), 1)
        self.assertIn("SHAREPOINT_TENANT_ID", errors[0])
        self.assertEqual(self.pings, [("upload", "success"), ("sharepoint", "fail")])

    def test_a_settings_problem_is_reported_as_its_own_message(self):
        # upload_data.py exits SETTINGS_ERROR_EXIT with an ERROR: line saying what to fix (here the token)
        line = ("ERROR: Borealis token rejected (HTTP 401): make a new token on https://borealisdata.ca (your name > "
                "API Token) and put it in BOREALIS_API_TOKEN.")
        with mock.patch.object(scheduler_temp, "capture_job_error") as captured:
            self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc),
                       finished(f"Exporting sensor data\n{line}\n", code=scheduler_temp.SETTINGS_ERROR_EXIT))
        captured.assert_called_once()
        error = captured.call_args.args[0]
        self.assertIsInstance(error, SettingsError)
        self.assertNotIsInstance(error, subprocess.CalledProcessError)
        self.assertEqual(str(error), line[len("ERROR: "):])
        self.assertTrue(any("[ERROR] upload_data.py stopped: Borealis token rejected (HTTP 401)" in entry
                            for entry in self.logs), self.logs)
        self.assertEqual(self.pings, [("upload", "fail")])
        self.assertEqual(self.recorded(), set())

    def test_other_failures_are_still_reported_as_the_failed_command(self):
        with mock.patch.object(scheduler_temp, "capture_job_error") as captured:
            self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc),
                       finished("ERROR: Uploading x.csv to Borealis: publish failed (HTTP 503)\n", code=1))
        self.assertIsInstance(captured.call_args.args[0], subprocess.CalledProcessError)

    def test_without_an_upload_dataset_borealis_is_skipped_quietly(self):
        # Borealis deliberately not set up: no run, no ping, nothing to Sentry; SharePoint still goes up
        env = {"BOREALIS_UPLOAD_PERSISTENT_ID": "", "SHAREPOINT_TENANT_ID": "t", "SHAREPOINT_CLIENT_ID": "c",
               "SHAREPOINT_CLIENT_SECRET": "s", "SHAREPOINT_SITE": "https://x/sites/W"}
        with mock.patch.dict(os.environ, env), mock.patch.object(scheduler_temp, "capture_job_error") as captured:
            self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc),
                       finished("Successfully uploaded x.csv to SharePoint (added)\n"))
        self.assertEqual(self.scripts, ["sharepoint_upload.py"])
        self.assertEqual(self.pings, [("sharepoint", "success")])
        captured.assert_not_called()
        self.assertFalse(any("[ERROR]" in line for line in self.logs), self.logs)

    def test_a_borealis_settings_problem_doesnt_stop_sharepoint(self):
        def run(cmd, timeout):
            if cmd[1].endswith("upload_data.py"):
                raise subprocess.CalledProcessError(scheduler_temp.SETTINGS_ERROR_EXIT, cmd, stderr="",
                                                    output="ERROR: Not uploading to Borealis: BOREALIS_URL not set\n")
            return subprocess.CompletedProcess(cmd, 0, "Successfully uploaded x.csv to SharePoint (added)\n", "")
        with mock.patch.dict(os.environ, {"SHAREPOINT_TENANT_ID": "t", "SHAREPOINT_CLIENT_ID": "c",
                                          "SHAREPOINT_CLIENT_SECRET": "s", "SHAREPOINT_SITE": "https://x/sites/W"}), \
                mock.patch.object(scheduler_temp, "capture_job_error"):
            self.check(dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc), run)
        self.assertEqual(self.scripts, ["upload_data.py", "sharepoint_upload.py"])
        self.assertEqual(self.pings, [("upload", "fail"), ("sharepoint", "success")])


class SettingsErrorTests(TestCase):
    def test_the_last_error_line_is_the_message(self):
        exc = subprocess.CalledProcessError(3, ["python", "scripts/upload_data.py"], stderr="",
                                            output="ERROR: first\nprogress\nERROR: what to fix\n")
        self.assertEqual(str(settings_error(exc)), "what to fix")

    def test_without_an_error_line_it_names_the_script(self):
        exc = subprocess.CalledProcessError(3, ["python", "scripts/upload_data.py"], output=None, stderr="")
        self.assertIn("upload_data.py", str(settings_error(exc)))


if __name__ == "__main__":
    main()
