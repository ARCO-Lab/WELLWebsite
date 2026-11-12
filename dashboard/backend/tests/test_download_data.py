"""download_data.py's bookkeeping: refused files are recorded once and not retried, --force re-imports only the files
it names, and a run that refused a file reports REJECTED_<n>_FILES and fails; the scheduler reports that as a
failure. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import datetime as dt
import io
import json
import pathlib
import subprocess
import sys
import types
from unittest import TestCase, main, mock

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


class BookkeepingTests(TestCase):
    def test_import_outcome(self):
        self.assertEqual(download_data.import_outcome(0, "[INFO] Inserted 12 new sampling records.\n"), ("processed", 12))
        self.assertEqual(download_data.import_outcome(0, "[INFO] Inserted 0 new sampling records.\n"), ("processed", 0))
        self.assertEqual(download_data.import_outcome(INVALID_FILE_EXIT, REFUSED_OUT), ("refused", 7))
        self.assertEqual(download_data.import_outcome(1, "psycopg2.OperationalError"), ("failed", None))

    def test_import_counts(self):
        out = ("[INFO] Inserted 2 new sampling records.\n[INFO] Corrected 3 stored sampling records (the file's value "
               "replaced the stored one).\n[CORRECTED] site 1 E. coli on 2026-10-06 09:40: 1200.0 -> 120.0\n"
               "[WARN] 4 rows present in the DB but not in the latest file (same sites, ...)\n")
        self.assertEqual(download_data.import_counts(out), {"inserted": 2, "corrected": 3, "withdrawn": 4, "held": 0})
        self.assertEqual(download_data.import_counts(""), {"inserted": 0, "corrected": 0, "withdrawn": 0, "held": 0})

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

    def test_same_day_uploads_are_imported_in_upload_order(self):
        # Same create_date: the Dataverse id, which only grows, decides (as a number: 9 before 10)
        first, second, third = dataset_file(9, 4), dataset_file(10, 4), dataset_file(11, 4)
        self.assertEqual(download_data.choose_files([third, second, first], empty_state()), [first, second, third])

    def test_newer_files_are_the_processed_ones_with_a_higher_id(self):
        state = empty_state()
        download_data.record(state, OLD, "processed", scope={"sites": ["1"]})
        download_data.record(state, NEW, "processed", scope={"sites": ["2"]})
        state["processed_files"].append({"filename": "legacy.csv", "id": 7, "create_date": "2026-05-07T00:00:00"})
        self.assertEqual(download_data.newer_files(state, BAD), [
            {"file": "WELLAncasterWatershed_3.csv (ID: 3)", "scope": {"sites": ["2"]}},
            {"file": "legacy.csv (ID: 7)", "scope": None}])   # recorded before scopes: unknown, covers everything
        self.assertEqual(download_data.newer_files(state, dataset_file(8, 9)), [])

    def test_import_scope(self):
        self.assertEqual(download_data.import_scope('[INFO] x\n[SCOPE] {"sites": ["1"]}\n'), {"sites": ["1"]})
        self.assertIsNone(download_data.import_scope("[INFO] Inserted 1 new sampling records.\n"))


class MainTests(TestCase):
    def run_main(self, state, outcomes, *argv, files=(OLD, BAD, NEW)):
        """main() over OLD, BAD and NEW with the given state; outcomes maps file id -> (returncode, stdout)."""
        saved = []

        def importer(cmd, **kwargs):
            file_id = int(pathlib.Path(cmd[2]).stem)   # python, inject_sampling.py, the file, [--newer ...]
            code, out = outcomes[file_id]
            return subprocess.CompletedProcess(cmd, code, out, "")

        with mock.patch.object(sys, "argv", ["download_data.py", *argv]), \
                mock.patch.object(download_data, "load_state", return_value=state), \
                mock.patch.object(download_data, "save_state", side_effect=lambda s: saved.append(s)), \
                mock.patch.object(download_data, "get_files_from_dataset", return_value=list(files)), \
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

    def test_corrections_and_withdrawn_rows_are_summed_and_flagged(self):
        changed = (0, "[INFO] Inserted 1 new sampling records.\n[INFO] Corrected 2 stored sampling records (...)\n"
                      "[WARN] 3 rows present in the DB but not in the latest file (...)\n")
        clean = (0, "[INFO] Inserted 4 new sampling records.\n[INFO] Corrected 1 stored sampling records (...)\n")
        code, out, _, _ = self.run_main(empty_state(), {1: clean, 3: changed}, files=(OLD, NEW))
        self.assertEqual(code, 0)   # applied corrections and kept rows don't fail the run
        self.assertIn("OUTPUT: PROCESSED_2_FILES", out)
        self.assertIn("SUMMARY: 5 new, 3 corrected, 0 corrections not applied (a newer file covers them), 3 rows "
                      "present in the DB but not in the latest file", out)
        attention = [line for line in out.splitlines() if line.startswith("ATTENTION:")]
        self.assertEqual(len(attention), 1, out)
        self.assertIn("WELLAncasterWatershed_3.csv (ID: 3): 3 rows present in the DB but not in the latest file",
                      attention[0])

    def test_an_older_file_retried_after_a_newer_one_gets_the_newer_files_scope(self):
        # OLD's import failed last week; NEW (a higher id) was imported. This week OLD is retried.
        state = empty_state()
        scope = {"sites": ["3"], "measurement_types": ["E. coli"], "start": "2026-10-06T00:00:00",
                 "end": "2026-10-07T00:00:00"}
        download_data.record(state, NEW, "processed", scope=scope)
        held = (0, "[INFO] Inserted 0 new sampling records.\n[INFO] Corrected 0 stored sampling records (...)\n"
                   "[WARN] 1 corrections not applied: a newer file, already imported, covers these readings\n"
                   '[SCOPE] {"sites": ["3"]}\n')
        code, out, saved, run = self.run_main(state, {1: held}, files=(OLD, NEW))
        self.assertEqual(code, 0)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[3], "--newer")
        self.assertEqual(json.loads(cmd[4]), [{"file": "WELLAncasterWatershed_3.csv (ID: 3)", "scope": scope}])
        self.assertIn("SUMMARY: 0 new, 0 corrected, 1 corrections not applied", out)
        self.assertIn("ATTENTION: WELLAncasterWatershed_1.csv (ID: 1): 1 corrections not applied", out)
        self.assertEqual({f["id"]: f["scope"] for f in saved[-1]["processed_files"]},
                         {3: scope, 1: {"sites": ["3"]}})

    def test_files_imported_in_order_see_no_newer_file(self):
        ok = (0, "[INFO] Inserted 1 new sampling records.\n")
        code, _, _, run = self.run_main(empty_state(), {1: ok, 3: ok}, files=(NEW, OLD))
        self.assertEqual(code, 0)
        self.assertEqual([c.args[0][2] for c in run.call_args_list], ["/tmp/1.xlsx", "/tmp/3.xlsx"])
        self.assertTrue(all(len(c.args[0]) == 3 for c in run.call_args_list))   # no --newer

    def test_a_failed_import_is_retried_and_fails_the_run(self):
        code, out, saved, _ = self.run_main(empty_state(), {1: (1, ""), 2: (1, ""), 3: (1, "")})
        self.assertEqual(code, 1)
        self.assertIn("OUTPUT: FAILED_3_FILES", out)
        self.assertEqual(saved[-1], empty_state())   # nothing recorded, so the next run tries again

    def test_no_reminder_for_a_refused_file_no_longer_in_the_dataset(self):
        state = empty_state()
        download_data.record(state, BAD, "refused", 7)
        code, out, _, _ = self.run_main(state, {3: (0, "[INFO] Inserted 1 new sampling records.\n")}, files=(NEW,))
        self.assertEqual(code, 0)
        self.assertNotIn("was refused", out)

    def test_an_empty_dataset_reports_no_new_files(self):
        code, out, _, run = self.run_main(empty_state(), {}, files=())
        self.assertEqual((code, run.call_count), (0, 0))
        self.assertIn("OUTPUT: NO_NEW_FILES", out)

    def test_a_file_name_matching_nothing_is_an_error(self):
        code, out, _, run = self.run_main(empty_state(), {}, "--force", "--file", "99", "--file", "2")
        self.assertNotEqual(code, 0)
        self.assertEqual(run.call_count, 0)
        self.assertIn("ERROR: --file 99 matches no file of the dataset", out)
        self.assertNotIn("OUTPUT:", out)


class SchedulerTests(TestCase):
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

    def test_attention_lines_go_to_sentry_as_warnings(self):
        line = "ATTENTION: WELLAncasterWatershed_3.csv (ID: 3): 3 rows present"
        # Also when another file of the same run was refused (the run then exits 1)
        for code, status in ((0, "PROCESSED_1_FILES"), (1, "REJECTED_1_FILES")):
            with self.subTest(code=code), mock.patch.object(scheduler_temp, "capture_job_warning") as warn:
                self.run_job(f"{line}\nOUTPUT: {status}\n", code)
                warn.assert_called_once_with(line)
        with mock.patch.object(scheduler_temp, "capture_job_warning") as warn:
            self.assertEqual(self.run_job("OUTPUT: PROCESSED_1_FILES\n", 0)[1], [("download", "success")])
            warn.assert_not_called()

    def test_success_and_nothing_new(self):
        self.assertEqual(self.run_job("OUTPUT: PROCESSED_2_FILES\n", 0)[1], [("download", "success")])
        self.assertEqual(self.run_job("OUTPUT: NO_NEW_FILES\n", 0)[1], [("download", "success")])


if __name__ == "__main__":
    main()
