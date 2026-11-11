"""db/migrations/0002 (recorded_at to timestamptz), its rollback, and the code that reads and writes recorded_at,
on PostgreSQL. Run from dashboard/backend: python -m unittest discover -s tests -t .

Runs only when TEST_POSTGRES_URL points at a disposable PostgreSQL database (CI starts one). Everything happens in
its own schema, tstz_test, which is dropped and created again by each test; never point it at a real database.

The fixture is the table as production had it before the change: naive America/Toronto wall-clock times, with only
the first (EDT) copy of the hour repeated on 2026-11-01, plus a day when clocks sprang forward and ordinary rows."""
import datetime as dt
import os
import pathlib
import sys
import unittest.mock

from sqlalchemy import create_engine, text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import migrate  # noqa: E402

URL = os.getenv("TEST_POSTGRES_URL")
SCHEMA = "tstz_test"
UTC = dt.timezone.utc
DOWN = migrate.MIGRATIONS_DIR / "down" / "0002_sensor_measurements_recorded_at_timestamptz.sql"
VERSION = "0002_sensor_measurements_recorded_at_timestamptz"

# The table as created by db.create_all() before this change, as production has it.
OLD_TABLE = """
CREATE TABLE sensor_measurements (
    id serial PRIMARY KEY,
    station_id varchar NOT NULL,
    group_type varchar,
    measurement_type varchar,
    value float,
    unit varchar,
    recorded_at timestamp NOT NULL,
    UNIQUE (station_id, measurement_type, recorded_at)
);
CREATE INDEX ix_sensor_measurements_group_type_recorded_at ON sensor_measurements (group_type, recorded_at);
"""

# (naive Toronto wall time as stored before, the instant it must become)
FIXTURE = [
    ("2026-07-01 12:00", "2026-07-01 16:00"),   # summer (EDT, UTC-4)
    ("2026-01-15 12:00", "2026-01-15 17:00"),   # winter (EST, UTC-5)
    ("2026-11-01 00:50", "2026-11-01 04:50"),   # the fall-back night, before the change
    ("2026-11-01 01:00", "2026-11-01 05:00"),   # the repeated hour: the stored rows are its first copy (EDT)
    ("2026-11-01 01:30", "2026-11-01 05:30"),
    ("2026-11-01 01:50", "2026-11-01 05:50"),
    ("2026-11-01 02:00", "2026-11-01 07:00"),   # after the change (EST)
    ("2026-03-08 01:50", "2026-03-08 06:50"),   # the spring-forward night: 01:50 EST
    ("2026-03-08 03:00", "2026-03-08 07:00"),   # 03:00 EDT, ten minutes after 01:50 EST
]


