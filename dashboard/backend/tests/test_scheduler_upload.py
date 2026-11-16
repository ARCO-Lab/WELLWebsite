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
        no_sharepoint.update(BOREALIS_URL="https://borealisdata.ca", BOREALIS_API_TOKEN="t",   # the Borealis upload is on
                             BOREALIS_UPLOAD_PERSISTENT_ID="doi:10.5683/SP3/WELLUP")
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

    def without_borealis_upload(self, borealis_env, hours_utc=(7,)):
        """Run the hourly check at `hours_utc` of 2026-11-02 (7 is 02:00 Toronto time) with `borealis_env` as the only
        BOREALIS_* settings, SharePoint on; returns the mock of capture_job_error."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("BOREALIS_")}
        env.update(borealis_env, SHAREPOINT_TENANT_ID="t", SHAREPOINT_CLIENT_ID="c", SHAREPOINT_CLIENT_SECRET="s",
                   SHAREPOINT_SITE="https://x/sites/W")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(scheduler_temp, "capture_job_error") as captured:
            for hour in hours_utc:
                self.check(dt.datetime(2026, 11, 2, hour, tzinfo=dt.timezone.utc),
                           finished("Successfully uploaded x.csv to SharePoint (added)\n"))
        return captured

    def test_borealis_upload_off_is_skipped_quietly(self):
        # Turned off on purpose: no run, no ping, nothing to Sentry; SharePoint still goes up
        for borealis_env in ({"BOREALIS_UPLOAD": "off", "BOREALIS_URL": "https://borealisdata.ca",
                              "BOREALIS_API_TOKEN": "t"}, {}):
            self.scripts, self.pings, self.logs = [], [], []
            if os.path.exists(self.sharepoint_record):   # so SharePoint has the month to upload again
                os.remove(self.sharepoint_record)
            captured = self.without_borealis_upload(borealis_env)
            self.assertEqual(self.scripts, ["sharepoint_upload.py"], borealis_env)
            self.assertEqual(self.pings, [("sharepoint", "success")])
            captured.assert_not_called()
            self.assertFalse(any("[ERROR]" in line for line in self.logs), self.logs)

    def test_a_token_without_the_upload_doi_is_reported_once_a_day(self):
        # The DOI forgotten: one SettingsError naming it, a /fail ping, and SharePoint still goes up
        captured = self.without_borealis_upload({"BOREALIS_URL": "https://borealisdata.ca",
                                                 "BOREALIS_API_TOKEN": "t"}, hours_utc=range(24))
        self.assertEqual(self.scripts, ["sharepoint_upload.py"])
        self.assertEqual(self.pings, [("upload", "fail"), ("sharepoint", "success")])
        captured.assert_called_once()
        error = captured.call_args.args[0]
        self.assertIsInstance(error, SettingsError)
        self.assertIn("BOREALIS_UPLOAD_PERSISTENT_ID not set", str(error))
        self.assertIn("BOREALIS_UPLOAD=off", str(error))
        self.assertEqual(len([line for line in self.logs if "[ERROR]" in line]), 1)

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


# Monday 16 November 2026, 02:00 Toronto time (EST): days to the 15th, week 46 and October have ended
MONDAY_2AM = dt.datetime(2026, 11, 16, 7, tzinfo=dt.timezone.utc)
UPLOADED = finished("Successfully uploaded x.csv to SharePoint (added)\n")


class CadenceUploadTests(TestCase):
    """The SharePoint copy with SHAREPOINT_LAYOUT=cadence: days, weeks and months, each with its own record."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.records = {c: os.path.join(self.dir.name, f"sharepoint_{c}.json") for c in ("daily", "weekly", "monthly")}
        self.logs, self.cmds, self.timeouts, self.pings = [], [], [], []
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SHAREPOINT_", "BOREALIS_", "DEMO_"))}
        env.update(BOREALIS_UPLOAD="off", SHAREPOINT_TENANT_ID="t", SHAREPOINT_CLIENT_ID="c",
                   SHAREPOINT_CLIENT_SECRET="s", SHAREPOINT_SITE="https://x/sites/W", SHAREPOINT_LAYOUT="cadence",
                   SHAREPOINT_LIBRARY="Data Uploads")
        self.firsts = {"daily": "2026-11-13", "weekly": "2026-W45", "monthly": ""}
        for patch in (
            mock.patch.object(scheduler_temp, "sharepoint_period_records", self.records),
            mock.patch.object(scheduler_temp, "SHAREPOINT_FIRST_PERIODS", self.firsts),
            mock.patch.object(scheduler_temp, "SHAREPOINT_FIRST_MONTH", "2026-10"),
            mock.patch.object(scheduler_temp, "SHAREPOINT_FILES_PER_RUN", "40"),
            mock.patch.object(scheduler_temp, "sharepoint_uploaded_months_path", os.path.join(self.dir.name, "y.json")),
            mock.patch.object(scheduler_temp, "timestamped_print_upload", lambda *a: self.logs.append(" ".join(map(str, a)))),
            mock.patch.object(scheduler_temp, "ping_heartbeat",
                              lambda *a, **k: self.pings.append((*a, k.get("message")))),
            mock.patch.object(scheduler_temp, "capture_job_error"),
            mock.patch.dict(os.environ, env, clear=True),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def check(self, run, when_utc=MONDAY_2AM):
        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return when_utc.astimezone(tz)

        def recording(cmd, timeout):
            self.assertTrue(cmd[1].endswith("sharepoint_upload.py"))
            self.cmds.append(" ".join(cmd[2:]))
            self.timeouts.append(timeout)
            return run(cmd, timeout)

        with mock.patch.object(scheduler_temp, "datetime", Clock), mock.patch.object(scheduler_temp, "run_bounded", recording):
            scheduler_temp.monthly_upload_check()

    def recorded(self, cadence, field="uploaded"):
        return scheduler_temp.load_record(self.records[cadence], field)

    def test_each_ended_period_goes_up_with_its_own_record(self):
        self.check(UPLOADED)
        self.assertEqual(self.cmds, ["--day 2026-11-13", "--day 2026-11-14", "--day 2026-11-15",
                                     "--week 2026-W45", "--week 2026-W46", "--year 2026 --month 10",
                                     "--sampling all"])
        self.assertEqual(self.timeouts[:5], [scheduler_temp.PERIOD_TIMEOUT_S] * 5)
        self.assertEqual(self.timeouts[5], scheduler_temp.UPLOAD_TIMEOUT_S)
        # Days and weeks that ended less than 7 days ago go up but aren't recorded: more readings may come in
        self.assertEqual(self.recorded("daily"), set())
        self.assertEqual(self.recorded("weekly"), {"2026-W45"})
        self.assertEqual(self.recorded("monthly"), {"2026-10"})
        self.assertEqual(self.pings, [("sharepoint", "success",
                                       "daily: 0 uploaded, 3 recent refreshed; weekly: 1 uploaded, 1 recent "
                                       "refreshed; monthly: 1 uploaded; sampling: every month with readings is up to "
                                       "date")])
        # The next night uploads the recent ones again (an unchanged file isn't sent again) and the sampling months,
        # and it still pings: the check expects one a day
        self.cmds, self.pings = [], []
        self.check(UPLOADED)
        self.assertEqual(self.cmds, ["--day 2026-11-13", "--day 2026-11-14", "--day 2026-11-15", "--week 2026-W46",
                                     "--sampling all"])
        self.assertEqual(self.pings[0][:2], ("sharepoint", "success"))
        # A week later they have settled: uploaded once more, recorded, and not sent again
        self.cmds = []
        self.check(UPLOADED, when_utc=MONDAY_2AM + dt.timedelta(days=7))
        self.assertLessEqual({"2026-11-13", "2026-11-14", "2026-11-15"}, self.recorded("daily"))
        self.assertIn("2026-W46", self.recorded("weekly"))
        self.cmds = []
        self.check(UPLOADED, when_utc=MONDAY_2AM + dt.timedelta(days=8))
        self.assertNotIn("--day 2026-11-13", self.cmds)

    def test_a_day_whose_readings_change_is_replaced_the_next_night(self):
        # The script against a fake Graph: the day's file has more readings on the second night (late data)
        from tests.test_sharepoint import FakeGraph, make_client
        from utils import periods, sharepoint
        graph, outcomes, night = FakeGraph(library="Data Uploads"), [], {"rows": 1}
        client, _ = make_client(graph, SHAREPOINT_LAYOUT="cadence", SHAREPOINT_LIBRARY="Data Uploads")

        def run(cmd, timeout):
            day = periods.parse("daily", cmd[3])
            graph.received = b""   # the fake keeps one upload's bytes at a time
            content = "ID,Timestamp\n" + "".join(f"{i},{cmd[3]}T00:{i:02d}:00\n" for i in range(night["rows"]))
            outcome, _ = sharepoint.put_file(client, sharepoint.period_folder(client.config, day),
                                             periods.file_name(day), content, log=lambda *a: None)
            outcomes.append((cmd[3], outcome))
            return subprocess.CompletedProcess(cmd, 0, f"Successfully uploaded x.csv to SharePoint ({outcome})\n", "")
        self.firsts["daily"] = "2026-11-15"
        with mock.patch.dict(os.environ, {"SHAREPOINT_CADENCES": "daily"}):
            self.check(run)
            self.check(run, when_utc=MONDAY_2AM + dt.timedelta(days=1))   # nothing new: left as it is
            night["rows"] = 3
            self.check(run, when_utc=MONDAY_2AM + dt.timedelta(days=2))   # late readings: replaced
        self.assertEqual([outcome for day, outcome in outcomes if day == "2026-11-15"],
                         ["added", "unchanged", "replaced"])
        stored = graph.items["West Campus/Daily/2026/11/WELLWestCampus_2026-11-15.csv"]
        self.assertEqual(stored["size"], len("ID,Timestamp\n") + 3 * len("0,2026-11-15T00:00:00\n"))
        self.assertEqual(self.recorded("daily"), set())

    def test_a_backfill_goes_up_a_few_files_a_night_oldest_first(self):
        self.firsts["daily"] = "2026-11-01"
        with mock.patch.object(scheduler_temp, "SHAREPOINT_FILES_PER_RUN", "4"), \
                mock.patch.dict(os.environ, {"SHAREPOINT_CADENCES": "daily"}):
            self.check(UPLOADED)
            # Four of the settled days (1st to 8th), then the recent ones, which the limit doesn't count
            self.assertEqual(self.cmds, ["--day 2026-11-01", "--day 2026-11-02", "--day 2026-11-03", "--day 2026-11-04"]
                             + [f"--day 2026-11-{d:02d}" for d in range(9, 16)])
            self.assertEqual(self.pings, [("sharepoint", "success",
                                           "daily: 4 uploaded, 7 recent refreshed, 4 still to do")])
            self.cmds = []
            self.check(UPLOADED)
            self.assertEqual(self.cmds[0], "--day 2026-11-05")

    def test_a_day_without_readings_is_retried_for_a_week_then_recorded_as_empty(self):
        self.firsts["daily"] = "2026-11-07"
        with mock.patch.dict(os.environ, {"SHAREPOINT_CADENCES": "daily"}):
            self.check(finished("ERROR: No sensor data found\n", code=2))
        # The 7th and 8th ended 7 days or more ago; the 9th to the 15th may still be filled in
        self.assertEqual(self.recorded("daily", "empty"), {"2026-11-07", "2026-11-08"})
        self.assertEqual(self.recorded("daily"), set())
        self.assertEqual(self.pings, [("sharepoint", "success", "daily: 0 uploaded, 2 recorded empty")])
        scheduler_temp.capture_job_error.assert_not_called()

    def test_failures_stop_a_cadence_for_the_night_but_not_the_others(self):
        def run(cmd, timeout):
            if cmd[2] == "--day":
                raise subprocess.CalledProcessError(1, cmd, output="ERROR: Uploading: HTTP 500", stderr="")
            return UPLOADED(cmd, timeout)
        self.firsts["daily"] = "2026-11-01"
        self.check(run)
        self.assertIn("--sampling all", self.cmds)
        self.assertEqual([c for c in self.cmds if c.startswith("--day")], ["--day 2026-11-01", "--day 2026-11-02",
                                                                           "--day 2026-11-03"])
        self.assertEqual(self.recorded("weekly"), {"2026-W45"})
        self.assertEqual(self.pings[0][:2], ("sharepoint", "fail"))
        self.assertIn("daily: 0 uploaded, 3 failed, 8 still to do", self.pings[0][2])

    def test_a_night_stops_starting_files_at_its_time_limit(self):
        # Each file takes an hour on this clock: the 2.5 h budget fits three, and the third may only run until
        # PERIOD_TIMEOUT_S past the limit
        now = {"t": 0.0}

        def run(cmd, timeout):
            now["t"] += 3600
            return UPLOADED(cmd, timeout)
        self.firsts["daily"] = "2026-11-01"
        with mock.patch.object(scheduler_temp, "run_bounded", lambda cmd, timeout: (self.cmds.append(" ".join(cmd[2:])),
                                                                                    self.timeouts.append(timeout),
                                                                                    run(cmd, timeout))[2]), \
                mock.patch.object(scheduler_temp, "ping_heartbeat",
                                  lambda *a, **k: self.pings.append((*a, k.get("message")))):
            scheduler_temp.sharepoint_cadence_check(MONDAY_2AM.astimezone(scheduler_temp.SITE_TZ),
                                                    ["daily", "monthly", "sampling"], clock=lambda: now["t"])
        self.assertEqual(self.cmds, ["--day 2026-11-01", "--day 2026-11-02", "--day 2026-11-03"])
        budget, period = scheduler_temp.SHAREPOINT_NIGHT_BUDGET_S, scheduler_temp.PERIOD_TIMEOUT_S
        self.assertEqual(self.timeouts, [period, period, period])
        self.assertLessEqual(2 * 3600 + self.timeouts[-1], budget + period)
        self.assertEqual(self.pings, [("sharepoint", "success",
                                       "daily: 3 uploaded, 5 still to do, stopped at the time limit; "
                                       "monthly: 0 uploaded, 1 still to do, stopped at the time limit; "
                                       "sampling: not run tonight (time limit)")])
        # A month started near the limit gets only what is left of it, plus PERIOD_TIMEOUT_S
        self.assertEqual(scheduler_temp.budget_timeout(scheduler_temp.UPLOAD_TIMEOUT_S, 100.0, lambda: 40.0),
                         60 + period)
        # The upload run's stuck detection allows for Borealis and then a whole SharePoint night
        self.assertGreaterEqual(scheduler_temp.UPLOAD_RUN_MAX_S, scheduler_temp.UPLOAD_TIMEOUT_S + budget + period)

    def test_the_spring_forward_night_runs_at_three(self):
        # 14 March 2027: clocks go from 02:00 to 03:00 EDT, so there is no 02:00 run; 03:00 EDT is 07:00 UTC
        with mock.patch.dict(os.environ, {"SHAREPOINT_CADENCES": "daily"}):
            self.firsts["daily"] = "2027-03-13"
            self.check(UPLOADED, when_utc=dt.datetime(2027, 3, 14, 7, tzinfo=dt.timezone.utc))
            self.assertEqual(self.cmds, ["--day 2027-03-13"])
            self.assertEqual(self.pings[0][:2], ("sharepoint", "success"))
            # On other days 03:00 is not the upload hour
            self.cmds = []
            self.check(UPLOADED, when_utc=dt.datetime(2027, 3, 15, 7, tzinfo=dt.timezone.utc))
            self.assertEqual(self.cmds, [])
        at_three = dt.datetime(2027, 3, 14, 3, tzinfo=scheduler_temp.SITE_TZ)
        self.assertTrue(scheduler_temp.upload_slot(at_three))
        self.assertFalse(scheduler_temp.upload_slot(at_three.replace(day=21)))

    def test_only_the_chosen_cadences_run(self):
        with mock.patch.dict(os.environ, {"SHAREPOINT_CADENCES": "weekly"}):
            self.check(UPLOADED)
        self.assertEqual(self.cmds, ["--week 2026-W45", "--week 2026-W46"])

    def test_sampling_without_readings_is_not_a_failure_but_a_failed_run_is(self):
        with mock.patch.dict(os.environ, {"SHAREPOINT_CADENCES": "sampling"}):
            self.check(finished("ERROR: No sampling readings found (all); nothing uploaded.\n", code=2))
            self.assertEqual(self.pings, [("sharepoint", "success", "sampling: no readings yet")])
            self.pings = []
            self.check(finished("ERROR: 1 sampling file(s) didn't go up to SharePoint\n", code=1))
            self.assertEqual(self.pings, [("sharepoint", "fail", "sampling: failed")])
        self.assertEqual(self.timeouts, [scheduler_temp.SAMPLING_TIMEOUT_S] * 2)

    def test_bad_settings_fail_the_check_without_uploading(self):
        for env in ({"SHAREPOINT_CADENCES": "hourly"}, {"SHAREPOINT_LAYOUT": "flat"}):
            self.pings = []
            with self.subTest(env), mock.patch.dict(os.environ, env):
                self.check(UPLOADED)
                self.assertEqual(self.cmds, [])
                self.assertEqual(self.pings, [("sharepoint", "fail", None)])
        self.pings = []
        with mock.patch.object(scheduler_temp, "SHAREPOINT_FILES_PER_RUN", "0"):
            self.check(UPLOADED)
        self.assertEqual(self.cmds, [])
        self.assertEqual(self.pings[0][:2], ("sharepoint", "fail"))

    def test_a_bad_first_day_stops_only_the_daily_files(self):
        self.firsts["daily"] = "14/11/2026"
        self.check(UPLOADED)
        self.assertFalse([c for c in self.cmds if c.startswith("--day")])
        self.assertIn("--week 2026-W46", self.cmds)
        self.assertEqual(self.pings[0][:2], ("sharepoint", "fail"))
        self.assertTrue(any("SHAREPOINT_DAILY_FIRST_DAY" in line for line in self.logs))

    def test_the_year_layout_is_unchanged(self):
        with mock.patch.dict(os.environ, {"SHAREPOINT_LAYOUT": ""}):
            self.check(UPLOADED, when_utc=dt.datetime(2026, 11, 1, 7, tzinfo=dt.timezone.utc))
        self.assertEqual(self.cmds, ["--year 2026 --month 10"])
        self.assertFalse(any(os.path.exists(path) for path in self.records.values()))
        self.assertEqual(self.pings, [("sharepoint", "success", None)])


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
