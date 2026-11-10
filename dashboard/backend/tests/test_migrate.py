"""Tests for scripts/migrate.py, run against throwaway SQLite databases and migration folders. Run from
dashboard/backend: python -m unittest discover -s tests"""
import pathlib
import sys
import tempfile
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


class Marker(unittest.TestCase):
    def test_only_a_first_line_marker_counts(self):
        self.assertTrue(migrate.needs_autocommit("-- migrate: no-transaction\nCREATE INDEX CONCURRENTLY x ON t (a);"))
        self.assertTrue(migrate.needs_autocommit("\n  -- Migrate: No-Transaction  \nSELECT 1"))
        self.assertFalse(migrate.needs_autocommit("-- an index\n-- migrate: no-transaction\nSELECT 1"))
        self.assertFalse(migrate.needs_autocommit(""))


class RepoMigrations(unittest.TestCase):
    def test_repo_folder(self):
        names = [p.name for p in migrate.migration_files()]
        self.assertIn("0001_sensor_measurements_group_time_idx.sql", names)
        self.assertNotIn("2026-11-10_swap_air_soil_temperature.sql", names)
        self.assertEqual(len({n[:4] for n in names}), len(names), "two migrations share a number")
        index = (migrate.MIGRATIONS_DIR / "0001_sensor_measurements_group_time_idx.sql").read_text(encoding="utf-8")
        self.assertTrue(migrate.needs_autocommit(index), "CREATE INDEX CONCURRENTLY can't run in a transaction")


if __name__ == "__main__":
    unittest.main()
