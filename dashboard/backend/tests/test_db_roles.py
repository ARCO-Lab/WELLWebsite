"""The least-privileged database roles (app/db/roles.sql, checked by app/db/roles_check.sql).

Builds a database the way the VM's was built (the tables created by a superuser), applies roles.sql, then runs the
migrations, the backup and its restore drill as well_app and welldash²'s reads and writes as well_ops, and checks
that neither role can do what made the superuser dangerous: run programs or read files on the database host, create
roles or databases. Runs only when TEST_POSTGRES_URL points at a disposable server reached as a superuser (CI's
postgres:13 container), because it creates the cluster-wide roles well_app and well_ops and drops them again;
never point it at a real one. Run from dashboard/backend: python -m unittest tests.test_db_roles"""
import datetime as dt
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
from utils import backup  # noqa: E402

ROLES_SQL = APP / "db" / "roles.sql"
CHECK_SQL = APP / "db" / "roles_check.sql"
DATABASE = "well_roles_test"
RESTORED = "welldb_restore_check_roles_test"
PASSWORDS = {"well_app": "app-test-password", "well_ops": "ops-test-password"}
INSUFFICIENT_PRIVILEGE = "42501"


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to a disposable PostgreSQL server "
                                                     "(as a superuser) to test the database roles")
class DatabaseRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from sqlalchemy.engine import make_url
        cls.psycopg2 = psycopg2
        cls.admin_url = make_url(os.environ["TEST_POSTGRES_URL"]).set(drivername="postgresql+psycopg2")
        cls.admin = backup.parse_database_url(os.environ["TEST_POSTGRES_URL"])
        if not cls.server_sql("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")[0][0]:
            raise unittest.SkipTest("set TEST_POSTGRES_URL to a superuser's URL: roles.sql transfers ownership")
        existing = cls.server_sql("SELECT rolname FROM pg_roles WHERE rolname IN ('well_app', 'well_ops')")
        if existing:
            raise RuntimeError(f"{existing} already exist on this server: run this test against a throwaway one")
        cls.superuser_url = cls.url(None)   # from here on, tearDownClass cleans up
        try:
            cls.build()
        except BaseException:
            cls.tearDownClass()   # unittest doesn't call it when setUpClass fails
            raise

    @classmethod
    def build(cls):
        from sqlalchemy import create_engine
        cls.server_sql(f"DROP DATABASE IF EXISTS {DATABASE}")
        cls.server_sql(f"CREATE DATABASE {DATABASE}")

        # The tables as on the VM: created by the superuser, with create_all(), plus a table, a sequence and a type
        # made by hand (as the one-off data fix created data_fixes)
        cls.run_ok(cls.run_app("db/init_db.py", cls.superuser_url))
        cls.db_sql("CREATE TABLE data_fixes (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())",
                   "CREATE SEQUENCE standalone_seq", "CREATE TYPE fix_kind AS ENUM ('swap', 'delete')")

        # Twice: a second run must be a no-op that still succeeds
        cls.roles_output = cls.run_ok(cls.psql(ROLES_SQL))
        cls.run_ok(cls.psql(ROLES_SQL))
        for role, password in PASSWORDS.items():
            cls.db_sql(f"ALTER ROLE {role} PASSWORD '{password}'")
        cls.app_url, cls.ops_url = cls.url("well_app"), cls.url("well_ops")

        # Every migration as well_app, on tables it only got from roles.sql (0001 and 0004 build indexes
        # CONCURRENTLY on sensor_measurements, 0003 alters alert_incidents), then roles.sql again for the tables
        # migration 0005 created, which welldash² writes to
        cls.migrate_output = cls.run_ok(cls.run_app("scripts/migrate.py", cls.app_url))
        cls.run_ok(cls.psql(ROLES_SQL))
        cls.check_output = cls.run_ok(cls.psql(CHECK_SQL))
        cls.app_engine = create_engine(cls.app_url)
        cls.ops_engine = create_engine(cls.ops_url)

    @classmethod
    def tearDownClass(cls):
        for engine in (getattr(cls, "app_engine", None), getattr(cls, "ops_engine", None)):
            if engine is not None:
                engine.dispose()
        if not hasattr(cls, "superuser_url"):
            return   # skipped or refused before creating anything
        cls.server_sql(f"DROP DATABASE IF EXISTS {RESTORED}")
        cls.server_sql(f"DROP DATABASE IF EXISTS {DATABASE}")
        # Their privileges and default privileges were in that database only, so the roles can go now
        cls.server_sql("DROP ROLE IF EXISTS well_app")
        cls.server_sql("DROP ROLE IF EXISTS well_ops")

    # --- helpers ---------------------------------------------------------------------------------------------

    @classmethod
    def url(cls, role):
        url = cls.admin_url.set(database=DATABASE)
        if role:
            url = url.set(username=role, password=PASSWORDS[role])
        return url.render_as_string(hide_password=False)

    @classmethod
    def server_sql(cls, statement):
        """Run `statement` as the superuser in the server's own database (autocommit); its rows, if any."""
        conn = cls.psycopg2.connect(**backup.psycopg2_kwargs(cls.admin))
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(statement)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    @classmethod
    def db_sql(cls, *statements):
        """Run `statements` as the superuser in the test database, in one transaction."""
        conn = cls.psycopg2.connect(**backup.psycopg2_kwargs(backup.with_database(cls.admin, DATABASE)))
        try:
            with conn, conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    @classmethod
    def psql(cls, path):
        """Run a .sql file with psql as the superuser, from stdin, as the README tells the owner to."""
        with backup.libpq_env(backup.with_database(cls.admin, DATABASE)) as env, open(path, "rb") as sql_file:
            return subprocess.run([backup.pg_tool("psql"), "-X", "-v", "ON_ERROR_STOP=1"], stdin=sql_file, env=env,
                                  capture_output=True, timeout=120)

    @classmethod
    def run_app(cls, script, database_url, *args, **env):
        environ = {**os.environ, "DATABASE_URL": database_url, "SENTRY_DSN": "", "BACKUP_MIN_FREE_MB": "0", **env}
        return subprocess.run([sys.executable, script, *args], env=environ, cwd=APP, capture_output=True,
                              timeout=300)

    @staticmethod
    def run_ok(done):
        out = (done.stdout + done.stderr).decode() if isinstance(done.stdout, bytes) else done.stdout + done.stderr
        if done.returncode != 0:
            raise AssertionError(f"{done.args} exited with {done.returncode}:\n{out}")
        return out

    def connect(self, role):
        return self.psycopg2.connect(**backup.psycopg2_kwargs(backup.parse_database_url(self.url(role))))

    def refused(self, role, statement):
        """The SQLSTATE PostgreSQL answers `statement` with, run as `role` (None if it succeeded); rolled back.
        CREATE DATABASE can't run in a transaction, so it runs in autocommit."""
        conn = self.connect(role)
        conn.autocommit = statement.startswith("CREATE DATABASE")
        try:
            with conn.cursor() as cur:
                cur.execute(statement)
            return None
        except self.psycopg2.Error as e:
            return e.pgcode
        finally:
            conn.rollback()
            conn.close()

    def public_tables(self):
        return [r[0] for r in self.db_sql("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")]

    # --- the roles themselves --------------------------------------------------------------------------------

    def test_roles_have_none_of_the_superuser_powers(self):
        rows = self.db_sql("SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls, "
                           "rolcanlogin FROM pg_roles WHERE rolname IN ('well_app', 'well_ops') ORDER BY 1")
        self.assertEqual(rows, [("well_app", False, False, False, False, False, True),
                                ("well_ops", False, False, False, False, False, True)])
        self.assertEqual(self.db_sql("SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
                                     "WHERE r.rolname IN ('well_app', 'well_ops')"), [(0,)])
        self.assertIn("roles check passed", self.check_output)

    def test_roles_sql_handed_the_superusers_objects_to_well_app(self):
        self.assertIn("owner of sensor_measurements is now well_app", self.roles_output)
        self.assertIn("owner of data_fixes is now well_app", self.roles_output)
        self.assertIn("owner of sequence standalone_seq is now well_app", self.roles_output)
        self.assertIn("owner of type fix_kind is now well_app", self.roles_output)
        owners = self.db_sql("SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c "
                             "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public'")
        self.assertEqual(owners, [("well_app",)])   # tables, indexes, sequences, the migrations' new tables too
        self.assertEqual(self.db_sql("SELECT pg_get_userbyid(typowner) FROM pg_type WHERE typname = 'fix_kind'"),
                         [("well_app",)])

    def test_neither_role_can_run_programs_read_files_or_create_roles(self):
        statements = [
            "COPY (SELECT 1) TO PROGRAM 'true'",
            "COPY data_fixes (name) FROM PROGRAM 'id'",
            "COPY data_fixes (name) FROM '/etc/passwd'",
            "COPY (SELECT 1) TO '/tmp/well_roles_test.out'",
            "SELECT pg_read_file('/etc/passwd')",
            "SELECT pg_ls_dir('.')",
            "CREATE ROLE well_roles_intruder LOGIN",
            "ALTER ROLE well_app SUPERUSER",
            "ALTER ROLE well_ops CREATEROLE",
            "GRANT pg_execute_server_program TO well_app",
            "CREATE DATABASE well_roles_intruder",
        ]
        for role in ("well_app", "well_ops"):
            for statement in statements:
                with self.subTest(role=role, statement=statement):
                    self.assertEqual(self.refused(role, statement), INSUFFICIENT_PRIVILEGE)

    # --- well_app: the API, the worker, the export worker, migrations, backups -------------------------------

    def test_migrations_ran_as_well_app_and_a_second_run_finds_nothing(self):
        self.assertIn("migration(s) applied", self.migrate_output)
        again = self.run_ok(self.run_app("scripts/migrate.py", self.app_url))
        self.assertIn("nothing to apply", again)
        indexes = {r[0] for r in self.db_sql("SELECT indexname FROM pg_indexes WHERE tablename = 'sensor_measurements'")}
        self.assertLessEqual({"ix_sensor_measurements_group_type_recorded_at", "ix_sensor_measurements_series_time"},
                             indexes)
        invalid = self.db_sql("SELECT count(*) FROM pg_index WHERE NOT indisvalid")
        self.assertEqual(invalid, [(0,)])

    def test_well_app_reads_and_writes_every_table(self):
        conn = self.connect("well_app")
        try:
            with conn.cursor() as cur:
                for table in self.public_tables():
                    cur.execute(f"SELECT count(*) FROM {table}")
                cur.execute("INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, unit, "
                            "recorded_at) VALUES ('1', 'Weather', 'Air Temperature', 1.5, 'C', now()) RETURNING id")
                row_id = cur.fetchone()[0]
                cur.execute("UPDATE sensor_measurements SET value = 2 WHERE id = %s", (row_id,))
                cur.execute("DELETE FROM sensor_measurements WHERE id = %s", (row_id,))
                cur.execute("INSERT INTO export_jobs (id, status, domain, payload, progress_pct, created_at) "
                            "VALUES ('roles-test', 'queued', 'sensor', '{}', 0, now())")
                cur.execute("INSERT INTO data_fixes (name) VALUES ('roles test')")
                cur.execute("SELECT pg_advisory_xact_lock(hashtext('export_jobs_limits'))")   # the export limit lock
                cur.execute("SET LOCAL work_mem = '64MB'")                                     # /api/series
                cur.execute("SET LOCAL statement_timeout = '15s'")                              # /api/windrose
                cur.execute("ANALYZE sensor_measurements")                                     # the backup's counts
        finally:
            conn.rollback()
            conn.close()

    def test_tables_made_later_keep_working(self):
        try:
            # By a migration (well_app): welldash² can read it without another run of roles.sql
            conn = self.connect("well_app")
            with conn, conn.cursor() as cur:
                cur.execute("CREATE TABLE roles_test_later (id serial PRIMARY KEY, note text)")
                cur.execute("INSERT INTO roles_test_later (note) VALUES ('x')")
            conn.close()
            # By hand, as the superuser: well_app can use it, welldash² can read it
            self.db_sql("CREATE TABLE roles_test_by_hand (id serial PRIMARY KEY, note text)")
            conn = self.connect("well_app")
            with conn, conn.cursor() as cur:
                cur.execute("INSERT INTO roles_test_by_hand (note) VALUES ('y')")
                cur.execute("UPDATE roles_test_by_hand SET note = 'z'")
            conn.close()
            for table in ("roles_test_later", "roles_test_by_hand"):
                with self.subTest(table=table):
                    self.assertIsNone(self.refused("well_ops", f"SELECT * FROM {table}"))
                    self.assertEqual(self.refused("well_ops", f"INSERT INTO {table} (note) VALUES ('no')"),
                                     INSUFFICIENT_PRIVILEGE)
        finally:
            self.db_sql("DROP TABLE IF EXISTS roles_test_later", "DROP TABLE IF EXISTS roles_test_by_hand")

    def test_backup_and_restore_drill_as_well_app(self):
        conn = self.connect("well_app")
        with conn, conn.cursor() as cur:
            cur.execute("INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, unit, "
                        "recorded_at) SELECT '21079936', 'Quality', 'Temperature', g, 'C', "
                        "timestamp '2026-11-01' + g * interval '10 min' FROM generate_series(1, 200) g")
            cur.execute("INSERT INTO sampling_measurements (site_id, creek_id, measurement_type, value, unit, "
                        "recorded_at) VALUES ('S1', 'C1', 'E. coli', 10, 'CFU/100mL', '2026-11-01')")
        conn.close()
        with tempfile.TemporaryDirectory() as directory:
            done = self.run_app("scripts/backup_db.py", self.app_url, "--dir", directory)
            out = self.run_ok(done)
            self.assertNotIn("WARNING", done.stderr.decode(), "well_app owns everything, so nothing is left out")
            self.assertIn("every table", out)

            # Creating the throwaway database needs CREATEDB, which well_app lacks; the README grants it for the drill
            drill = self.run_app("scripts/restore_check.py", self.app_url, "--dir", directory, "--database", RESTORED)
            self.assertEqual(drill.returncode, 1)
            self.assertIn("CREATEDB", drill.stderr.decode())
            self.db_sql("ALTER ROLE well_app CREATEDB")
            try:
                drill = self.run_app("scripts/restore_check.py", self.app_url, "--dir", directory, "--database",
                                     RESTORED)
                self.assertIn("Restore check passed", self.run_ok(drill))
            finally:
                self.db_sql("ALTER ROLE well_app NOCREATEDB")
            self.assertEqual(self.server_sql(f"SELECT count(*) FROM pg_database WHERE datname = '{RESTORED}'"), [(0,)])

    # --- well_ops: welldash² -----------------------------------------------------------------------------------

    def test_well_ops_reads_every_table_and_writes_only_its_own(self):
        from ops import data, probe
        now = dt.datetime.now(dt.timezone.utc)
        for fn, args in ((data.database, ()), (data.migrations, ()), (data.vendors, ()), (data.alerts, (now,)),
                         (data.freshness, (now,)), (data.export_jobs, (now, "24h")),
                         (data.availability, (now,)), (data.traffic_summary, (now, "24h"))):
            with self.subTest(section=fn.__name__):
                result = data.section(self.ops_engine, fn, *args)
                self.assertNotIn("error", result)
        self.assertEqual(data.section(self.ops_engine, data.database)["role"], "well_ops")

        probe.record(self.ops_engine, [probe.check("api", "http://127.0.0.1:1/", {}, now=now)])
        self.assertEqual(probe.prune(self.ops_engine, 0, now=now + dt.timedelta(seconds=1)),
                         {"uptime_probes": 1, "request_metrics": 0})

        for table in self.public_tables():
            with self.subTest(table=table):
                self.assertIsNone(self.refused("well_ops", f"SELECT count(*) FROM {table}"))
        for statement in ("INSERT INTO sensor_measurements (station_id, recorded_at) VALUES ('1', now())",
                          "UPDATE export_jobs SET status = 'failed'",
                          "DELETE FROM sensor_measurements",
                          "DELETE FROM schema_migrations",
                          "TRUNCATE request_metrics",
                          "UPDATE uptime_probes SET ok = true",
                          "CREATE TABLE ops_made (id int)",
                          "DROP TABLE uptime_probes",
                          "ALTER TABLE uptime_probes ADD COLUMN x int"):
            with self.subTest(statement=statement):
                self.assertEqual(self.refused("well_ops", statement), INSUFFICIENT_PRIVILEGE)


if __name__ == "__main__":
    unittest.main()
