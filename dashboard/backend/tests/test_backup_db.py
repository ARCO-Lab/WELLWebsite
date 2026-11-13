"""The nightly database backup (scripts/backup_db.py, utils/backup.py), its restore drill (scripts/restore_check.py)
and its slot in the scheduler. Run from dashboard/backend: python -m unittest discover -s tests -t .

RoundTrip runs pg_dump and pg_restore against PostgreSQL. It runs only when TEST_POSTGRES_URL points at a disposable
server reached as a superuser (CI's postgres:13 container), because it creates and drops a role and databases there;
never point it at a real one."""
import datetime as dt
import io
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import types
import unittest.mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
from utils import backup  # noqa: E402

mock = unittest.mock

LISTING = """;
; Archive created at 2026-11-11 03:15:02 EST
;     dbname: welldb
;
; Selected TOC Entries:
;
200; 1259 16385 TABLE public sensor_measurements welluser
201; 1259 16390 TABLE public sampling_measurements welluser
3001; 0 16385 TABLE DATA public sensor_measurements welluser
3002; 0 16390 TABLE DATA public sampling_measurements welluser
3003; 0 16400 TABLE DATA public schema_migrations welluser
3004; 0 0 SEQUENCE SET public sensor_measurements_id_seq welluser
"""


class RetentionTests(unittest.TestCase):
    def names(self, start, days, times=("0315",)):
        day = dt.date.fromisoformat(start)
        return [f"welldb-{(day + dt.timedelta(days=i)).strftime('%Y%m%d')}-{t}.dump"
                for i in range(days) for t in times]

    def test_keeps_newest_per_day_for_n_days_and_per_week_for_m_weeks(self):
        names = self.names("2026-09-01", 70)   # 1 Sep .. 9 Nov 2026, one a night
        keep = backup.dumps_to_keep(names, keep_daily=7, keep_weekly=4)
        daily = {f"welldb-202611{d:02d}-0315.dump" for d in range(3, 10)}
        self.assertLessEqual(daily, keep)
        # Weeks are ISO weeks (Monday to Sunday); each keeps its newest dump. Week 45 (2-8 Nov) and 46 (9 Nov) are
        # already covered by the daily ones; the two before end on Sundays 1 Nov and 25 Oct.
        self.assertEqual(keep - daily, {"welldb-20261101-0315.dump", "welldb-20261025-0315.dump"})
        self.assertEqual(len(backup.dumps_to_prune(names, 7, 4)), 70 - len(keep))

    def test_two_dumps_on_one_day_keep_only_the_newer(self):
        names = self.names("2026-11-09", 2, times=("0315", "1420"))
        self.assertEqual(backup.dumps_to_keep(names, keep_daily=7, keep_weekly=0),
                         {"welldb-20261109-1420.dump", "welldb-20261110-1420.dump"})
        self.assertEqual(backup.dumps_to_prune(names, 7, 0),
                         ["welldb-20261109-0315.dump", "welldb-20261110-0315.dump"])

    def test_never_touches_other_files(self):
        names = self.names("2026-01-01", 30) + [
            "welldb-2026-11-10.dump", "notes.txt", ".welldb-20261111-0315.dump.partial", "welldb-20261399-0315.dump",
            "manual-before-migration.dump", "welldb-20261110-0315.dump.bak"]
        pruned = backup.dumps_to_prune(names, keep_daily=1, keep_weekly=0)
        self.assertEqual(len(pruned), 29)
        self.assertTrue(all(backup.dump_time(n) for n in pruned))

    def test_dump_name_round_trips(self):
        when = dt.datetime(2026, 11, 11, 3, 15)
        self.assertEqual(backup.dump_name(when), "welldb-20261111-0315.dump")
        self.assertEqual(backup.dump_time(backup.dump_name(when)), when)

    def test_a_dump_taken_by_hand_before_the_nightly_one_survives_that_night(self):
        # Taken at 01:00 before a migration; the 03:15 dump is that day's newest, which alone would doom it
        names = ["welldb-20261110-0315.dump", "welldb-20261111-0100.dump", "welldb-20261111-0315.dump"]
        night = dt.datetime(2026, 11, 11, 3, 20)
        self.assertEqual(backup.dumps_to_prune(names, 7, 0), ["welldb-20261111-0100.dump"])   # without `now`
        self.assertEqual(backup.dumps_to_prune(names, 7, 0, now=night), [])
        # Once it is more than 24 h old, it goes like any other
        self.assertEqual(backup.dumps_to_prune(names, 7, 0, now=dt.datetime(2026, 11, 12, 0, 30)), [])
        self.assertEqual(backup.dumps_to_prune(names, 7, 0, now=dt.datetime(2026, 11, 12, 3, 20)),
                         ["welldb-20261111-0100.dump"])

    def test_the_last_good_dump_is_never_pruned(self):
        # Ten failing nights after the last good dump (the 1st): retention alone would delete it
        names = self.names("2026-11-01", 11)
        self.assertIn("welldb-20261101-0315.dump", backup.dumps_to_prune(names, 7, 0))
        self.assertNotIn("welldb-20261101-0315.dump",
                         backup.dumps_to_prune(names, 7, 0, protect=["welldb-20261101-0315.dump", "notes.txt"]))

    def test_row_count_files_follow_their_dumps(self):
        names = ["welldb-20261110-0315.dump", ".welldb-20261110-0315.dump.counts.json",
                 ".welldb-20261101-0315.dump.counts.json", ".notes.counts.json", ".row-counts.json"]
        self.assertEqual(backup.counts_name("welldb-20261110-0315.dump"), ".welldb-20261110-0315.dump.counts.json")
        self.assertEqual(backup.orphan_counts_files(names), [".welldb-20261101-0315.dump.counts.json"])


class ConnectionTests(unittest.TestCase):
    def test_parses_the_apps_url_and_strips_the_driver(self):
        s = backup.parse_database_url("postgresql+psycopg2://welluser:p%40ss%3Aw@host.docker.internal:5432/welldb"
                                      "?sslmode=require")
        self.assertEqual((s["host"], s["port"], s["user"], s["password"], s["database"]),
                         ("host.docker.internal", 5432, "welluser", "p@ss:w", "welldb"))
        with backup.libpq_env(s, base_env={"PGPASSWORD": "stale", "PATH": "/bin"}) as env:
            self.assertEqual((env["PGHOST"], env["PGPORT"], env["PGUSER"], env["PGDATABASE"], env["PGSSLMODE"]),
                             ("host.docker.internal", "5432", "welluser", "welldb", "require"))
            self.assertNotIn("PGPASSWORD", env)
            passfile = env["PGPASSFILE"]
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(os.stat(passfile).st_mode), 0o600)
            with open(passfile) as f:
                self.assertEqual(f.read(), "*:*:*:*:p@ss\\:w\n")
            self.assertNotIn("p@ss", " ".join(v for k, v in env.items() if k != "PGPASSFILE"))
        self.assertFalse(os.path.exists(passfile))

    def test_pgpass_escapes_backslash_and_colon(self):
        self.assertEqual(backup.pgpass_line("a\\b:c"), "*:*:*:*:a\\\\b\\:c\n")

    def test_bad_urls_never_echo_the_password(self):
        for url in ("", "sqlite:///x.db", "postgresql://u:secret@h", "postgresql://u:secret@h:notaport/db"):
            with self.subTest(url=url), self.assertRaises(ValueError) as caught:
                backup.parse_database_url(url)
            self.assertNotIn("secret", str(caught.exception))


