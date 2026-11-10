"""Tests for utils/jobs.py (the worker scheduler's helpers). Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import subprocess
import sys
import threading
import time
import unittest

import schedule

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.jobs import download_status, run_bounded, run_in_background  # noqa: E402


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
        for _ in range(50):  # the kernel may need a moment to reap it
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail(f"child process {child_pid} outlived the timeout")


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


if __name__ == "__main__":
    unittest.main()
