"""The nightly database backup (scripts/backup_db.py, utils/backup.py), its restore drill (scripts/restore_check.py)
and its slot in the scheduler. Run from dashboard/backend: python -m unittest discover -s tests -t .

RoundTrip runs pg_dump and pg_restore against PostgreSQL. It runs only when TEST_POSTGRES_URL points at a disposable
server reached as a superuser (CI's postgres:13 container), because it creates and drops a role and databases there;
never point it at a real one."""
import datetime as dt
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock as mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
from utils import backup  # noqa: E402

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


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the backup round trip against "
                                                     "PostgreSQL")
class RoundTrip(unittest.TestCase):
    """Seed a database owned by an unprivileged role, with two tables it can't read (as export_jobs and data_fixes
    are on the VM), back it up as that role with the script, restore the dump into a new database with the restore
    drill, and check every row came back."""
    ROLE = "backup_test_owner"
    PASSWORD = "p:w\\d@x"   # a colon and a backslash, which the password file must escape
    SOURCE = "backup_test_source"
    RESTORED = "backup_test_restored"

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
        environ = {**os.environ, "DATABASE_URL": self.owner_url, "SENTRY_DSN": "", **env}
        return subprocess.run([sys.executable, str(APP / "scripts" / script), *args], env=environ, cwd=APP,
                              capture_output=True, text=True, timeout=300)

    def test_backup_then_restore_brings_back_every_row(self):
        with tempfile.TemporaryDirectory() as directory:
            done = self.run_script("backup_db.py", "--dir", directory, BACKUP_MIN_FREE_MB="0")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn(self.PASSWORD, done.stdout + done.stderr)
            dumps = os.listdir(directory)
            self.assertEqual(len(dumps), 1, dumps)
            self.assertIsNotNone(backup.dump_time(dumps[0]))
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(directory, dumps[0])).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(directory).st_mode), 0o700)
            self.assertIn("Checked: 3 tables with data", done.stdout)

            # The restore drill, as a superuser (the owner role has no CREATEDB), comparing with the live counts
            drill = self.run_script("restore_check.py", "--dir", directory, "--database", self.RESTORED, "--keep",
                                    RESTORE_CHECK_DATABASE_URL=os.environ["TEST_POSTGRES_URL"])
            self.assertEqual(drill.returncode, 0, drill.stdout + drill.stderr)
            self.assertIn("Restore check passed", drill.stdout)
            self.assertIn("public.export_jobs", drill.stdout)   # listed as excluded on purpose, not a failure
            for table in ("sensor_measurements", "sampling_measurements", "schema_migrations"):
                self.assertEqual(self.rows(self.RESTORED, table), self.rows(self.SOURCE, table), table)
            self.assertEqual(len(self.rows(self.RESTORED, "sensor_measurements")), 500)
            self.admin_sql(f"DROP DATABASE {self.RESTORED}")

            # Without the exclusions the owner role can't lock export_jobs: the run fails and leaves no file behind
            failed = self.run_script("backup_db.py", "--dir", directory, "--no-prune", BACKUP_MIN_FREE_MB="0",
                                     BACKUP_EXCLUDE_TABLES="")
            self.assertEqual(failed.returncode, 1)
            self.assertIn("permission denied", failed.stderr)
            self.assertEqual(sorted(os.listdir(directory)), dumps)

    def test_restore_check_without_createdb_explains(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_script("backup_db.py", "--dir", directory, BACKUP_MIN_FREE_MB="0").returncode, 0)
            drill = self.run_script("restore_check.py", "--dir", directory, "--database", self.RESTORED)
            self.assertEqual(drill.returncode, 1)
            self.assertIn("CREATEDB", drill.stderr)


if __name__ == "__main__":
    unittest.main()
