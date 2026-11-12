"""The worker's shutdown on SIGTERM (scripts/scheduler_temp.py shut_down, utils/jobs.py stop_subprocesses): running
jobs get time to finish, then their subprocesses are stopped and nothing new starts.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))

import scheduler_temp  # noqa: E402
from utils import jobs  # noqa: E402
from utils.jobs import run_bounded, run_in_background, stop_subprocesses  # noqa: E402


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.addCleanup(jobs._stopping.clear)   # stop_subprocesses sets it for the whole process

    def wait_until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.05)
        return condition()

    def test_a_job_that_finishes_in_time_is_waited_for(self):
        done = threading.Event()

        def quick():
            time.sleep(0.5)
            done.set()

        run = run_in_background(quick, log=self.logs.append)
        run()
        left = scheduler_temp.shut_down([run], self.logs.append, wait_s=5, grace_s=1, final_wait_s=1)
        self.assertEqual(left, [])
        self.assertTrue(done.is_set())
        self.assertIn("[shutdown] Waiting up to 5 s for: quick", self.logs)
        self.assertEqual(self.logs[-1], "[shutdown] Exiting")

    def test_nothing_running_exits_at_once(self):
        run = run_in_background(lambda: None, log=self.logs.append, name="idle")
        started = time.monotonic()
        self.assertEqual(scheduler_temp.shut_down([run], self.logs.append, wait_s=5), [])
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.logs, ["[shutdown] Exiting"])

    @unittest.skipUnless(hasattr(os, "killpg"), "process groups are POSIX-only; the worker runs on Linux")
    def test_a_slow_subprocess_is_stopped_and_its_job_logs_the_failure(self):
        outcome = []

        def backup():
            try:
                run_bounded([sys.executable, "-c", "import time; time.sleep(60)"], timeout=120)
                outcome.append("finished")
            except subprocess.CalledProcessError as e:
                outcome.append(e.returncode)

        run = run_in_background(backup, log=self.logs.append, name="backup")
        run()
        self.assertTrue(self.wait_until(lambda: jobs._groups))   # its subprocess is running
        started = time.monotonic()
        left = scheduler_temp.shut_down([run], self.logs.append, wait_s=0.5, grace_s=5, final_wait_s=5)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(left, [])
        self.assertEqual(outcome, [-signal.SIGTERM])
        self.assertTrue(any(line.startswith("[shutdown] Still running after 0.5 s, stopping: backup")
                            for line in self.logs))
        self.assertIn("[shutdown] Sent SIGTERM to 1 subprocess group(s)", self.logs)

    @unittest.skipUnless(hasattr(os, "killpg"), "process groups are POSIX-only; the worker runs on Linux")
    def test_a_subprocess_that_ignores_sigterm_is_killed(self):
        stubborn = ("import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); "
                    "time.sleep(60)")
        outcome = []

        def job():
            try:
                run_bounded([sys.executable, "-c", stubborn], timeout=120)
            except subprocess.CalledProcessError as e:
                outcome.append(e.returncode)

        thread = threading.Thread(target=job)
        thread.start()
        self.assertTrue(self.wait_until(lambda: jobs._groups))
        time.sleep(0.5)   # let it install its SIGTERM handler
        self.assertEqual(stop_subprocesses(grace=1), 1)
        thread.join(5)
        self.assertEqual(outcome, [-signal.SIGKILL])

    def test_no_new_subprocess_starts_once_stopping(self):
        stop_subprocesses(grace=0)
        with self.assertRaisesRegex(RuntimeError, "shutting down"):
            run_bounded([sys.executable, "-c", "print('never')"], timeout=10)

    def test_request_stop_only_sets_the_flag(self):
        self.addCleanup(scheduler_temp.stopping.clear)
        scheduler_temp.request_stop(signal.SIGTERM, None)
        self.assertTrue(scheduler_temp.stopping.is_set())

    def test_touch_alive_creates_and_updates_the_file_and_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "alive")
            scheduler_temp.touch_alive(path)
            self.assertTrue(os.path.exists(path))
            os.utime(path, (0, 0))
            scheduler_temp.touch_alive(path)
            self.assertGreater(os.path.getmtime(path), time.time() - 60)
            scheduler_temp.touch_alive(os.path.join(tmp, "no-such-folder", "alive"))   # no exception


@unittest.skipUnless(hasattr(os, "killpg"), "signals to a child process; the worker runs on Linux")
class SigtermEndToEndTests(unittest.TestCase):
    """The real loop in a child process: SIGTERM makes it exit 0 within seconds, after logging the shutdown."""

    def test_sigterm_stops_the_loop_and_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, "run.py")
            with open(script, "w") as f:
                f.write(f"""
import sys, time, types
sys.path.insert(0, {str(APP)!r}); sys.path.insert(0, {str(APP / 'scripts')!r})
sys.modules['inject_from_api'] = types.SimpleNamespace(inject_all_new_data=lambda: None)
import signal, scheduler_temp as s
signal.signal(signal.SIGTERM, s.request_stop)
log = s.file_logger({os.path.join(tmp, 'w.log')!r})
run = s.run_in_background(lambda: time.sleep(1), log=log, name="ingestion")
run()
print("ready", flush=True)
while not s.stopping.is_set():
    time.sleep(0.1)
s.shut_down([run], log, wait_s=10)
""")
            proc = subprocess.Popen([sys.executable, script], stdout=subprocess.PIPE, text=True)
            self.assertEqual(proc.stdout.readline().strip(), "ready")
            started = time.monotonic()
            proc.send_signal(signal.SIGTERM)
            self.assertEqual(proc.wait(10), 0)
            self.assertLess(time.monotonic() - started, 5)
            with open(os.path.join(tmp, "w.log")) as f:
                text = f.read()
            self.assertIn("[shutdown] Waiting up to 10 s for: ingestion", text)
            self.assertIn("[shutdown] Exiting", text)
            proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
