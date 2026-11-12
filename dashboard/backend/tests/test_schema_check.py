"""The guards that keep this code off a database that hasn't had migration 0002 (db/models.py): the Instant type
and check_schema, which create_app() runs. No database needed; the PostgreSQL side is in test_timestamptz_postgres.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import pathlib
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from db.models import Instant, OldSchemaError, check_schema  # noqa: E402

UTC = dt.timezone.utc
POSTGRES, SQLITE = types.SimpleNamespace(name="postgresql"), types.SimpleNamespace(name="sqlite")


class InstantResults(unittest.TestCase):
    def test_aware_values_become_utc(self):
        est = dt.timezone(dt.timedelta(hours=-5))
        got = Instant().process_result_value(dt.datetime(2026, 11, 1, 1, 30, tzinfo=est), POSTGRES)
        self.assertEqual((got, got.tzinfo), (dt.datetime(2026, 11, 1, 6, 30, tzinfo=UTC), UTC))

    def test_naive_from_sqlite_is_the_stored_utc_wall_time(self):
        got = Instant().process_result_value(dt.datetime(2026, 11, 1, 6, 30), SQLITE)
        self.assertEqual(got, dt.datetime(2026, 11, 1, 6, 30, tzinfo=UTC))

    def test_naive_from_postgresql_means_the_old_schema_and_raises(self):
        with self.assertRaisesRegex(OldSchemaError, "run scripts/migrate.py"):
            Instant().process_result_value(dt.datetime(2026, 11, 1, 1, 30), POSTGRES)

    def test_none_passes(self):
        self.assertIsNone(Instant().process_result_value(None, POSTGRES))


class CheckSchema(unittest.TestCase):
    def test_only_postgresql_is_checked(self):
        check_schema("sqlite://")
        check_schema(None)

    def test_an_unreachable_database_is_logged_and_let_through(self):
        # As in CI's import check: nothing listens on port 1, so the connection is refused at once.
        logged = []
        check_schema("postgresql://u:p@127.0.0.1:1/x", log=logged.append)
        self.assertEqual(len(logged), 1)
        self.assertIn("can't be reached", logged[0])
        self.assertNotIn("u:p", logged[0])   # never the URL or its credentials


if __name__ == "__main__":
    unittest.main()
