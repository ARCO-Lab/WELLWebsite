"""Tests for utils/jobs.py (the worker scheduler's helpers). Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import schedule

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.jobs import (  # noqa: E402
    download_status, load_uploaded_months, months_due_for_upload, parse_month_key, record_uploaded_month, run_bounded,
    run_in_background,
)


class RunInBackgroundTests(unittest.TestCase):
    def test_a_run_still_going_is_skipped_not_overlapped(self):
        release, started, logs, runs = threading.Event(), threading.Event(), [], []

        def slow():
            runs.append(1)
            started.set()
            release.wait(5)

        start = run_in_background(slow, log=logs.append)
        first = start()
        self.assertTrue(started.wait(5))
        self.assertIsNone(start())  # previous run still going
        self.assertEqual(len(runs), 1)
        self.assertIn("still running", logs[0])
        release.set()
        first.join(5)
        second = start()  # free again once the first finished
        self.assertIsNotNone(second)
        second.join(5)
        self.assertEqual(len(runs), 2)

    def test_each_skip_is_reported_with_the_number_in_a_row(self):
        release, started, skips = threading.Event(), threading.Event(), []

        def slow():
            started.set()
            release.wait(5)

        def broken_report(n, message):
            skips.append((n, message))
            raise RuntimeError("heartbeat down")   # a failing report must not stop the scheduler loop

        logs = []
        start = run_in_background(slow, log=logs.append, name="backup", on_skip=broken_report)
        first = start()
        self.assertTrue(started.wait(5))
        self.assertIsNone(start())
        self.assertIsNone(start())
        self.assertEqual([n for n, _ in skips], [1, 2])
        self.assertIn("backup is still running", skips[0][1])
        self.assertTrue(any("reporting the skipped backup run failed" in line for line in logs), logs)
        release.set()
        first.join(5)
        started.clear()
        release.clear()
        second = start()   # a run that starts resets the count
        self.assertTrue(started.wait(5))
        self.assertIsNone(start())
        self.assertEqual(skips[-1][0], 1)
        release.set()
        second.join(5)

    def test_a_failing_run_is_logged_and_frees_the_job(self):
        logs = []

        def boom():
            raise RuntimeError("vendor down")

        start = run_in_background(boom, log=logs.append)
        start().join(5)
        self.assertTrue(any("failed: vendor down" in line for line in logs))
        t = start()
        self.assertIsNotNone(t)  # the lock was released
        t.join(5)

    def test_scheduler_runs_a_due_job_once_even_while_it_is_still_running(self):
        """The old worker polled one scheduler from three threads, and a job's next run only moved
        once the job returned, so a slow job started twice. The wrapper returns at once instead."""
        started, finished, release, runs = threading.Event(), threading.Event(), threading.Event(), []

        def slow():
            runs.append(1)
            started.set()
            release.wait(5)
            finished.set()

        scheduler = schedule.Scheduler()
        job = scheduler.every(10).minutes.do(run_in_background(slow, log=lambda *_: None))
        try:
            job.next_run = dt.datetime.now() - dt.timedelta(seconds=1)
            scheduler.run_pending()  # must return while slow() is still blocked
            self.assertTrue(started.wait(5))
            self.assertFalse(finished.is_set(), "the job ran inline instead of in its own thread")
            scheduler.run_pending()  # same moment, e.g. a second poller
            self.assertEqual(len(runs), 1)
            self.assertGreater(job.next_run, dt.datetime.now())
        finally:
            release.set()


class RunBoundedTests(unittest.TestCase):
    def test_returns_output_on_success(self):
        r = run_bounded([sys.executable, "-c", "print('ok')"], timeout=30)
        self.assertEqual(r.stdout.strip(), "ok")

    def test_raises_on_failure_with_output(self):
        with self.assertRaises(subprocess.CalledProcessError) as ctx:
            run_bounded([sys.executable, "-c", "import sys; print('boom'); sys.exit(3)"], timeout=30)
        self.assertEqual(ctx.exception.returncode, 3)
        self.assertIn("boom", ctx.exception.stdout)

    @unittest.skipUnless(hasattr(os, "killpg"), "process groups are POSIX-only; the worker runs on Linux")
    def test_timeout_also_stops_what_the_command_started(self):
        """download_data.py runs inject_sampling.py; a timeout must stop both."""
        script = "; ".join([
            "import subprocess, sys, time",
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])",
            "print(child.pid, flush=True)",
            "time.sleep(60)",
        ])
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired) as ctx:
            run_bounded([sys.executable, "-c", script], timeout=2, grace=2)
        self.assertLess(time.monotonic() - started, 30)
        child_pid = int(ctx.exception.output.split()[0])
        for _ in range(50):  # give the kernel a moment
            if not _running(child_pid):
                break
            time.sleep(0.1)
        else:
            self.fail(f"child process {child_pid} outlived the timeout")


def _running(pid):
    """True while pid is a live process. A zombie (killed, not yet reaped, e.g. re-parented to a PID 1 that
    doesn't reap, as in a container) has stopped running, so it counts as gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as f:
            state = f.read().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return state not in ("Z", "X")


class DownloadStatusTests(unittest.TestCase):
    def test_reads_the_last_status_line(self):
        out = "DEBUG: Starting process...\nOUTPUT: PROCESSED_2_FILES\n"
        self.assertEqual(download_status(out), "PROCESSED_2_FILES")

    def test_no_new_files_is_a_status_not_a_path(self):
        self.assertEqual(download_status("DEBUG: All files have been processed.\nOUTPUT: NO_NEW_FILES\n"), "NO_NEW_FILES")

    def test_missing_status(self):
        self.assertIsNone(download_status("No files to process. Use --list-files to debug available files.\n"))
        self.assertIsNone(download_status(""))
        self.assertIsNone(download_status(None))

    def test_ignores_output_text_inside_other_lines(self):
        self.assertIsNone(download_status("inject_sampling.py stdout: something OUTPUT: x\n"))


def toronto():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Toronto")
    except Exception:
        raise unittest.SkipTest("no time zone database on this machine")


def utc(*args):
    return dt.datetime(*args, tzinfo=dt.timezone.utc)


class MonthlyUploadTests(unittest.TestCase):
    def due(self, when_utc, uploaded=(), first=(2026, 10)):
        return months_due_for_upload(when_utc.astimezone(toronto()), set(uploaded), first)

    def test_uploads_last_month_at_2am_toronto_on_the_1st(self):
        self.assertEqual(self.due(utc(2026, 11, 1, 7, 0)), [(2026, 10)])  # 02:00 EST
        self.assertEqual(self.due(utc(2027, 7, 1, 6, 0), uploaded=[f"2026-{m}" for m in ("10", "11", "12")]
                                  + [f"2027-0{m}" for m in range(1, 6)]), [(2027, 6)])  # 02:00 EDT

    def test_not_at_2am_utc_when_toronto_is_still_in_the_old_month(self):
        """02:00 UTC on the 1st is 21:00/22:00 Toronto on the last day: the month's last hours aren't over."""
        self.assertEqual(self.due(utc(2026, 11, 1, 2, 0)), [])
        self.assertEqual(self.due(utc(2026, 12, 1, 2, 0), uploaded={"2026-10"}), [])

    def test_only_in_the_2am_hour(self):
        self.assertEqual(self.due(utc(2026, 11, 1, 6, 0)), [])  # 01:00 EST
        self.assertEqual(self.due(utc(2026, 11, 1, 8, 0)), [])  # 03:00 EST

    def test_a_missed_or_failed_upload_is_tried_again_the_next_days(self):
        self.assertEqual(self.due(utc(2026, 11, 2, 7, 0)), [(2026, 10)])
        self.assertEqual(self.due(utc(2026, 11, 20, 7, 0)), [(2026, 10)])

    def test_a_month_still_failing_on_the_next_1st_is_kept_oldest_first(self):
        self.assertEqual(self.due(utc(2026, 12, 1, 7, 0)), [(2026, 10), (2026, 11)])
        self.assertEqual(self.due(utc(2027, 2, 1, 7, 0), uploaded={"2026-11"}), [(2026, 10), (2026, 12), (2027, 1)])

    def test_an_uploaded_month_is_not_sent_again(self):
        self.assertEqual(self.due(utc(2026, 11, 1, 7, 0), uploaded={"2026-10"}), [])
        self.assertEqual(self.due(utc(2026, 11, 2, 7, 0), uploaded={"2026-10"}), [])

    def test_months_before_the_first_month_are_never_sent(self):
        self.assertEqual(self.due(utc(2026, 11, 1, 7, 0), first=(2026, 11)), [])
        self.assertEqual(self.due(utc(2026, 12, 1, 7, 0), first=(2026, 11)), [(2026, 11)])

    def test_january_uploads_december_of_the_year_before(self):
        self.assertEqual(self.due(utc(2027, 1, 1, 7, 0), first=(2026, 12)), [(2026, 12)])

    def test_parse_month_key(self):
        self.assertEqual(parse_month_key("2026-10"), (2026, 10))
        self.assertEqual(parse_month_key(" 2027-01\n"), (2027, 1))
        for bad in ("2026-13", "2026-1", "Oct 2026", "", None):
            with self.assertRaises(ValueError):
                parse_month_key(bad)

    def test_record_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "uploaded_months.json")
            self.assertEqual(load_uploaded_months(path), set())  # no file yet
            record_uploaded_month(path, 2026, 10)
            record_uploaded_month(path, 2026, 11)
            record_uploaded_month(path, 2026, 10)
            self.assertEqual(load_uploaded_months(path), {"2026-10", "2026-11"})
            self.assertEqual(os.listdir(d), ["uploaded_months.json"])  # no temp file left behind

    def test_a_damaged_record_raises_instead_of_reading_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "uploaded_months.json")
            with open(path, "w") as f:
                f.write('{"uploaded_mon')
            with self.assertRaises(ValueError):
                load_uploaded_months(path)


if __name__ == "__main__":
    unittest.main()
