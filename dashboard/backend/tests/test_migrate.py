"""Tests for scripts/migrate.py, run against throwaway SQLite databases and migration folders. Run from
dashboard/backend: python -m unittest discover -s tests

The PostgreSQL-only paths (the advisory lock, the invalid-index refusal after a failed CREATE INDEX CONCURRENTLY,
and rolling back a multi-statement file, which SQLite can't run in one call) are in PostgresRunner. It runs only
when MIGRATE_TEST_DATABASE_URL points at a disposable PostgreSQL database, because it drops and creates tables
there; never point it at a real one. They were run against a throwaway postgres:13 container."""
import os
import pathlib
import sys
import tempfile
import threading
import unittest

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import migrate  # noqa: E402


class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.engine = create_engine(f"sqlite:///{self.dir / 'test.db'}")

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def write(self, name, sql):
        (self.dir / name).write_text(sql, encoding="utf-8")

    def run_migrate(self):
        return migrate.migrate(self.engine, self.dir, log=lambda *_: None)

    def recorded(self):
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))]

    def test_applies_numbered_files_in_order_and_skips_others(self):
        # Each migration appends to a log table, so the table's row order is the order they ran in.
        self.write("0010_third.sql", "INSERT INTO log VALUES ('0010')")
        self.write("0002_second.sql", "INSERT INTO log VALUES ('0002')")
        self.write("0001_first.sql", "CREATE TABLE log (name text)")
        self.write("2026-11-10_one_off_fix.sql", "DROP TABLE log")   # a dated one-off: never run by the runner
        self.write("notes.txt", "not SQL")
        self.assertEqual(self.run_migrate(), ["0001_first", "0002_second", "0010_third"])
        with self.engine.connect() as conn:
            ran = [r[0] for r in conn.execute(text("SELECT name FROM log ORDER BY rowid"))]
        self.assertEqual(ran, ["0002", "0010"])
        self.assertEqual(self.recorded(), ["0001_first", "0002_second", "0010_third"])

    def test_second_run_applies_nothing_and_new_files_run_alone(self):
        self.write("0001_first.sql", "CREATE TABLE log (name text)")
        self.run_migrate()
        self.assertEqual(self.run_migrate(), [])
        self.write("0002_second.sql", "INSERT INTO log VALUES ('0002')")
        self.assertEqual(migrate.pending(self.engine, self.dir), [self.dir / "0002_second.sql"])
        self.assertEqual(self.run_migrate(), ["0002_second"])
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM log")).scalar(), 1)

    def test_a_failing_migration_is_not_recorded_and_stops_the_run(self):
        self.write("0001_first.sql", "CREATE TABLE log (name text)")
        self.write("0002_broken.sql", "INSERT INTO missing_table VALUES (1)")
        self.write("0003_after.sql", "INSERT INTO log VALUES ('0003')")
        with self.assertRaises(Exception):
            self.run_migrate()
        self.assertEqual(self.recorded(), ["0001_first"])
        self.assertEqual([p.name for p in migrate.pending(self.engine, self.dir)], ["0002_broken.sql", "0003_after.sql"])

    def test_no_transaction_file_runs_and_is_recorded(self):
        self.write("0001_table.sql", "CREATE TABLE t (a int, b int)")
        self.write("0002_index.sql", "-- migrate: no-transaction\n-- why it needs autocommit\nCREATE INDEX ix_t ON t (a, b)")
        self.run_migrate()
        self.assertEqual([ix["name"] for ix in inspect(self.engine).get_indexes("t")], ["ix_t"])
        self.assertEqual(self.recorded(), ["0001_table", "0002_index"])

    def test_status_reads_without_creating_the_table(self):
        self.write("0001_first.sql", "CREATE TABLE log (name text)")
        self.assertEqual(migrate.applied_versions(self.engine), set())
        self.assertEqual(len(migrate.pending(self.engine, self.dir)), 1)
        self.assertFalse(inspect(self.engine).has_table("schema_migrations"))

    def test_duplicate_numbers_are_refused_before_anything_runs(self):
        self.write("0001_first.sql", "CREATE TABLE log (name text)")
        self.write("0001_other.sql", "CREATE TABLE other (name text)")
        with self.assertRaisesRegex(migrate.MigrationError, "0001"):
            self.run_migrate()
        self.assertFalse(inspect(self.engine).has_table("schema_migrations"))
        self.assertFalse(inspect(self.engine).has_table("log"))

    def test_a_byte_order_mark_does_not_hide_the_marker(self):
        (self.dir / "0001_index.sql").write_text("-- migrate: no-transaction\nSELECT 1", encoding="utf-8-sig")
        self.assertTrue(migrate.needs_autocommit(migrate.read(self.dir / "0001_index.sql")))


class Marker(unittest.TestCase):
    def test_only_a_first_line_marker_counts(self):
        self.assertTrue(migrate.needs_autocommit("-- migrate: no-transaction\nCREATE INDEX CONCURRENTLY x ON t (a);"))
        self.assertTrue(migrate.needs_autocommit("\n  -- Migrate: No-Transaction  \nSELECT 1"))
        self.assertFalse(migrate.needs_autocommit("-- an index\n-- migrate: no-transaction\nSELECT 1"))
        self.assertFalse(migrate.needs_autocommit(""))