def instant(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


@unittest.skipUnless(URL, "set TEST_POSTGRES_URL to a disposable PostgreSQL")
class PostgresFixture(unittest.TestCase):
    """The pre-change table in a fresh schema; `session_zone` is the session's TimeZone."""
    session_zone = "UTC"   # not the site's zone, so nothing can depend on the session's TimeZone by accident

    def setUp(self):
        self.apps = []
        admin = create_engine(URL)
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            c.exec_driver_sql(f"CREATE SCHEMA {SCHEMA}")
        admin.dispose()
        self.options = f"-c search_path={SCHEMA} -c TimeZone={self.session_zone}"
        self.engine = create_engine(URL, connect_args={"options": self.options})
        with self.engine.begin() as c:
            c.exec_driver_sql(OLD_TABLE)
            for i, (wall, _) in enumerate(FIXTURE):
                for mtype in ("Air Temperature", "Water Temperature"):
                    c.execute(text("INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, "
                                   "unit, recorded_at) VALUES ('22051538', 'Weather', :m, :v, '°C', :t)"),
                              {"m": mtype, "v": float(i), "t": dt.datetime.strptime(wall, "%Y-%m-%d %H:%M")})

    def tearDown(self):
        from db.database import db
        for app in self.apps:
            with app.app_context():
                db.engine.dispose()
        self.engine.dispose()
        admin = create_engine(URL)
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        admin.dispose()

    def rows(self, sql, **params):
        with self.engine.connect() as c:
            return c.execute(text(sql), params).fetchall()

    def column_type(self):
        return self.rows("SELECT data_type FROM information_schema.columns WHERE table_schema = :s "
                         "AND table_name = 'sensor_measurements' AND column_name = 'recorded_at'", s=SCHEMA)[0][0]

    def stored(self):
        """{value: recorded_at} of the Air Temperature rows (value = the fixture's index)."""
        return {int(v): t for v, t in self.rows(
            "SELECT value, recorded_at FROM sensor_measurements WHERE measurement_type = 'Air Temperature'")}

    def run_migrations(self):
        return migrate.migrate(self.engine, log=lambda *_: None)


@unittest.skipUnless(URL, "set TEST_POSTGRES_URL to a disposable PostgreSQL")
class MigrationTests(PostgresFixture):

    def test_plain_conversion_would_pick_the_second_copy(self):
        # Why the migration doesn't use `recorded_at AT TIME ZONE 'America/Toronto'` alone: PostgreSQL gives an
        # ambiguous wall time the offset after the change (EST), but the stored rows are the first copy (EDT).
        [(plain,)] = self.rows("SELECT timestamp '2026-11-01 01:30' AT TIME ZONE 'America/Toronto'")
        self.assertEqual(plain, instant("2026-11-01 06:30"))
        [(gap,)] = self.rows("SELECT timestamp '2026-03-08 02:30' AT TIME ZONE 'America/Toronto'")
        self.assertEqual(gap, instant("2026-03-08 07:30"))   # the skipped hour: the offset before the change

    def test_converts_every_time_to_its_instant(self):
        before = self.stored()
        self.assertEqual(self.column_type(), "timestamp without time zone")
        self.assertIn(VERSION, self.run_migrations())
        self.assertEqual(self.column_type(), "timestamp with time zone")
        after = self.stored()
        self.assertEqual(len(after), len(before))
        for i, (wall, expected) in enumerate(FIXTURE):
            self.assertEqual(after[i], instant(expected), wall)
        self.assertEqual(self.rows("SELECT count(*) FROM sensor_measurements")[0][0], 2 * len(FIXTURE))
        self.assertEqual(self.run_migrations(), [])   # recorded, so it never runs again

    def test_keeps_the_unique_constraint_and_the_indexes(self):
        def indexes():
            return dict(self.rows("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = :s "
                                  "AND tablename = 'sensor_measurements'", s=SCHEMA))
        before = indexes()
        self.run_migrations()
        after = indexes()
        self.assertEqual(after, before)   # same names and definitions, rebuilt by the ALTER
        self.assertIn("ix_sensor_measurements_group_type_recorded_at", after)
        self.assertEqual(self.rows("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                                   "WHERE conrelid = 'sensor_measurements'::regclass AND contype = 'u'"),
                         [("UNIQUE (station_id, measurement_type, recorded_at)",)])
        invalid = self.rows("SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid "
                            "WHERE c.relname = 'sensor_measurements' AND NOT i.indisvalid")
        self.assertEqual(invalid, [(0,)])

    def test_both_copies_of_the_repeated_hour_can_then_be_stored(self):
        from sqlalchemy.dialects.postgresql import insert
        from db.models import SensorMeasurement
        from utils.parsers import licor_rows
        self.run_migrations()
        records = [{"sensor_sn": "21948438-1", "sensor_measurement_type": "Temperature", "unit": "°C",
                    "timestamp": f"2026-11-01 {t}Z", "value": v}
                   for t, v in (("05:30:00", 3.0), ("06:30:00", 103.0))]   # 01:30 EDT (stored), 01:30 EST (new)
        rows = list(licor_rows(records, {"Weather"}, "22051538").values())
        with self.engine.begin() as c:
            stmt = insert(SensorMeasurement.__table__).values(rows).on_conflict_do_nothing(
                index_elements=["station_id", "measurement_type", "recorded_at"])
            self.assertEqual(c.execute(stmt).rowcount, 1)   # the EDT copy was already there
        at_0130 = self.rows("SELECT recorded_at, value FROM sensor_measurements WHERE measurement_type = 'Air Temperature' "
                            "AND (recorded_at AT TIME ZONE 'America/Toronto') = timestamp '2026-11-01 01:30' "
                            "ORDER BY recorded_at")
        self.assertEqual(at_0130, [(instant("2026-11-01 05:30"), 4.0), (instant("2026-11-01 06:30"), 103.0)])

    def test_refuses_a_time_in_the_skipped_spring_hour_and_changes_nothing(self):
        # 02:30 on 2026-03-08 never happened in Toronto. Converted, it would read as 03:30 EDT and could collide with a
        # real 03:30 reading, so the migration stops first.
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, unit, "
                           "recorded_at) VALUES ('22051538', 'Weather', 'Air Temperature', 50, '°C', :t)"),
                      {"t": dt.datetime(2026, 3, 8, 2, 30)})
        before = self.stored()
        with self.assertRaisesRegex(Exception, "1 sensor_measurements rows have a recorded_at in an hour skipped"):
            self.run_migrations()
        self.assertEqual(self.column_type(), "timestamp without time zone")
        self.assertEqual(self.stored(), before)
        self.assertNotIn(VERSION, [r[0] for r in self.rows("SELECT version FROM schema_migrations")])

    def test_does_nothing_on_a_table_that_is_already_timestamptz(self):
        # A database made by db/init_db.py after this change: running the USING expression there would shift it.
        self.run_migrations()
        with self.engine.begin() as c:
            c.exec_driver_sql("DELETE FROM schema_migrations")
        before = self.stored()
        self.assertIn(VERSION, self.run_migrations())
        self.assertEqual(self.stored(), before)

    def test_rollback_restores_the_naive_times_and_saves_the_second_copies(self):
        before = {i: t.isoformat(sep=" ") for i, t in self.stored().items()}
        self.run_migrations()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, unit, "
                           "recorded_at) VALUES ('22051538', 'Weather', 'Air Temperature', 99, '°C', :t)"),
                      {"t": instant("2026-11-01 06:30")})   # the second 01:30, which naive time can't hold
        with self.engine.begin() as c:   # as psql -1 runs it: one transaction
            c.exec_driver_sql(DOWN.read_text(encoding="utf-8"), execution_options={"no_parameters": True})
        self.assertEqual(self.column_type(), "timestamp without time zone")
        self.assertEqual({i: t.isoformat(sep=" ") for i, t in self.stored().items()}, before)
        saved = self.rows("SELECT value, recorded_at FROM sensor_measurements_dst_rollback")
        self.assertEqual(saved, [(99.0, instant("2026-11-01 06:30"))])
        self.assertNotIn(VERSION, [r[0] for r in self.rows("SELECT version FROM schema_migrations")])
        # A second run is a no-op: the column is already naive, nothing more is moved or deleted.
        with self.engine.begin() as c:
            c.exec_driver_sql(DOWN.read_text(encoding="utf-8"), execution_options={"no_parameters": True})
        self.assertEqual({i: t.isoformat(sep=" ") for i, t in self.stored().items()}, before)
        self.assertEqual(self.rows("SELECT count(*) FROM sensor_measurements_dst_rollback"), [(1,)])

    def test_refuses_an_unexpected_column_type(self):
        with self.engine.begin() as c:
            c.exec_driver_sql("ALTER TABLE sensor_measurements ALTER COLUMN recorded_at TYPE text")
        with self.assertRaisesRegex(Exception, "recorded_at is text, expected timestamp or timestamptz"):
            self.run_migrations()
        self.assertNotIn(VERSION, [r[0] for r in self.rows("SELECT version FROM schema_migrations")])


