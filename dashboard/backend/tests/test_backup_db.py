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

            # Without the exclusions the owner role can't lock export_jobs: the run fails and leaves no file behind
            failed = self.run_script("backup_db.py", "--dir", directory, "--no-prune", BACKUP_MIN_FREE_MB="0",
                                     BACKUP_EXCLUDE_TABLES="")
            self.assertEqual(failed.returncode, 1)
            self.assertIn("permission denied", failed.stderr)
            self.assertEqual(sorted(n for n in os.listdir(directory) if n != ".backup.lock"), dumps)

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


if __name__ == "__main__":
    unittest.main()
