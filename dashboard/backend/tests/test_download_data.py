"""download_data.py's bookkeeping: refused files are recorded once and not retried, --force re-imports only the files
it names, and a run that refused a file reports REJECTED_<n>_FILES and fails; the scheduler reports that as a
failure. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import datetime as dt
import io
import pathlib
import subprocess
import sys
import types
import unittest
from unittest import mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
from scripts import download_data  # noqa: E402
from utils.sampling_csv import INVALID_FILE_EXIT  # noqa: E402
sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
import scheduler_temp  # noqa: E402


def dataset_file(file_id, day):
    return {"filename": f"WELLAncasterWatershed_{file_id}.csv", "id": file_id, "create_date": dt.datetime(2026, 5, day)}


OLD, BAD, NEW = dataset_file(1, 1), dataset_file(2, 2), dataset_file(3, 3)
REFUSED_OUT = "[ERROR] row 2, site: unknown site 'X'\n[ERROR] 7 problems in /tmp/x.xlsx; nothing was imported.\n"


def empty_state():
    return {"processed_files": [], "refused_files": []}


class BookkeepingTests(unittest.TestCase):
    def test_import_outcome(self):
        self.assertEqual(download_data.import_outcome(0, "[INFO] Inserted 12 new sampling records.\n"), ("processed", 12))
        self.assertEqual(download_data.import_outcome(0, "[INFO] Inserted 0 new sampling records.\n"), ("processed", 0))
        self.assertEqual(download_data.import_outcome(INVALID_FILE_EXIT, REFUSED_OUT), ("refused", 7))
        self.assertEqual(download_data.import_outcome(1, "psycopg2.OperationalError"), ("failed", None))

    def test_run_status(self):
        self.assertEqual(download_data.run_status(2, 0, 0), "PROCESSED_2_FILES")
        self.assertEqual(download_data.run_status(0, 0, 0), "NO_FILES_PROCESSED")
        self.assertEqual(download_data.run_status(3, 1, 1), "REJECTED_1_FILES")
        self.assertEqual(download_data.run_status(3, 0, 2), "FAILED_2_FILES")

    def test_record_moves_a_file_between_lists(self):
        state = empty_state()
        download_data.record(state, BAD, "refused", 7)
        self.assertEqual([(f["id"], f["errors"]) for f in state["refused_files"]], [(2, 7)])
        download_data.record(state, BAD, "processed")   # re-imported with --force after a fix
        self.assertEqual(state["refused_files"], [])
        self.assertEqual([f["id"] for f in state["processed_files"]], [2])

    def test_choose_files(self):
        state = empty_state()
        download_data.record(state, OLD, "processed")
        download_data.record(state, BAD, "refused", 7)
        choose = download_data.choose_files
        self.assertEqual(choose([NEW, BAD, OLD], state), [NEW])
        self.assertEqual(choose([NEW, BAD, OLD], state, force=True), [NEW])   # --force alone re-imports nothing
        self.assertEqual(choose([NEW, BAD, OLD], state, ["2"], force=True), [BAD, NEW])
        self.assertEqual(choose([NEW, BAD, OLD], state, [OLD["filename"]], force=True), [OLD, NEW])
        self.assertEqual(choose([NEW, BAD, OLD], state, ["2"]), [NEW])        # naming needs --force


class MainTests(unittest.TestCase):
    def run_main(self, state, outcomes, *argv):
        """main() over OLD, BAD and NEW with the given state; outcomes maps file id -> (returncode, stdout)."""
        saved = []

        def importer(cmd, **kwargs):
            file_id = int(pathlib.Path(cmd[-1]).stem)
            code, out = outcomes[file_id]
            return subprocess.CompletedProcess(cmd, code, out, "")

        with mock.patch.object(sys, "argv", ["download_data.py", *argv]), \
                mock.patch.object(download_data, "load_state", return_value=state), \
                mock.patch.object(download_data, "save_state", side_effect=lambda s: saved.append(s)), \
                mock.patch.object(download_data, "get_files_from_dataset", return_value=[OLD, BAD, NEW]), \
                mock.patch.object(download_data, "process_single_file", side_effect=lambda f: f"/tmp/{f['id']}.xlsx"), \
                mock.patch.object(download_data.os, "unlink"), \
                mock.patch.object(download_data.subprocess, "run", side_effect=importer) as run, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                download_data.main()
                code = 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), saved, run

    def test_a_refused_file_is_recorded_reported_and_fails_the_run(self):
        ok = (0, "[INFO] Inserted 0 new sampling records.\n")
        code, out, saved, _ = self.run_main(empty_state(), {1: ok, 2: (INVALID_FILE_EXIT, REFUSED_OUT), 3: ok})
        self.assertEqual(code, 1)
        self.assertIn("OUTPUT: REJECTED_1_FILES", out)
        self.assertIn("unknown site 'X'", out)   # the import's problems are logged with the refusal
        state = saved[-1]
        self.assertEqual([(f["id"], f["errors"]) for f in state["refused_files"]], [(2, 7)])
        # Imported with nothing new (every row already stored) still counts as processed: no weekly retry
        self.assertEqual(sorted(f["id"] for f in state["processed_files"]), [1, 3])

    def test_a_refused_file_is_not_retried_but_a_reminder_is_logged(self):
        state = empty_state()
        download_data.record(state, OLD, "processed")
        download_data.record(state, BAD, "refused", 7)
        code, out, _, run = self.run_main(state, {3: (0, "[INFO] Inserted 4 new sampling records.\n")})
        self.assertEqual(code, 0)
        self.assertIn("OUTPUT: PROCESSED_1_FILES", out)
        self.assertEqual(run.call_count, 1)   # NEW only
        self.assertIn("WARNING: WELLAncasterWatershed_2.csv (ID: 2) was refused", out)
        self.assertNotIn("unknown site 'X'", out)   # the problems themselves were logged once, when refused

    def test_force_reimports_only_named_files(self):
        state = empty_state()
        for f in (OLD, NEW):
            download_data.record(state, f, "processed")
        download_data.record(state, BAD, "refused", 7)
        code, out, _, run = self.run_main(state, {}, "--force")
        self.assertEqual((code, run.call_count), (0, 0))
        self.assertIn("OUTPUT: NO_NEW_FILES", out)
        code, out, saved, run = self.run_main(state, {2: (0, "[INFO] Inserted 9 new sampling records.\n")},
                                              "--force", "--file", "2")
        self.assertEqual((code, run.call_count), (0, 1))
        self.assertEqual(saved[-1]["refused_files"], [])

    def test_a_failed_import_is_retried_and_fails_the_run(self):
        code, out, saved, _ = self.run_main(empty_state(), {1: (1, ""), 2: (1, ""), 3: (1, "")})
        self.assertEqual(code, 1)
        self.assertIn("OUTPUT: FAILED_3_FILES", out)
        self.assertEqual(saved[-1], empty_state())   # nothing recorded, so the next run tries again


class SchedulerTests(unittest.TestCase):
    def run_job(self, stdout, code):
        logs, pings = [], []

        def run(cmd, timeout):
            if "--list-files" in cmd:
                raise AssertionError("listed the dataset for a run that only refused a file")
            if code:
                raise subprocess.CalledProcessError(code, cmd, output=stdout, stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout, "")

        with mock.patch.object(scheduler_temp, "run_bounded", side_effect=run), \
                mock.patch.object(scheduler_temp, "timestamped_print_download", lambda *a: logs.append(" ".join(map(str, a)))), \
                mock.patch.object(scheduler_temp, "ping_heartbeat", side_effect=lambda *a: pings.append(a)):
            scheduler_temp.download_job()
        return "\n".join(logs), pings

    def test_refused_file_is_a_failure(self):
        logs, pings = self.run_job("OUTPUT: REJECTED_1_FILES\n", 1)
        self.assertIn("[ERROR] download_data.py finished with status REJECTED_1_FILES", logs)
        self.assertEqual(pings, [("download", "fail")])

    def test_success_and_nothing_new(self):
        self.assertEqual(self.run_job("OUTPUT: PROCESSED_2_FILES\n", 0)[1], [("download", "success")])
        self.assertEqual(self.run_job("OUTPUT: NO_NEW_FILES\n", 0)[1], [("download", "success")])


if __name__ == "__main__":
    unittest.main()
