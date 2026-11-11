"""Tests for scripts/clean_sentinels.py. Run from dashboard/backend: python -m unittest discover -s tests -t .

They need PostgreSQL (the script's SQL is what runs in production): set TEST_POSTGRES_URL to an empty, throwaway
database (its tables are created and dropped). Without it they're skipped.
"""
import contextlib
import csv
import datetime as dt
import io
import os
import pathlib
import stat
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the cleanup against PostgreSQL")
class CleanSentinelsTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from db.models import SensorMeasurement
        from scripts import clean_sentinels
        self.cs = clean_sentinels
        self.table = SensorMeasurement.__table__
        self.engine = create_engine(os.environ["TEST_POSTGRES_URL"])
        self.table.create(self.engine, checkfirst=True)
        t = dt.datetime(2026, 6, 12, 11, 10)   # site wall time; stored as the instant it names (15:10Z)
        rows = [("4501", "Quality", "ODO", -100000.0, "mg/L", t),
                ("4501", "Quality", "TSS", -100000.0, "mg/L", t),
                ("4501", "Quality", "ODO", 8.2, "mg/L", t + dt.timedelta(minutes=10)),
                ("22051538", "Weather", "Air Temperature", -12.5, "°C", t),
                ("22051538", "Weather", "Air Temperature", -99998.0, "°C", t + dt.timedelta(days=1))]  # kept: above
        with self.engine.begin() as conn:
            conn.execute(self.table.delete())
            conn.execute(self.table.insert(), [dict(zip(("station_id", "group_type", "measurement_type", "value",
                                                         "unit", "recorded_at"), r)) for r in rows])
        self.logs = tempfile.TemporaryDirectory()
        self.addCleanup(self.logs.cleanup)

    def tearDown(self):
        self.table.drop(self.engine, checkfirst=True)
        self.engine.dispose()

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.cs.main(list(argv), engine=self.engine, logs_dir=self.logs.name)
        return code, out.getvalue()

    def values(self):
        with self.engine.connect() as conn:
            return sorted(r[0] for r in conn.execute(self.table.select().with_only_columns(self.table.c.value)))

    def test_check_is_the_default_and_changes_nothing(self):
        for argv in ((), ("--check",)):
            code, out = self.run_main(*argv)
            self.assertEqual(code, 0)
            self.assertIn("2 stored value(s) at or below -99999", out)
            self.assertIn("2026-06-12  Quality  ODO", out)
            self.assertIn("2026-06-12  Quality  TSS", out)
            self.assertEqual(len(self.values()), 5)
            self.assertEqual(os.listdir(self.logs.name), [])

    def test_apply_backs_up_then_deletes_only_sentinels(self):
        code, out = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertIn("Deleted 2 row(s)", out)
        self.assertEqual(self.values(), [-99998.0, -12.5, 8.2])
        (name,) = os.listdir(self.logs.name)
        path = pathlib.Path(self.logs.name) / name
        self.assertRegex(name, r"^sentinels-\d{8}T\d{6}\.csv$")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)  # owner only
        with open(path, newline="", encoding="utf-8") as f:
            backup = list(csv.DictReader(f))
        self.assertEqual(sorted((r["measurement_type"], float(r["value"]), r["recorded_at"]) for r in backup),
                         [("ODO", -100000.0, "2026-06-12 15:10:00+00:00"),   # 11:10 EDT, as an instant
                          ("TSS", -100000.0, "2026-06-12 15:10:00+00:00")])
        code, out = self.run_main("--apply")  # nothing left: no second backup
        self.assertIn("0 stored value(s)", out)
        self.assertEqual(len(os.listdir(self.logs.name)), 1)

    def test_nothing_is_deleted_when_the_backup_fails(self):
        with unittest.mock.patch.object(self.cs, "write_backup", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.run_main("--apply")
        self.assertEqual(len(self.values()), 5)

    def test_check_and_apply_together_are_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.cs.parse_args(["--check", "--apply"])


if __name__ == "__main__":
    unittest.main()
