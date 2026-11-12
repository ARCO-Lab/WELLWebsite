"""The worker's file logs (utils/worklog.py): timestamps, rotation by size, and a log that can't be written never
stopping a job. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import builtins
import io
import os
import pathlib
import re
import sys
import tempfile
import types
from unittest import TestCase, main, mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))

from utils.worklog import file_logger  # noqa: E402


class FileLoggerTests(TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def lines(self, name):
        with open(self.path(name), encoding="utf-8") as f:
            return f.read().splitlines()

    def test_lines_are_timestamped_like_print(self):
        log = file_logger(self.path("a.log"))
        log("hello", 3, None)
        log("x", "y", sep="-")
        first, second = self.lines("a.log")
        self.assertRegex(first, r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\] hello 3 None$")
        self.assertTrue(second.endswith("] x-y"))

    def test_mirrors_to_stdout_when_asked(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            file_logger(self.path("b.log"), mirror_stdout=True)("seen")
        self.assertRegex(out.getvalue(), r"^\[[^]]+\] seen\n$")

    def test_print_to_a_stream_goes_to_that_stream(self):
        # Standing in for builtins.print, print(..., file=f) must still write to f, not the log
        stream = io.StringIO()
        file_logger(self.path("c.log"))("to the stream", file=stream)
        self.assertEqual(stream.getvalue(), "to the stream\n")
        self.assertFalse(os.path.exists(self.path("c.log")))

    def test_rotates_by_size_and_keeps_a_few_old_copies(self):
        log = file_logger(self.path("r.log"), max_bytes=200, backup_count=2)
        for n in range(40):
            log(f"line {n:02d} " + "x" * 30)
        names = sorted(os.listdir(self.dir.name))
        self.assertEqual(names, ["r.log", "r.log.1", "r.log.2"])
        for name in names:
            self.assertLessEqual(os.path.getsize(self.path(name)), 200)
        self.assertIn("line 39", self.lines("r.log")[-1])   # the newest line is in the current file

    def test_a_file_already_over_the_limit_is_rotated_on_the_first_line(self):
        with open(self.path("big.log"), "w") as f:
            f.write("old\n" * 100)
        file_logger(self.path("big.log"), max_bytes=100, backup_count=3)("new")
        self.assertEqual(len(self.lines("big.log")), 1)
        self.assertEqual(self.lines("big.log.1"), ["old"] * 100)   # kept, not deleted

    def test_an_unwritable_log_never_raises_and_is_reported_once(self):
        log = file_logger(os.path.join(self.dir.name, "missing-folder", "x.log"))
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            log("one")
            log("two")
        self.assertEqual(err.getvalue().count("can't write"), 1)
        self.assertIn("FileNotFoundError", err.getvalue())
        # Once the folder exists, lines are written again
        os.mkdir(os.path.join(self.dir.name, "missing-folder"))
        log("three")
        with open(os.path.join(self.dir.name, "missing-folder", "x.log")) as f:
            self.assertTrue(f.read().rstrip().endswith("] three"))

    def test_the_same_file_shares_one_handler(self):
        a = file_logger(self.path("s.log"), max_bytes=10_000)
        b = file_logger(self.path("s.log"), max_bytes=10_000)
        a("from a")
        b("from b")
        self.assertEqual([re.sub(r"^\[[^]]+\] ", "", line) for line in self.lines("s.log")], ["from a", "from b"])


class IngestionWithoutALogTests(TestCase):
    """A log that can't be written mustn't stop a job before its heartbeat ping."""

    def test_a_failed_run_still_pings_fail_when_its_log_is_unwritable(self):
        sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
        import scheduler_temp
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        broken_print = file_logger(os.path.join(tmp.name, "no-such-folder", "db_injections.log"))
        pings = []

        def vendor_down():
            raise RuntimeError("LI-COR unreachable")

        with mock.patch.object(builtins, "print", broken_print), \
                mock.patch.object(scheduler_temp, "inject_all_new_data", vendor_down), \
                mock.patch.object(scheduler_temp, "ping_heartbeat", lambda *a: pings.append(a)), \
                mock.patch.object(scheduler_temp, "capture_job_error", lambda *a, **k: None), \
                mock.patch.object(scheduler_temp, "alert_check_job", lambda: None), \
                mock.patch("sys.stderr", io.StringIO()):
            scheduler_temp.api_injection_job()
        self.assertEqual(pings, [("ingestion", "fail")])


if __name__ == "__main__":
    main()