@unittest.skipUnless(URL, "set TEST_POSTGRES_URL to a disposable PostgreSQL")
class MigrationUnderTheSiteZoneTests(MigrationTests):
    session_zone = "America/New_York"   # production's session TimeZone; the result must be the same


@unittest.skipUnless(URL, "set TEST_POSTGRES_URL to a disposable PostgreSQL")
class ApiOnPostgresTests(PostgresFixture):
    """/api/data and /api/latest on the migrated table give the strings the naive column gave before."""
    session_zone = "America/New_York"

    def app(self):
        from config import Config
        import server
        # create_app() builds the engine options with engine_options(); use this fixture's schema and session zone.
        options = {"pool_pre_ping": True, "connect_args": {"options": self.options}}
        with unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", URL), \
             unittest.mock.patch.object(server, "engine_options", lambda uri, timeout_ms: options):
            app = server.create_app()
        self.apps.append(app)   # its engine is disposed before the schema is dropped
        return app

    def test_the_new_code_refuses_to_start_on_the_old_schema(self):
        # Started before the migration, it would read every naive time as UTC: 4-5 hours off. It must not start.
        from db.models import OldSchemaError
        with self.assertRaisesRegex(OldSchemaError, "still timestamp without time zone.*run scripts/migrate.py"):
            self.app()
        self.run_migrations()
        self.assertEqual(self.app().test_client().get("/api/latest").status_code, 200)

    def test_a_naive_value_from_postgresql_raises_instead_of_being_read_as_utc(self):
        # If the old schema is reached anyway (the check found the database unreachable at start), reads fail loudly.
        from db.models import Instant, OldSchemaError
        query = text("SELECT recorded_at FROM sensor_measurements LIMIT 1").columns(recorded_at=Instant)
        with self.engine.connect() as c, self.assertRaisesRegex(OldSchemaError, "run scripts/migrate.py"):
            c.execute(query).all()
        self.run_migrations()
        with self.engine.connect() as c:
            self.assertEqual(c.execute(query).scalar().tzinfo, UTC)

    def test_api_strings_are_unchanged_and_the_range_is_real_time(self):
        # What the old code returned: the naive column's isoformat().
        old = sorted(t.isoformat() for (t,) in self.rows(
            "SELECT recorded_at FROM sensor_measurements WHERE recorded_at BETWEEN '2026-10-31 20:00' AND '2026-11-01 23:00' "
            "AND measurement_type = 'Air Temperature'"))
        self.run_migrations()
        client = self.app().test_client()
        # The dashboard's bounds: local midnight to 23:59:59.999 of Nov 1, sent as UTC with Z (a 25-hour day).
        r = client.get("/api/data?start=2026-11-01T04:00:00.000Z&end=2026-11-02T04:59:59.999Z&group_type=Weather")
        self.assertEqual(r.status_code, 200)
        got = sorted(x["recorded_at"] for x in r.get_json() if x["measurement_type"] == "Air Temperature")
        self.assertEqual(got, old)
        self.assertEqual(got[0], "2026-11-01T00:50:00")
        # An hour of real time inside the repeated hour: 05:30Z-06:29Z holds only the EDT 01:30 and 01:50.
        r = client.get("/api/data?start=2026-11-01T05:30:00Z&end=2026-11-01T06:29:00Z&group_type=Weather")
        self.assertEqual(sorted({x["recorded_at"] for x in r.get_json()}), ["2026-11-01T01:30:00", "2026-11-01T01:50:00"])
        latest = {x["measurement_type"]: x["recorded_at"] for x in client.get("/api/latest").get_json()}
        self.assertEqual(latest, {"Air Temperature": "2026-11-01T02:00:00", "Water Temperature": "2026-11-01T02:00:00"})


if __name__ == "__main__":
    unittest.main()
