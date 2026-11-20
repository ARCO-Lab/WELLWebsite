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
import tempfile
import types
from unittest import TestCase, main, mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
from scripts import download_data  # noqa: E402
from utils.sampling_csv import INVALID_FILE_EXIT, validate_csv  # noqa: E402
from utils.jobs import SETTINGS_ERROR_EXIT  # noqa: E402
sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
import scheduler_temp  # noqa: E402

MAX_LISTED = 50   # inject_sampling.py lists at most this many problems; keep in step with it


def dataset_file(file_id, day):
    return {"filename": f"WELLAncasterWatershed_{file_id}.csv", "id": file_id, "create_date": dt.datetime(2026, 5, day)}


OLD, BAD, NEW = dataset_file(1, 1), dataset_file(2, 2), dataset_file(3, 3)
REFUSED_OUT = "[ERROR] row 2, site: unknown site 'X'\n[ERROR] 7 problems in /tmp/x.xlsx; nothing was imported.\n"


def inject_refused_output(csv_text, path="/tmp/x.csv"):
    """What inject_sampling.py prints when the standard-CSV validator refuses `csv_text` (utils/sampling_csv), so a
    test exercises the real format rules, not a hand-written message. Returns (stdout, Result)."""
    result = validate_csv(csv_text.encode("utf-8"))
    assert not result.ok, "expected a malformed file"
    lines = [f"[ERROR] {issue}" for issue in result.errors[:MAX_LISTED]]
    if len(result.errors) > MAX_LISTED:
        lines.append(f"[ERROR] ... and {len(result.errors) - MAX_LISTED} more problems not listed "
                     f"(scripts/check_sampling_csv.py lists them all)")
    lines.append(f"[ERROR] {len(result.errors)} problems in {path}; nothing was imported. Fix them and upload the "
                 f"file again.")
    return "\n".join(lines) + "\n", result


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

    def test_state_is_written_whole_or_not_at_all(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(pathlib.Path(folder, "processed.json"))
            state = empty_state()
            download_data.record(state, OLD, "processed", scope={"sites": ["1"]})
            with mock.patch.object(download_data, "STATE_FILE", path), contextlib.redirect_stdout(io.StringIO()):
                download_data.save_state(state)
                self.assertEqual(json.loads(pathlib.Path(path).read_text())["processed_files"][0]["id"], 1)
                # A write that fails part-way (here an entry that can't be written as JSON) leaves the file as it was
                download_data.record(state, NEW, "processed", scope={"sites": {"not", "json"}})
                download_data.save_state(state)
            self.assertEqual([f["id"] for f in json.loads(pathlib.Path(path).read_text())["processed_files"]], [1])

    def test_a_damaged_state_file_stops_the_run_and_is_kept(self):
        # Read as empty, every dataset file would be imported again, undoing deletions and held corrections
        for damaged in ('{"processed_files": [{"id": 1', "", "[]", '{"processed_files": "1,2"}',
                        b"\xff\xfe not utf-8"):
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as folder:
                path = pathlib.Path(folder, "processed.json")
                (path.write_bytes if isinstance(damaged, bytes) else path.write_text)(damaged)
                with mock.patch.object(download_data, "STATE_FILE", str(path)), \
                        contextlib.redirect_stdout(io.StringIO()), self.assertRaises(download_data.StateFileError) as e:
                    download_data.load_state()
                self.assertIn("can't be read", str(e.exception))
                self.assertIn("processed.json.bad", str(e.exception))
                bad = pathlib.Path(folder, "processed.json.bad")
                self.assertEqual(bad.read_bytes(), path.read_bytes())   # the original is left as it was, too

    def test_no_state_file_is_an_empty_state_and_a_good_one_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder, "processed.json")
            with mock.patch.object(download_data, "STATE_FILE", str(path)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(download_data.load_state(), empty_state())
                path.write_text(json.dumps({"processed_files": [{"id": 1, "filename": "a.csv"}]}))
                self.assertEqual(download_data.load_state(),
                                 {"processed_files": [{"id": 1, "filename": "a.csv"}], "refused_files": []})

    def test_a_damaged_state_file_fails_the_run_before_any_download(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder, "processed.json")
            path.write_text("{")
            out = io.StringIO()
            with mock.patch.object(download_data, "STATE_FILE", str(path)), \
                    mock.patch.object(download_data, "get_files_from_dataset") as listing, \
                    mock.patch.object(sys, "argv", ["download_data.py"]), contextlib.redirect_stdout(out), \
                    self.assertRaises(SystemExit) as exited:
                download_data.main()
            self.assertEqual(exited.exception.code, 1)
            listing.assert_not_called()
            self.assertIn("can't be read", out.getvalue())
            self.assertNotIn("OUTPUT:", out.getvalue())

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

    def test_refusal_problems_are_the_listed_issues_only(self):
        out = ("[INFO] Loading file: /tmp/x.csv\n"
               "[ERROR] row 1, unit: required column is missing\n"
               "[ERROR] row 12, date: '2026-13-05' is not a real date\n"
               "[ERROR] ... and 3 more problems not listed (scripts/check_sampling_csv.py lists them all)\n"
               "[ERROR] 5 problems in /tmp/x.csv; nothing was imported. Fix them and upload the file again.\n")
        self.assertEqual(download_data.refusal_problems(out),
                         ["row 1, unit: required column is missing",
                          "row 12, date: '2026-13-05' is not a real date"])
        self.assertEqual(download_data.refusal_problems(""), [])

    def test_refusal_attention_names_the_file_the_count_and_the_first_problems(self):
        line = download_data.refusal_attention(BAD, 5, ["row 1, unit: required column is missing",
                                                        "row 12, date: '2026-13-05' is not a real date",
                                                        "row 2, parameter: unknown parameter 'Nitrite'",
                                                        "row 3, site: unknown site 'X'"])
        self.assertTrue(line.startswith("ATTENTION: WELLAncasterWatershed_2.csv (ID: 2): "))
        self.assertIn("sampling upload in the wrong format (5 problems), needs a manual check", line)
        self.assertIn("row 1, unit: required column is missing", line)
        self.assertIn("and 2 more", line)                               # 4 given, 3 shown
        self.assertNotIn("unknown site 'X'", line)                      # the 4th isn't shown
        self.assertIn("docs/sampling-csv-format.md", line)
        # One problem reads as singular, and a short list names them all without "more"
        one = download_data.refusal_attention(BAD, 1, ["row 1, unit: required column is missing"])
        self.assertIn("(1 problem),", one)
        self.assertNotIn("more", one)

    def test_each_malformed_file_is_flagged_with_the_validators_own_message(self):
        # The real format rules (utils/sampling_csv), so the alert can't drift from the one source of truth
        header = "date,site,parameter,value,unit\n"
        cases = {
            "missing column": ("date,site,parameter,value\n2026-05-06,Falkirk Forest,pH,7.1\n",
                               "unit: required column is missing"),
            "unparseable date": (header + "2026-13-40,Falkirk Forest,pH,7.1,pH units\n", "is not a real date"),
            "ambiguous date": (header + "05/06/2026,Falkirk Forest,pH,7.1,pH units\n", "ambiguous"),
            "unknown parameter": (header + "2026-05-06,Falkirk Forest,Nitrite,0.1,mg/L\n",
                                  "unknown parameter 'Nitrite'"),
            "unknown site": (header + "2026-05-06,Nowhere,pH,7.1,pH units\n", "unknown site 'Nowhere'"),
            "wrong unit": (header + "2026-05-06,Falkirk Forest,pH,7.1,NTU\n", "doesn't match pH"),
            "no readings": (header, "no readings to import"),
        }
        for name, (csv_text, expected) in cases.items():
            with self.subTest(case=name):
                out, result = inject_refused_output(csv_text)
                problems = download_data.refusal_problems(out)
                self.assertEqual(problems, [str(issue) for issue in result.errors])   # the validator's exact text
                line = download_data.refusal_attention(BAD, len(result.errors), problems)
                self.assertIn("sampling upload in the wrong format", line)
                self.assertIn("needs a manual check", line)
                self.assertIn(expected, line)


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
                mock.patch.object(download_data, "get_files_from_dataset",
                                  **({"side_effect": files} if isinstance(files, Exception)
                                     else {"return_value": list(files)})), \
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

    def test_a_wrong_format_file_is_flagged_and_the_good_files_still_import(self):
        # A mix: the good files ingest, the malformed one is flagged for a manual check and fails the run
        # One row with several problems: a bad date, an unknown site and an unknown parameter
        bad_csv = "date,site,parameter,value,unit\n2026-13-40,Nowhere,Nitrite,0.1,mg/L\n"
        refused_out, result = inject_refused_output(bad_csv)
        self.assertGreater(len(result.errors), 1)
        ok = (0, "[INFO] Inserted 5 new sampling records.\n")
        code, out, saved, _ = self.run_main(empty_state(),
                                             {1: ok, 2: (INVALID_FILE_EXIT, refused_out), 3: ok})
        self.assertEqual(code, 1)
        self.assertIn("OUTPUT: REJECTED_1_FILES", out)
        attention = [line for line in out.splitlines() if line.startswith("ATTENTION:")]
        self.assertEqual(len(attention), 1, out)
        self.assertIn("WELLAncasterWatershed_2.csv (ID: 2): sampling upload in the wrong format", attention[0])
        self.assertIn("needs a manual check", attention[0])
        self.assertIn(f"({len(result.errors)} problems)", attention[0])
        self.assertIn("unknown site 'Nowhere'", attention[0])   # a real problem the validator found
        # The good files were imported and recorded; only the malformed one is refused
        self.assertEqual(sorted(f["id"] for f in saved[-1]["processed_files"]), [1, 3])
        self.assertEqual([f["id"] for f in saved[-1]["refused_files"]], [2])

    def test_a_clean_run_raises_no_format_alert(self):
        ok = (0, "[INFO] Inserted 4 new sampling records.\n")
        code, out, saved, _ = self.run_main(empty_state(), {1: ok, 2: ok, 3: ok})
        self.assertEqual(code, 0)
        self.assertIn("OUTPUT: PROCESSED_3_FILES", out)
        self.assertNotIn("wrong format", out)
        self.assertEqual([line for line in out.splitlines() if line.startswith("ATTENTION:")], [])
        self.assertEqual(saved[-1]["refused_files"], [])

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

    def test_a_never_published_dataset_is_a_warning_not_a_failure(self):
        for argv in ((), ("--list-files",)):
            for waiting in ([], ["WELLAncasterWatershed_May2026.csv"]):
                with self.subTest(argv=argv, waiting=waiting):
                    code, out, saved, run = self.run_main(empty_state(), {}, *argv,
                                                          files=download_data.NotPublished(waiting))
                    self.assertEqual((code, run.call_count, saved), (0, 0, []))
                    self.assertIn("WARNING: ", out)
                    self.assertIn("OUTPUT: NOT_PUBLISHED", out)
                    pending = [line for line in out.splitlines() if line.startswith("PENDING:")]
                    self.assertEqual(len(pending), len(waiting))
                    if waiting:
                        self.assertIn("1 sampling files wait in the unpublished draft", pending[0])
                        self.assertIn("WELLAncasterWatershed_May2026.csv", pending[0])

    def test_a_setting_to_fix_exits_with_the_settings_code(self):
        out = io.StringIO()
        problem = download_data.DownloadSettingsError("BOREALIS_URL is https://borealisdata.ca but the dataset ...")
        with mock.patch.object(sys, "argv", ["download_data.py"]), \
                mock.patch.object(download_data, "load_state", return_value=empty_state()), \
                mock.patch.object(download_data, "get_files_from_dataset", side_effect=problem), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as exited:
            download_data.main()
        self.assertEqual(exited.exception.code, SETTINGS_ERROR_EXIT)
        self.assertEqual(out.getvalue().splitlines()[-1], f"ERROR: {problem}")

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
                raise AssertionError("listed the dataset for a run that only refused a file or needs a setting")
            if code:
                raise subprocess.CalledProcessError(code, cmd, output=stdout, stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout, "")

        with mock.patch.object(scheduler_temp, "run_bounded", side_effect=run), \
                mock.patch.object(scheduler_temp, "timestamped_print_download", lambda *a: logs.append(" ".join(map(str, a)))), \
                mock.patch.object(scheduler_temp, "ping_heartbeat",
                                  side_effect=lambda *a, **k: pings.append(a + tuple(k.values()))):
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

    def test_a_wrong_format_refusal_reaches_sentry_and_the_digest(self):
        # The refused run exits 1 (REJECTED); its ATTENTION: line must still reach Sentry (warning) and the digest
        line = ("ATTENTION: WELLAncasterWatershed_May2026.csv (ID: 57): sampling upload in the wrong format "
                "(3 problems), needs a manual check; nothing from it was imported.")
        with mock.patch.object(scheduler_temp, "capture_job_warning") as warn, \
                mock.patch.object(scheduler_temp, "record_attention") as record:
            logs, pings = self.run_job(f"{line}\nOUTPUT: REJECTED_1_FILES\n", 1)
        warn.assert_called_once_with(line)
        recorded = [x for call in record.call_args_list for x in call.args[0] if x.startswith("ATTENTION:")]
        self.assertEqual(recorded, [line])          # the daily digest lists it under "needs a decision"
        self.assertEqual(pings, [("download", "fail")])

    def test_success_and_nothing_new(self):
        self.assertEqual(self.run_job("OUTPUT: PROCESSED_2_FILES\n", 0)[1], [("download", "success")])
        self.assertEqual(self.run_job("OUTPUT: NO_NEW_FILES\n", 0)[1], [("download", "success")])

    def test_a_never_published_dataset_is_a_logged_success(self):
        with mock.patch.object(scheduler_temp, "capture_job_error") as error, \
                mock.patch.object(scheduler_temp, "capture_job_warning") as warn:
            logs, pings = self.run_job("WARNING: doi:x has no published version yet\nOUTPUT: NOT_PUBLISHED\n", 0)
        error.assert_not_called()
        warn.assert_not_called()
        self.assertIn("[WARN] The sampling dataset has no published version yet", logs)
        self.assertEqual(pings, [("download", "success", scheduler_temp.NOT_PUBLISHED_NOTE)])

    def test_files_waiting_in_an_unpublished_draft_go_to_the_digest_not_sentry(self):
        pending = "PENDING: 2 sampling files wait in the unpublished draft of doi:x (a.csv, b.csv); ..."
        with mock.patch.object(scheduler_temp, "capture_job_warning") as warn, \
                mock.patch.object(scheduler_temp, "record_attention") as record:
            _, pings = self.run_job(f"{pending}\nOUTPUT: NOT_PUBLISHED\n", 0)
        warn.assert_not_called()
        # record_attention keeps only the ATTENTION: lines of what it is given (report_attention passes all)
        lines = [line for call in record.call_args_list for line in call.args[0] if line.startswith("ATTENTION:")]
        self.assertEqual(lines, ["ATTENTION: " + pending[len("PENDING: "):]])
        self.assertEqual(pings, [("download", "success", scheduler_temp.NOT_PUBLISHED_NOTE)])

    def test_a_setting_to_fix_is_reported_as_its_message(self):
        message = "BOREALIS_URL is https://borealisdata.ca but the dataset doi:10.80240/FK2/X is on the demo server"
        with mock.patch.object(scheduler_temp, "capture_job_error") as error:
            logs, pings = self.run_job(f"DEBUG: Starting process...\nERROR: {message}\n", SETTINGS_ERROR_EXIT)
        reported = error.call_args.args[0]
        self.assertIsInstance(reported, scheduler_temp.SettingsError)
        self.assertEqual(str(reported), message)
        self.assertIn(f"[ERROR] download_data.py stopped: {message}", logs)
        self.assertEqual(pings, [("download", "fail")])


if __name__ == "__main__":
    main()