class ListingTests(unittest.TestCase):
    def test_counts_table_data_entries(self):
        self.assertEqual(backup.table_data_entries(LISTING), [
            ("public", "sensor_measurements"), ("public", "sampling_measurements"), ("public", "schema_migrations")])
        self.assertEqual(backup.missing_tables(LISTING, ["sensor_measurements", "public.sampling_measurements"]), [])
        self.assertEqual(backup.missing_tables(LISTING, ["sensor_measurements", "export_jobs"]), ["export_jobs"])


class RowCountTests(unittest.TestCase):
    """The comparison of the key tables' rows with the last good backup's (pg_dump lists data for an empty table)."""

    def test_growth_and_small_drops_pass(self):
        before = {"sensor_measurements": 1_000_000, "sampling_measurements": 300}
        self.assertEqual(backup.row_count_problems({"sensor_measurements": 1_000_500, "sampling_measurements": 300},
                                                   before, 5), [])
        self.assertEqual(backup.row_count_problems({"sensor_measurements": 960_000, "sampling_measurements": 290},
                                                   before, 5), [])   # 4% and 3.3% fewer: within the estimate's drift

    def test_an_emptied_or_shrunk_table_fails(self):
        before = {"sensor_measurements": 1_000_000, "sampling_measurements": 300}
        problems = backup.row_count_problems({"sensor_measurements": 900_000, "sampling_measurements": 0}, before, 5)
        self.assertEqual(problems, [
            "sensor_measurements has 900,000 rows, 10% fewer than the 1,000,000 it had at a good backup",
            "sampling_measurements is empty (it had 300 rows at a good backup)"])

    def test_without_an_earlier_count_only_an_empty_or_missing_table_fails(self):
        self.assertEqual(backup.row_count_problems({"a": 5, "b": 0, "c": None}, {}, 5),
                         ["b is empty", "c does not exist"])

    def test_an_accepted_empty_table_stays_accepted(self):
        self.assertEqual(backup.row_count_problems({"sampling_measurements": 0}, {"sampling_measurements": 0}, 5), [])

    def test_counts_are_saved_and_read_back(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(backup.load_row_counts(directory), {})
            backup.save_row_counts(directory, {"a": 12, "missing": None}, "welldb-20261111-0315.dump",
                                   dt.datetime(2026, 11, 11, 3, 15))
            self.assertEqual(backup.load_row_counts(directory), {"a": 12})
            self.assertEqual(os.listdir(directory), [backup.ROW_COUNTS_NAME])   # no temporary file left
            pathlib.Path(directory, backup.ROW_COUNTS_NAME).write_text("not json")
            with self.assertRaises(ValueError):
                backup.load_row_counts(directory)

    def test_the_setting(self):
        import backup_db
        for raw, expected in (("", backup.DEFAULT_MAX_SHRINK_PCT), (" OFF ", None), ("20", 20)):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"BACKUP_MAX_SHRINK_PCT": raw}):
                self.assertEqual(backup_db.shrink_setting(), expected)
        with mock.patch.dict(os.environ, {"BACKUP_MAX_SHRINK_PCT": "five"}), self.assertRaises(backup_db.BackupError):
            backup_db.shrink_setting()

    def test_the_reference_only_goes_down_when_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            when = dt.datetime(2026, 11, 11, 3, 15)
            backup.save_row_counts(directory, {"a": 100, "b": 5}, "welldb-20261111-0315.dump", when)
            backup.save_row_counts(directory, {"a": 96, "b": 7}, "welldb-20261112-0315.dump", when)
            self.assertEqual(backup.load_row_counts(directory), {"a": 100, "b": 7})   # the most each had
            backup.save_row_counts(directory, None, "welldb-20261113-0315.dump", when)   # nothing counted: kept
            self.assertEqual(backup.load_row_counts(directory), {"a": 100, "b": 7})
            backup.save_row_counts(directory, {"a": 96, "b": 7}, "welldb-20261114-0315.dump", when, lower=True)
            self.assertEqual(backup.load_row_counts(directory), {"a": 96, "b": 7})

    def test_small_losses_cant_add_up_night_after_night(self):
        import backup_db
        with tempfile.TemporaryDirectory() as directory:
            self.nightly(directory, 8, 100)
            self.nightly(directory, 9, 96)    # 4% fewer: within BACKUP_MAX_SHRINK_PCT, and the reference stays 100
            self.nightly(directory, 10, 97)
            with self.assertRaises(backup_db.RowCountError) as failed:
                self.nightly(directory, 11, 93)   # 7% below the 100, though only 4% below the night before
            self.assertIn("t has 93 rows, 7% fewer than the 100 it had at a good backup", str(failed.exception))
            self.assertEqual(backup.load_row_counts(directory), {"t": 100})

    def test_a_count_that_fails_or_times_out_still_takes_the_dump_then_fails(self):
        import backup_db
        import psycopg2
        with tempfile.TemporaryDirectory() as directory:
            self.nightly(directory, 8, 100)
            timeout = psycopg2.extensions.QueryCanceledError("canceling statement due to statement timeout")
            with self.assertRaises(backup_db.RowCountError) as failed:
                self.nightly(directory, 9, 100, count_error=timeout)
            self.assertIn("the row counts could not be checked: could not count the rows of t: canceling statement",
                          str(failed.exception))
            self.assertEqual(self.dumps(directory), ["welldb-20261108-0315.dump", "welldb-20261109-0315.dump"])
            record = backup.load_record(directory)
            self.assertEqual((record["dump"], record["failing_dumps"]),
                             ("welldb-20261108-0315.dump", ["welldb-20261109-0315.dump"]))
            # With the comparison off, a failed count is only a warning, and the dump counts as good
            warnings = []
            self.nightly(directory, 10, 100, max_shrink_pct=None, count_error=timeout, warn=warnings.append)
            self.assertEqual(len(warnings), 1, warnings)
            self.assertEqual(backup.load_record(directory)["dump"], "welldb-20261110-0315.dump")

    def test_a_damaged_record_still_takes_the_dump_and_accepting_replaces_it(self):
        import backup_db
        with tempfile.TemporaryDirectory() as directory:
            self.nightly(directory, 8, 100)
            pathlib.Path(directory, backup.ROW_COUNTS_NAME).write_text("")   # zero-length, as after a power cut
            for day in (9, 10):
                with self.assertRaises(backup_db.RowCountError) as failed:
                    self.nightly(directory, day, 100)
                self.assertIn("can't be read", str(failed.exception))
                self.assertIn("--accept-row-counts", str(failed.exception))
                self.assertIn(f"welldb-202611{day:02d}-0315.dump", self.dumps(directory))
            self.nightly(directory, 11, 100, accept_row_counts=True)
            record = backup.load_record(directory)
            self.assertEqual((record["dump"], record["counts"]), ("welldb-20261111-0315.dump", {"t": 100}))

    def test_each_dump_gets_its_source_counts_beside_it(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = self.nightly(directory, 8, 1234, exact_tables={"t"})
            self.assertEqual(backup.load_dump_counts(dump), ({"t": 1234}, {"t"}))
            self.assertIsNone(backup.load_dump_counts(pathlib.Path(directory, "welldb-20200101-0000.dump")))
            pathlib.Path(directory, backup.counts_name(dump.name)).write_text("{\"counts\": [1]}")
            with self.assertRaises(ValueError):
                backup.load_dump_counts(dump)

    def test_a_full_disk_applies_retention_first_and_checks_again(self):
        import backup_db
        made_room = []
        short = backup_db.BackupError("not enough disk space in /x: 1 GB free")
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(backup_db, "check_free_space", side_effect=[short, None]):
                self.nightly(directory, 8, 100, make_room=lambda: made_room.append(1))
            self.assertEqual(made_room, [1])
            self.assertEqual(self.dumps(directory), ["welldb-20261108-0315.dump"])
            # Still too full after retention: no dump
            with mock.patch.object(backup_db, "check_free_space", side_effect=[short, short]), \
                    self.assertRaises(backup_db.BackupError):
                self.nightly(directory, 9, 100, make_room=lambda: made_room.append(1))
            # And without retention allowed (--no-prune), the first check decides
            with mock.patch.object(backup_db, "check_free_space", side_effect=[short]), \
                    self.assertRaises(backup_db.BackupError):
                self.nightly(directory, 10, 100)
            self.assertEqual(self.dumps(directory), ["welldb-20261108-0315.dump"])

    def test_retention_keeps_the_last_good_dump_and_recent_ones_and_drops_orphan_count_files(self):
        import backup_db
        with tempfile.TemporaryDirectory() as directory:
            for day in range(1, 12):
                pathlib.Path(directory, f"welldb-202611{day:02d}-0315.dump").write_text("x")
            pathlib.Path(directory, "welldb-20261111-0100.dump").write_text("x")   # by hand, before a change
            pathlib.Path(directory, backup.counts_name("welldb-20261031-0315.dump")).write_text("{}")   # orphan
            pathlib.Path(directory, backup.counts_name("welldb-20261101-0315.dump")).write_text("{}")
            backup.save_record(directory, {"dump": "welldb-20261101-0315.dump"})
            deleted = backup_db.prune(directory, 7, 0, log=lambda *a: None,
                                      now=dt.datetime(2026, 11, 11, 3, 20, tzinfo=backup_db.SITE_TZ))
            self.assertEqual(deleted, [f"welldb-202611{day:02d}-0315.dump" for day in (2, 3, 4)])
            names = os.listdir(directory)
            self.assertIn("welldb-20261101-0315.dump", names)
            self.assertIn("welldb-20261111-0100.dump", names)
            self.assertIn(backup.counts_name("welldb-20261101-0315.dump"), names)
            self.assertNotIn(backup.counts_name("welldb-20261031-0315.dump"), names)

    def nightly(self, directory, day, rows, max_shrink_pct=5, count_error=None, exact_tables=(), warn=None,
                **kwargs):
        """back_up() on 2026-11-`day` at 03:15 with `rows` in the table (or counting raising `count_error`), pg_dump
        and its check stood in for."""
        import backup_db

        def fake_dump(cmd, env, timeout):
            pathlib.Path(next(c for c in cmd if c.startswith("--file=")).split("=", 1)[1]).write_text("dump")

        def fake_count(settings, tables, warn=None, exact=None):
            if count_error:
                raise count_error
            if exact is not None:
                exact.update(set(exact_tables))
            return {"t": rows}

        with mock.patch.object(backup_db, "count_rows", side_effect=fake_count), \
                mock.patch.object(backup_db, "run_tool", side_effect=fake_dump), \
                mock.patch.object(backup_db, "verify_dump"), \
                mock.patch.object(backup_db, "pg_tool", return_value="pg_dump"):
            return backup_db.back_up(directory, {"database": "welldb"}, [], ["t"], 0, log=lambda *a: None,
                                     warn=warn or (lambda *a: None), now=dt.datetime(2026, 11, day, 3, 15),
                                     max_shrink_pct=max_shrink_pct, **kwargs)

    def dumps(self, directory):
        return sorted(name for _, name in backup.dumps_in(os.listdir(directory)))

    def test_while_the_check_fails_only_the_newest_failing_dump_is_kept(self):
        import backup_db
        with tempfile.TemporaryDirectory() as directory:
            self.nightly(directory, 8, 100)
            self.nightly(directory, 9, 100)
            for day in (10, 11, 12):
                with self.assertRaises(backup_db.RowCountError) as failed:
                    self.nightly(directory, day, 0)
                self.assertIn("t is empty (it had 100 rows at a good backup)", str(failed.exception))
            self.assertEqual(self.dumps(directory),
                             ["welldb-20261108-0315.dump", "welldb-20261109-0315.dump", "welldb-20261112-0315.dump"])
            self.assertEqual(backup.load_record(directory)["failing_dumps"], ["welldb-20261112-0315.dump"])
            # --no-prune deletes nothing, and both stay marked as failing
            with self.assertRaises(backup_db.RowCountError):
                self.nightly(directory, 13, 0, prune_failing=False)
            self.assertEqual(len(self.dumps(directory)), 4)
            self.assertEqual(backup.load_record(directory)["failing_dumps"],
                             ["welldb-20261112-0315.dump", "welldb-20261113-0315.dump"])
            # Accepted: recorded as the last good backup, nothing marked as failing any more
            self.nightly(directory, 14, 0, accept_row_counts=True)
            record = backup.load_record(directory)
            self.assertEqual((record["dump"], record["failing_dumps"]), ("welldb-20261114-0315.dump", []))

    def test_dumps_made_with_the_check_off_are_never_deleted_by_it(self):
        import backup_db
        with tempfile.TemporaryDirectory() as directory:
            self.nightly(directory, 8, 100)
            for day in (9, 10, 11):   # the comparison turned off; the rows went down meanwhile
                self.nightly(directory, day, 10, max_shrink_pct=None)
            record = backup.load_record(directory)
            self.assertEqual((record["dump"], record["counts"]), ("welldb-20261111-0315.dump", {"t": 100}))
            for day in (12, 13):   # on again, and failing
                with self.assertRaises(backup_db.RowCountError):
                    self.nightly(directory, day, 10)
            self.assertEqual(self.dumps(directory), [f"welldb-202611{d:02d}-0315.dump" for d in (8, 9, 10, 11, 13)])

    def test_a_marked_name_that_isnt_a_dump_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "notes.txt").write_text("keep")
            backup.save_record(directory, {"failing_dumps": ["notes.txt"]})
            backup.mark_failing(directory, "welldb-20261112-0315.dump", prune=True, log=lambda *a: None)
            self.assertTrue(pathlib.Path(directory, "notes.txt").exists())
            self.assertEqual(backup.load_record(directory)["failing_dumps"], ["welldb-20261112-0315.dump"])


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
        import scheduler_temp
        self.scheduler = scheduler_temp
        self.logs, self.pings, self.cmds = [], [], []
        patcher = mock.patch.object(scheduler_temp, "ping_heartbeat",
                                    side_effect=lambda name, status="success": self.pings.append((name, status)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def at(self, hour):
        when = dt.datetime(2026, 11, 11, hour, 15, tzinfo=self.scheduler.SITE_TZ)
        return mock.patch.object(self.scheduler, "datetime", mock.Mock(now=lambda tz=None: when))

    def run_check(self, hour, run):
        with self.at(hour), mock.patch.object(self.scheduler, "capture_job_error") as capture:
            ok = self.scheduler.nightly_backup_check(log=self.logs.append, run=run)
        return ok, capture

    def test_does_nothing_outside_its_hour(self):
        ok, _ = self.run_check(4, run=lambda cmd, timeout: self.fail("ran outside 03:00"))
        self.assertIsNone(ok)
        self.assertEqual(self.pings, [])

    def test_success_pings_start_then_success(self):
        def run(cmd, timeout):
            self.cmds.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "Backup written: /app/backups/x.dump", "")
        ok, capture = self.run_check(3, run)
        self.assertTrue(ok)
        self.assertEqual(self.cmds[0][1:], ["scripts/backup_db.py"])
        self.assertEqual(self.pings, [("backup", "start"), ("backup", "success")])
        capture.assert_not_called()

    def test_failure_and_timeout_ping_fail_and_report(self):
        for error in (subprocess.CalledProcessError(1, ["x"], output="", stderr="ERROR: backup failed: disk"),
                      subprocess.TimeoutExpired(["x"], 7200, output="")):
            self.pings.clear()

            def run(cmd, timeout, error=error):
                raise error
            with self.subTest(error=type(error).__name__):
                ok, capture = self.run_check(3, run)
                self.assertFalse(ok)
                self.assertEqual(self.pings, [("backup", "start"), ("backup", "fail")])
                capture.assert_called_once_with(error)

    def test_a_retention_warning_is_still_a_success_and_goes_to_sentry_as_a_warning(self):
        warning = "WARNING: the backup is fine, but deleting old dumps failed: [Errno 13] Permission denied"
        with mock.patch.object(self.scheduler, "capture_job_warning") as warn:
            ok, capture = self.run_check(3, lambda cmd, timeout: subprocess.CompletedProcess(cmd, 0, "", warning))
        self.assertTrue(ok)
        self.assertEqual(self.pings, [("backup", "start"), ("backup", "success")])
        warn.assert_called_once_with(warning)
        capture.assert_not_called()

    def test_the_steps_fit_inside_the_schedulers_limit(self):
        import backup_db
        steps = backup_db.DUMP_TIMEOUT_S + backup_db.LIST_TIMEOUT_S + backup_db.READ_BACK_TIMEOUT_S
        self.assertLessEqual(steps + 10 * 60, self.scheduler.BACKUP_TIMEOUT_S)


FAKE_PG_DUMP = """#!/bin/sh
# Stands in for pg_dump: writes a few bytes to --file, notes its password file, then waits for $FAKE_DUMP_SLEEP s
for arg in "$@"; do case "$arg" in --file=*) out="${arg#--file=}";; esac; done
printf 'PGDMP' > "$out"
echo "$PGPASSFILE" > "$FAKE_MARKER"
exec sleep "${FAKE_DUMP_SLEEP:-0}"
"""
FAKE_PG_RESTORE = """#!/bin/sh
# Stands in for pg_restore: --list prints a listing with the main tables' data; reading the archive succeeds
if [ "$1" = "--list" ]; then cat "$FAKE_LISTING"; fi
exit 0
"""


@unittest.skipUnless(os.name == "posix", "needs POSIX signals and shell scripts")
class ScriptTests(unittest.TestCase):
    """backup_db.py end to end, with stand-ins for pg_dump and pg_restore (no database needed)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.bin, self.dir, self.temp = root / "bin", root / "backups", root / "tmp"
        for path in (self.bin, self.dir, self.temp):
            path.mkdir()
        for name, text in (("pg_dump", FAKE_PG_DUMP), ("pg_restore", FAKE_PG_RESTORE)):
            (self.bin / name).write_text(text)
            (self.bin / name).chmod(0o755)
        (root / "listing").write_text(LISTING)
        self.marker = root / "passfile-used"
        self.env = {**os.environ, "PG_BIN_DIR": str(self.bin), "TMPDIR": str(self.temp), "SENTRY_DSN": "",
                    "DATABASE_URL": "postgresql+psycopg2://welluser:s3cret@127.0.0.1:1/welldb",
                    "BACKUP_EXCLUDE_TABLES": "",   # nothing to exclude, so no catalog lookup (no database here)
                    "BACKUP_MAX_SHRINK_PCT": "off",   # no row counts either (RowCountTests and RoundTrip cover them)
                    "BACKUP_MIN_FREE_MB": "0", "FAKE_LISTING": str(root / "listing"), "FAKE_MARKER": str(self.marker)}

    def start(self, *args, **env):
        return subprocess.Popen([sys.executable, str(APP / "scripts" / "backup_db.py"), "--dir", str(self.dir), *args],
                                env={**self.env, **env}, cwd=APP, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)

    def passfiles(self):
        folder = self.temp / backup.PASSFILE_DIR_NAME
        return sorted(os.listdir(folder)) if folder.exists() else []

    def test_a_run_deletes_what_a_killed_run_left_and_only_that(self):
        leftovers = [".welldb-20261101-0315.dump.partial"]
        others = [".welldb-notes.partial", "welldb-20261101-0315.dump.partial", "notes.txt"]
        for name in leftovers + others:
            (self.dir / name).write_text("x")
        folder = self.temp / backup.PASSFILE_DIR_NAME
        folder.mkdir(mode=0o700)
        old, recent = folder / "pgpass-old", folder / "pgpass-recent"
        for path in (old, recent):
            path.write_text("*:*:*:*:pw\n")
        os.utime(old, (0, 0))
        out, err = self.start("--no-prune").communicate(timeout=60)
        self.assertIn("Backup written", out, err)
        names = os.listdir(self.dir)
        self.assertEqual(set(leftovers) & set(names), set())
        self.assertLessEqual(set(others), set(names))
        self.assertEqual(self.passfiles(), ["pgpass-recent"])   # its own file is gone too

    def test_sigterm_cleans_up_the_partial_dump_and_the_password_file(self):
        proc = self.start("--no-prune", FAKE_DUMP_SLEEP="60")
        for _ in range(200):
            if self.marker.exists() and self.marker.read_text().strip():
                break
            proc.poll()
            self.assertIsNone(proc.returncode, proc.stderr.read() if proc.returncode is not None else "")
            subprocess.run(["sleep", "0.05"])
        passfile = self.marker.read_text().strip()
        self.assertTrue(os.path.exists(passfile))
        self.assertTrue(any(n.endswith(".partial") for n in os.listdir(self.dir)))
        proc.terminate()
        proc.communicate(timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(passfile))
        self.assertEqual([n for n in os.listdir(self.dir) if n != backup_lock_name()], [])

    def test_only_one_run_at_a_time(self):
        first = self.start("--no-prune", FAKE_DUMP_SLEEP="60")
        try:
            for _ in range(200):
                if self.marker.exists():
                    break
                subprocess.run(["sleep", "0.05"])
            out, err = self.start("--no-prune").communicate(timeout=60)
            self.assertIn("another backup is running", err)
        finally:
            first.terminate()
            first.communicate(timeout=30)

    def test_a_failed_prune_after_a_good_backup_is_a_warning(self):
        import backup_db
        with mock.patch.object(backup_db, "back_up"), mock.patch.object(backup_db, "prepare_dir"), \
                mock.patch.object(backup_db, "prune", side_effect=PermissionError(13, "Permission denied")), \
                mock.patch.dict(os.environ, self.env), \
                mock.patch.object(backup_db.signal, "signal"), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(backup_db.main(["--dir", str(self.dir)]), 0)
            self.assertIn("WARNING: the backup is fine", err.getvalue())
            self.assertEqual(backup_db.main(["--dir", str(self.dir), "--prune-only"]), 1)


def backup_lock_name():
    import backup_db
    return backup_db.LOCK_NAME


class RestoreCheckGuardTests(unittest.TestCase):
    def test_refuses_a_database_name_without_the_prefix(self):
        env = {**os.environ, "DATABASE_URL": "postgresql://u:p@127.0.0.1:1/welldb", "SENTRY_DSN": ""}
        for name in ("welldb", "postgres", "Welldb_restore_check", "welldb_restore_check; DROP"):
            with self.subTest(name=name):
                done = subprocess.run([sys.executable, str(APP / "scripts" / "restore_check.py"), "--database", name],
                                      env=env, cwd=APP, capture_output=True, text=True, timeout=60)
                self.assertEqual(done.returncode, 1)
                self.assertIn("must start with welldb_restore_check", done.stderr)


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the backup round trip against "
                                                     "PostgreSQL")
class RoundTrip(unittest.TestCase):
    """Seed a database owned by an unprivileged role, with two tables it can't read (as export_jobs and data_fixes
    are on the VM), back it up as that role with the script, restore the dump into a new database with the restore
    drill, and check every row came back."""
    ROLE = "backup_test_owner"
    PASSWORD = "p:w\\d@x"   # a colon and a backslash, which the password file must escape
    SOURCE = "backup_test_source"
    RESTORED = "welldb_restore_check_test"

    @classmethod
    def setUpClass(cls):
        import psycopg2
        from sqlalchemy.engine import make_url
        cls.psycopg2 = psycopg2
        cls.admin_url = make_url(os.environ["TEST_POSTGRES_URL"])
        cls.admin = backup.parse_database_url(os.environ["TEST_POSTGRES_URL"])
        cls.cleanup()
        cls.admin_sql(f"CREATE ROLE {cls.ROLE} LOGIN PASSWORD %s", (cls.PASSWORD,))
        cls.admin_sql(f"CREATE DATABASE {cls.SOURCE} OWNER {cls.ROLE}")
        conn = psycopg2.connect(**backup.psycopg2_kwargs(backup.with_database(cls.admin, cls.SOURCE)))
        with conn, conn.cursor() as cur:
            # The postgres role's tables, which the owner role can't read
            cur.execute("CREATE TABLE export_jobs (id serial PRIMARY KEY, status text)")
            cur.execute("INSERT INTO export_jobs (status) VALUES ('done')")
            cur.execute("CREATE TABLE data_fixes (id serial PRIMARY KEY, note text)")
            cur.execute(f"SET ROLE {cls.ROLE}")
            cur.execute("CREATE TABLE sensor_measurements (id bigserial PRIMARY KEY, station_id int, "
                        "measurement_type text, value double precision, recorded_at timestamp)")
            cur.execute("CREATE TABLE sampling_measurements (id serial PRIMARY KEY, site text, value numeric)")
            cur.execute("CREATE TABLE schema_migrations (version varchar(255) PRIMARY KEY)")
            cur.execute("INSERT INTO sensor_measurements (station_id, measurement_type, value, recorded_at) "
                        "SELECT 21079936, 'Temperature', g * 0.5, timestamp '2026-11-01' + g * interval '10 min' "
                        "FROM generate_series(1, 500) g")
            cur.execute("INSERT INTO sampling_measurements (site, value) VALUES ('Site 1', 1.25), ('Site 2', NULL)")
            cur.execute("INSERT INTO schema_migrations VALUES ('0001_example')")
        conn.close()
        cls.owner_url = cls.admin_url.set(username=cls.ROLE, password=cls.PASSWORD, database=cls.SOURCE,
                                          drivername="postgresql+psycopg2").render_as_string(hide_password=False)

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    @classmethod
    def admin_sql(cls, statement, params=None):
        conn = cls.psycopg2.connect(**backup.psycopg2_kwargs(cls.admin))
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(statement, params)
        conn.close()

    @classmethod
    def cleanup(cls):
        for db in (cls.RESTORED, cls.SOURCE):
            cls.admin_sql(f"DROP DATABASE IF EXISTS {db}")
        cls.admin_sql(f"DROP ROLE IF EXISTS {cls.ROLE}")

    def rows(self, database, table):
        conn = self.psycopg2.connect(**backup.psycopg2_kwargs(backup.with_database(self.admin, database)))
        with conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} ORDER BY 1")
            rows = cur.fetchall()
        conn.close()
        return rows

    def run_script(self, script, *args, **env):
        environ = {**os.environ, "DATABASE_URL": self.owner_url, "SENTRY_DSN": "", "BACKUP_MIN_FREE_MB": "0", **env}
        return subprocess.run([sys.executable, str(APP / "scripts" / script), *args], env=environ, cwd=APP,
                              capture_output=True, text=True, timeout=300)

    def test_backup_then_restore_brings_back_every_row(self):
        with tempfile.TemporaryDirectory() as directory:
            done = self.run_script("backup_db.py", "--dir", directory, BACKUP_MIN_FREE_MB="0")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn(self.PASSWORD, done.stdout + done.stderr)
            dumps = [name for _, name in backup.dumps_in(os.listdir(directory))]
            self.assertEqual(len(dumps), 1, dumps)
            self.assertIsNotNone(backup.dump_time(dumps[0]))
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(directory, dumps[0])).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(directory).st_mode), 0o700)
            self.assertIn("Checked: 3 tables with data", done.stdout)
            # By default the tables (and the sequence) this role can't read are left out, and named in a warning
            warning = [line for line in done.stderr.splitlines() if line.startswith("WARNING:")]
            self.assertEqual(len(warning), 1, done.stderr)
            for name in ("public.data_fixes", "public.export_jobs", "public.export_jobs_id_seq"):
                self.assertIn(name, warning[0])

            # The restore drill, as a superuser (the owner role has no CREATEDB), comparing with the live counts
            drill = self.run_script("restore_check.py", "--dir", directory, "--database", self.RESTORED, "--keep",
                                    RESTORE_CHECK_DATABASE_URL=os.environ["TEST_POSTGRES_URL"])
            self.assertEqual(drill.returncode, 0, drill.stdout + drill.stderr)
            self.assertIn("Restore check passed", drill.stdout)
            self.assertIn("public.export_jobs", drill.stdout)   # listed as left out (unreadable), not a failure
            self.assertIn("can't read it", drill.stdout)
            for table in ("sensor_measurements", "sampling_measurements", "schema_migrations"):
                self.assertEqual(self.rows(self.RESTORED, table), self.rows(self.SOURCE, table), table)
            self.assertEqual(len(self.rows(self.RESTORED, "sensor_measurements")), 500)
            self.admin_sql(f"DROP DATABASE {self.RESTORED}")
            # The counts taken just before the dump are beside it, exact for these small tables, and the drill
            # compared the restore with them
            dump = os.path.join(directory, dumps[0])
            self.assertEqual(backup.load_dump_counts(dump),
                             ({"sensor_measurements": 500, "sampling_measurements": 2},
                              {"sensor_measurements", "sampling_measurements"}))
            self.assertIn("Row counts when", drill.stdout)

            # A dump that restores fewer rows than its source had (here: its record says so) fails the drill, and
            # the throwaway database is dropped
            record_path = pathlib.Path(directory, backup.counts_name(dumps[0]))
            record = record_path.read_text()
            record_path.write_text(record.replace('"sensor_measurements": 500', '"sensor_measurements": 2400000'))
            short = self.run_script("restore_check.py", "--dir", directory, "--database", self.RESTORED,
                                    RESTORE_CHECK_DATABASE_URL=os.environ["TEST_POSTGRES_URL"])
            self.assertEqual(short.returncode, 1, short.stdout + short.stderr)
            self.assertIn("sensor_measurements restored 500 rows, but had 2,400,000 when the dump was taken",
                          short.stderr)
            self.assertIn("Dropped the throwaway database", short.stdout)
            # Without its record, the drill compares with the live rows instead (shortfalls covers a failure there)
            record_path.unlink()
            fallback = self.run_script("restore_check.py", "--dir", directory, "--database", self.RESTORED,
                                       RESTORE_CHECK_DATABASE_URL=os.environ["TEST_POSTGRES_URL"])
            self.assertEqual(fallback.returncode, 0, fallback.stdout + fallback.stderr)
            self.assertIn("has no record of its source's row counts", fallback.stdout)
            record_path.write_text(record)

            # Without the exclusions the owner role can't lock export_jobs: the run fails and leaves no file behind
            failed = self.run_script("backup_db.py", "--dir", directory, "--no-prune", BACKUP_MIN_FREE_MB="0",
                                     BACKUP_EXCLUDE_TABLES="")
            self.assertEqual(failed.returncode, 1)
            self.assertIn("permission denied", failed.stderr)
            self.assertEqual(sorted(n for n in os.listdir(directory) if not n.startswith(".")), dumps)

    def listing(self, path):
        return subprocess.run([backup.pg_tool("pg_restore"), "--list", path], capture_output=True, text=True,
                              check=True).stdout

    def test_a_role_that_reads_everything_dumps_everything_without_a_warning(self):
        superuser = self.admin_url.set(database=self.SOURCE).render_as_string(hide_password=False)
        with tempfile.TemporaryDirectory() as directory:
            done = self.run_script("backup_db.py", "--dir", directory, DATABASE_URL=superuser)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn("WARNING", done.stderr)
            self.assertIn("every table", done.stdout)
            dump = os.path.join(directory, backup.dumps_in(os.listdir(directory))[0][1])
            tables = {table for _, table in backup.table_data_entries(self.listing(dump))}
            self.assertLessEqual({"export_jobs", "data_fixes", "sensor_measurements"}, tables)

    def test_an_explicit_list_overrides_auto(self):
        with tempfile.TemporaryDirectory() as directory:
            done = self.run_script("backup_db.py", "--dir", directory, BACKUP_EXCLUDE_TABLES="export_jobs,data_fixes")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn("WARNING", done.stderr)   # left out on purpose: nothing to warn about

    def test_restore_check_without_createdb_explains(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_script("backup_db.py", "--dir", directory, BACKUP_MIN_FREE_MB="0").returncode, 0)
            drill = self.run_script("restore_check.py", "--dir", directory, "--database", self.RESTORED)
            self.assertEqual(drill.returncode, 1)
            self.assertIn("CREATEDB", drill.stderr)

    def source_sql(self, statement):
        """Run `statement` in the source database as the owner role."""
        conn = self.psycopg2.connect(**backup.psycopg2_kwargs(backup.with_database(self.admin, self.SOURCE)))
        with conn, conn.cursor() as cur:
            cur.execute(f"SET ROLE {self.ROLE}")
            cur.execute(statement)
        conn.close()

    def test_an_emptied_or_shrunk_table_fails_the_backup_until_accepted(self):
        # A table of its own (BACKUP_EXPECT_TABLES), so the other tests' data stays as it is
        self.source_sql("CREATE TABLE shrink_check (id int); INSERT INTO shrink_check SELECT generate_series(1, 100)")
        self.addCleanup(self.source_sql, "DROP TABLE IF EXISTS shrink_check")
        expect = {"BACKUP_EXPECT_TABLES": "shrink_check,sensor_measurements"}
        with tempfile.TemporaryDirectory() as directory:
            def dumps():
                return [name for _, name in backup.dumps_in(os.listdir(directory))]

            def run(*args):
                return self.run_script("backup_db.py", "--dir", directory, *args, **expect)

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("Rows now: shrink_check 100, sensor_measurements 500 (reference, the most at a good backup: "
                          "no earlier count", first.stdout)
            self.assertEqual(backup.load_row_counts(directory), {"shrink_check": 100, "sensor_measurements": 500})

            # 4% fewer rows passes (within BACKUP_MAX_SHRINK_PCT's default 5%), but the reference stays at 100, so
            # losses can't add up night after night
            self.source_sql("DELETE FROM shrink_check WHERE id <= 4")
            self.assertEqual(run("--no-prune").returncode, 0)
            self.assertEqual(backup.load_row_counts(directory)["shrink_check"], 100)
            self.source_sql("DELETE FROM shrink_check WHERE id <= 6")   # 6% below the reference, 2% below last night
            crept = run("--no-prune")
            self.assertEqual(crept.returncode, 1)
            self.assertIn("shrink_check has 94 rows, 6% fewer than the 100 it had at a good backup", crept.stderr)

            # 50% fewer: the dump is written and checked, but the run fails and the counts aren't recorded
            self.source_sql("DELETE FROM shrink_check WHERE id <= 52")
            # A large table is counted by its estimate, refreshed by an ANALYZE first, so a DELETE that autovacuum
            # hasn't seen yet still shows (exact_limit=0 takes that path even for this small table)
            owner = backup.parse_database_url(self.owner_url)
            self.assertEqual(backup.count_rows(owner, ["shrink_check"], exact_limit=0), {"shrink_check": 48})
            # If ANALYZE can't get its lock (here held by another session, as a long VACUUM would), the older
            # estimate is used, with a warning, instead of failing the backup
            blocker = self.psycopg2.connect(**backup.psycopg2_kwargs(backup.with_database(self.admin, self.SOURCE)))
            self.addCleanup(blocker.close)
            blocker.cursor().execute("LOCK TABLE shrink_check IN SHARE UPDATE EXCLUSIVE MODE")
            warnings = []
            self.assertEqual(backup.count_rows(owner, ["shrink_check"], exact_limit=0, warn=warnings.append,
                                               analyze_lock_timeout="200ms"), {"shrink_check": 48})
            blocker.rollback()
            self.assertEqual(len(warnings), 1, warnings)
            self.assertIn("ANALYZE public.shrink_check failed", warnings[0])
            self.assertIn("lock timeout", warnings[0])
            shrunk = run()
            self.assertEqual(shrunk.returncode, 1)
            self.assertIn("shrink_check has 48 rows, 52% fewer than the 100 it had at a good backup", shrunk.stderr)
            self.assertIn("--accept-row-counts", shrunk.stderr)
            self.assertIn("Backup written", shrunk.stdout)
            self.assertEqual(backup.load_row_counts(directory)["shrink_check"], 100)

            # Emptied: still failing, also on the next run
            self.source_sql("TRUNCATE shrink_check")
            for _ in range(2):
                emptied = run("--no-prune")
                self.assertEqual(emptied.returncode, 1)
                self.assertIn("shrink_check is empty (it had 100 rows at a good backup)", emptied.stderr)

            # Accepted on purpose: a warning, the new counts recorded, and the next run passes
            accepted = run("--no-prune", "--accept-row-counts")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertIn("WARNING: row counts accepted with --accept-row-counts: shrink_check is empty", accepted.stderr)
            self.assertEqual(backup.load_row_counts(directory)["shrink_check"], 0)
            self.assertEqual(run("--no-prune").returncode, 0)
            self.assertTrue(dumps())

    def test_a_check_that_cant_be_made_still_takes_the_dump(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.run_script("backup_db.py", "--dir", directory)
            self.assertEqual(first.returncode, 0, first.stderr)
            # A record left zero-length (renamed before it reached the disk, then a power cut): the dump is still
            # taken and checked, then the run fails and says what to do
            pathlib.Path(directory, backup.ROW_COUNTS_NAME).write_text("")
            # Dumps are named by the minute, so the first one goes first: the one left must be the new one
            for _, name in backup.dumps_in(os.listdir(directory)):
                os.remove(os.path.join(directory, name))
            damaged = self.run_script("backup_db.py", "--dir", directory, "--no-prune")
            self.assertEqual(damaged.returncode, 1)
            self.assertIn("the row counts could not be checked", damaged.stderr)
            self.assertIn("--accept-row-counts", damaged.stderr)
            self.assertIn("Backup written", damaged.stdout)
            self.assertEqual(len(backup.dumps_in(os.listdir(directory))), 1)
            fixed = self.run_script("backup_db.py", "--dir", directory, "--no-prune", "--accept-row-counts")
            self.assertEqual(fixed.returncode, 0, fixed.stderr)
            self.assertEqual(backup.load_row_counts(directory), {"sensor_measurements": 500, "sampling_measurements": 2})
            # (A count stopped by its time limit takes the same path: RowCountTests covers it without a 5 min wait.)


class ExclusionSettingTests(unittest.TestCase):
    def test_unset_or_auto_means_auto_and_a_list_or_empty_is_explicit(self):
        self.assertEqual(backup.exclusion_setting({}), backup.AUTO_EXCLUDE)
        self.assertEqual(backup.exclusion_setting({"BACKUP_EXCLUDE_TABLES": " Auto "}), backup.AUTO_EXCLUDE)
        self.assertEqual(backup.exclusion_setting({"BACKUP_EXCLUDE_TABLES": ""}), [])
        self.assertEqual(backup.exclusion_setting({"BACKUP_EXCLUDE_TABLES": "export_jobs, data_fixes"}),
                         ["export_jobs", "data_fixes"])

    def test_the_drill_accepts_a_missing_table_only_when_it_was_meant_to_be_missing(self):
        import restore_check
        restored = {("public", "sensor_measurements"): 5}
        live = {("public", "sensor_measurements"): 6, ("public", "export_jobs"): restore_check.UNREADABLE,
                ("public", "alert_incidents"): 2}
        lines, problems = restore_check.compare(restored, live, backup.AUTO_EXCLUDE)
        self.assertEqual(problems, ["public.alert_incidents is missing from the backup"])
        self.assertTrue(any("can't read it" in line for line in lines), lines)
        _, problems = restore_check.compare(restored, live, ["alert_incidents"])
        self.assertEqual(problems, ["public.export_jobs is missing from the backup"])


class RestoreShortfallTests(unittest.TestCase):
    """The drill compares what it restored with the counts recorded beside the dump, not only with "not empty"."""
    SM, SAMPLING = ("public", "sensor_measurements"), ("public", "sampling_measurements")

    def test_a_nearly_empty_restore_fails(self):
        import restore_check
        restored, live = {self.SM: 10, self.SAMPLING: 300}, {self.SM: 2_400_000, self.SAMPLING: 300}
        recorded = ({"sensor_measurements": 2_399_000, "sampling_measurements": 300}, {"sampling_measurements"})
        _, problems = restore_check.compare(restored, live, [], recorded)
        self.assertEqual(problems, ["sensor_measurements restored 10 rows, but had 2,399,000 (estimated) when the dump "
                                    "was taken"])

    def test_an_estimate_has_a_tolerance_and_an_exact_count_none(self):
        import restore_check
        recorded = ({"sensor_measurements": 1_000_000, "sampling_measurements": 300}, {"sampling_measurements"})
        live = {self.SM: 1_001_000, self.SAMPLING: 300}
        # 1.5% under an estimate passes (the default tolerance is 2%); one row short of an exact count fails
        _, problems = restore_check.compare({self.SM: 985_000, self.SAMPLING: 300}, live, [], recorded)
        self.assertEqual(problems, [])
        _, problems = restore_check.compare({self.SM: 985_000, self.SAMPLING: 299}, live, [], recorded)
        self.assertEqual(problems, ["sampling_measurements restored 299 rows, but had 300 when the dump was taken"])
        _, problems = restore_check.compare({self.SM: 985_000, self.SAMPLING: 300}, live, [], recorded,
                                            tolerance_pct=1)
        self.assertEqual(len(problems), 1)

    def test_a_schema_qualified_name_matches_too(self):
        import restore_check
        _, problems = restore_check.compare({self.SM: 5}, {self.SM: 5}, [], ({"public.sensor_measurements": 6}, {
            "public.sensor_measurements"}))
        self.assertEqual(len(problems), 1)

    def test_without_a_record_the_main_tables_are_compared_with_live(self):
        import restore_check
        expected = ["sensor_measurements", "sampling_measurements"]
        live = {self.SM: 2_400_000, self.SAMPLING: 300, ("public", "alert_incidents"): 50}
        ok = {self.SM: 2_395_000, self.SAMPLING: 300, ("public", "alert_incidents"): 1}
        self.assertEqual(restore_check.compare(ok, live, [], None, expected)[1], [])   # other tables may differ
        _, problems = restore_check.compare({**ok, self.SM: 10}, live, [], None, expected)
        self.assertEqual(problems, ["sensor_measurements restored 10 rows, more than 5% fewer than the 2,400,000 live "
                                    "(the dump has no record of its own counts to compare with)"])


class RestoreSchedulerTests(unittest.TestCase):
    """The monthly restore drill's slot in the scheduler, with its own heartbeat."""

    def setUp(self):
        sys.modules.setdefault("inject_from_api", types.SimpleNamespace(inject_all_new_data=lambda: None))
        import scheduler_temp
        self.scheduler = scheduler_temp
        self.logs, self.pings, self.cmds = [], [], []
        patcher = mock.patch.object(scheduler_temp, "ping_heartbeat",
                                    side_effect=lambda name, status="success", **kw: self.pings.append((name, status)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_at(self, day, hour, run, setting="2"):
        when = dt.datetime(2026, 12, day, hour, 30, tzinfo=self.scheduler.SITE_TZ)
        with mock.patch.object(self.scheduler, "datetime", mock.Mock(now=lambda tz=None: when)), \
                mock.patch.object(self.scheduler, "RESTORE_CHECK_DAY", setting), \
                mock.patch.object(self.scheduler, "capture_job_error") as capture:
            return self.scheduler.monthly_restore_check(log=self.logs.append, run=run), capture

    def test_runs_only_at_its_hour_on_its_day(self):
        never = lambda cmd, timeout: self.fail("ran outside its slot")  # noqa: E731
        for day, hour in ((2, 4), (2, 6), (1, 5), (3, 5)):
            self.assertIsNone(self.run_at(day, hour, never)[0])
        self.assertIsNone(self.run_at(2, 5, never, setting="off")[0])
        self.assertEqual(self.pings, [])

    def test_success_and_failure_ping_the_restore_check(self):
        def ok(cmd, timeout):
            self.cmds.append((cmd, timeout))
            return subprocess.CompletedProcess(cmd, 0, "Restore check passed", "")

        def short(cmd, timeout):
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="ERROR: restore check failed: too few rows")

        self.assertTrue(self.run_at(2, 5, ok)[0])
        self.assertEqual(self.cmds[0][0][1:], ["scripts/restore_check.py"])
        self.assertEqual(self.cmds[0][1], self.scheduler.RESTORE_TIMEOUT_S)
        ran, capture = self.run_at(2, 5, short)
        self.assertFalse(ran)
        capture.assert_called_once()
        self.assertEqual(self.pings, [("restore", "start"), ("restore", "success"), ("restore", "start"),
                                      ("restore", "fail")])

    def test_a_bad_day_fails_once_a_day(self):
        never = lambda cmd, timeout: self.fail("ran with a bad setting")  # noqa: E731
        self.assertIsNone(self.run_at(2, 4, never, setting="31")[0])
        self.assertIsNone(self.run_at(2, 5, never, setting="31")[0])
        self.assertEqual(self.pings, [("restore", "fail")])

    def test_it_runs_after_the_backup_can_have_finished(self):
        start = self.scheduler.BACKUP_HOUR * 60 + 15
        self.assertLessEqual(start + self.scheduler.BACKUP_TIMEOUT_S // 60, self.scheduler.RESTORE_HOUR * 60 + 30)


if __name__ == "__main__":
    unittest.main()