class RepoMigrations(unittest.TestCase):
    def test_repo_folder(self):
        names = [p.name for p in migrate.migration_files()]   # also raises on duplicate numbers
        self.assertIn("0001_sensor_measurements_group_time_idx.sql", names)
        self.assertNotIn("2026-11-10_swap_air_soil_temperature.sql", names)
        index = migrate.read(migrate.MIGRATIONS_DIR / "0001_sensor_measurements_group_time_idx.sql")
        self.assertTrue(migrate.needs_autocommit(index), "CREATE INDEX CONCURRENTLY can't run in a transaction")


@unittest.skipUnless(os.getenv("MIGRATE_TEST_DATABASE_URL"), "set MIGRATE_TEST_DATABASE_URL to a disposable PostgreSQL")
class PostgresRunner(Runner):
    TABLES = "schema_migrations, t, t2"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.engine = create_engine(os.environ["MIGRATE_TEST_DATABASE_URL"])
        self.sql(f"DROP TABLE IF EXISTS {self.TABLES} CASCADE")

    def tearDown(self):
        self.sql(f"DROP TABLE IF EXISTS {self.TABLES} CASCADE")
        super().tearDown()

    def sql(self, statement):
        """Run one statement outside a transaction; returns the rows of a SELECT."""
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.exec_driver_sql(statement)
            return result.fetchall() if result.returns_rows else None

    # The SQLite tests above run here too (as subclass methods), except the ones that rely on SQLite's rowid.
    def test_applies_numbered_files_in_order_and_skips_others(self):
        self.write("0001_first.sql", "CREATE TABLE t (n serial, name text)")
        self.write("0010_third.sql", "INSERT INTO t (name) VALUES ('0010')")
        self.write("0002_second.sql", "INSERT INTO t (name) VALUES ('0002')")
        self.write("2026-11-10_one_off_fix.sql", "DROP TABLE t")
        self.assertEqual(self.run_migrate(), ["0001_first", "0002_second", "0010_third"])
        self.assertEqual([r[0] for r in self.sql("SELECT name FROM t ORDER BY n")], ["0002", "0010"])

    def test_second_run_applies_nothing_and_new_files_run_alone(self):
        self.write("0001_first.sql", "CREATE TABLE t (name text)")
        self.run_migrate()
        self.assertEqual(self.run_migrate(), [])
        self.write("0002_second.sql", "INSERT INTO t VALUES ('0002')")
        self.assertEqual(self.run_migrate(), ["0002_second"])

    def test_a_failing_migration_is_not_recorded_and_stops_the_run(self):
        self.write("0001_first.sql", "CREATE TABLE t (name text)")
        self.write("0002_broken.sql", "INSERT INTO missing_table VALUES (1)")
        with self.assertRaises(Exception):
            self.run_migrate()
        self.assertEqual(self.recorded(), ["0001_first"])

    def test_no_transaction_file_runs_and_is_recorded(self):
        self.write("0001_table.sql", "CREATE TABLE t (a int, b int)")
        self.write("0002_index.sql", "-- migrate: no-transaction\nCREATE INDEX CONCURRENTLY ix_t ON t (a, b)")
        self.run_migrate()
        self.assertEqual([ix["name"] for ix in inspect(self.engine).get_indexes("t")], ["ix_t"])
        self.assertEqual(self.recorded(), ["0001_table", "0002_index"])

    def test_a_failing_second_statement_rolls_back_the_first(self):
        self.write("0001_two.sql", "CREATE TABLE t2 (a int);\nINSERT INTO missing_table VALUES (1);")
        with self.assertRaises(Exception):
            self.run_migrate()
        self.assertFalse(inspect(self.engine).has_table("t2"))
        self.assertEqual(self.recorded(), [])

    def test_an_invalid_index_from_a_failed_concurrent_build_is_not_recorded(self):
        # A unique index over duplicate values fails part way and leaves an INVALID index behind.
        self.sql("CREATE TABLE t (a int)")
        self.sql("INSERT INTO t VALUES (1), (1)")
        self.write("0001_index.sql", "-- migrate: no-transaction\nCREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_t_a ON t (a)")
        with self.assertRaises(Exception):
            self.run_migrate()   # the build itself fails
        self.assertEqual(self.sql("SELECT indisvalid FROM pg_index WHERE indexrelid = 'ix_t_a'::regclass"), [(False,)])
        with self.assertRaisesRegex(migrate.MigrationError, "ix_t_a.*DROP INDEX CONCURRENTLY"):
            self.run_migrate()   # IF NOT EXISTS skips the invalid index; the runner must not record it
        self.assertEqual(self.recorded(), [])
        self.sql("DROP INDEX CONCURRENTLY ix_t_a")
        self.sql("TRUNCATE t; INSERT INTO t VALUES (1)")
        self.assertEqual(self.run_migrate(), ["0001_index"])

    def test_a_second_run_waits_for_the_lock_and_then_finds_nothing_to_do(self):
        self.sql("CREATE TABLE t (a int)")
        self.write("0001_index.sql", "-- migrate: no-transaction\nCREATE INDEX CONCURRENTLY ix_t_a ON t (a)")
        holder = self.engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        holder.execute(text("SELECT pg_advisory_lock(:key)"), {"key": migrate.LOCK_KEY})
        results = []
        run = threading.Thread(target=lambda: results.append(self.run_migrate()))
        run.start()
        run.join(1.5)
        self.assertTrue(run.is_alive(), "migrate() ran while another session held the lock")
        holder.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": migrate.LOCK_KEY})
        holder.close()
        run.join(30)
        self.assertEqual(results, [["0001_index"]])   # the CONCURRENTLY build didn't wait on the lock connection
        self.assertEqual(self.run_migrate(), [])


if __name__ == "__main__":
    unittest.main()
