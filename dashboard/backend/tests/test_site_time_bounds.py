"""Tests for how /api/samples and /api/data read their start and end (utils/timezone.site_range), and for the order
sampling rows are listed in (db/ordering.py). Run from dashboard/backend: python -m unittest discover -s tests -t .

recorded_at is naive America/Toronto wall time. A bound with an offset must be converted to that before the query:
bound as an aware value, PostgreSQL reads recorded_at in the session's TimeZone (so the answer depends on a database
setting) and SQLite drops the offset. The SQLite tests always run; the PostgreSQL ones need TEST_POSTGRES_URL (an
empty, throwaway database whose tables are created and dropped) and run with the session TimeZone set to UTC.
"""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database

from utils.timezone import site_range  # noqa: E402

T = dt.datetime


class SiteRangeTests(unittest.TestCase):
    def test_offsets_are_converted_to_toronto_wall_time(self):
        self.assertEqual(site_range("2026-10-31T04:00:00.000Z", "2026-11-03T04:59:59.999Z"),
                         (T(2026, 10, 31, 0, 0), T(2026, 11, 2, 23, 59, 59, 999000)))
        self.assertEqual(site_range("2026-07-01T12:00:00+00:00", "2026-07-01T12:00:00-05:00"),
                         (T(2026, 7, 1, 8, 0), T(2026, 7, 1, 13, 0)))

    def test_naive_times_are_already_local(self):
        self.assertEqual(site_range("2026-11-01T00:00:00", "2026-11-01T23:59:59"),
                         (T(2026, 11, 1, 0, 0), T(2026, 11, 1, 23, 59, 59)))

    def test_mixed_bounds(self):
        # 03:00Z on Nov 10 is 22:00 on Nov 9 in Toronto
        self.assertEqual(site_range("2026-11-09T21:00:00", "2026-11-10T03:00:00Z"),
                         (T(2026, 11, 9, 21, 0), T(2026, 11, 9, 22, 0)))

    def test_instants_inside_the_fall_back_hour_are_put_in_order(self):
        # 05:30Z is 01:30 EDT and 06:10Z is 01:10 EST: forty minutes whose wall times run backwards
        self.assertEqual(site_range("2026-11-01T05:30:00Z", "2026-11-01T06:10:00Z"),
                         (T(2026, 11, 1, 1, 10), T(2026, 11, 1, 1, 30)))
        # The same instants the wrong way round stay backwards, and match nothing
        self.assertEqual(site_range("2026-11-01T06:10:00Z", "2026-11-01T05:30:00Z"),
                         (T(2026, 11, 1, 1, 30), T(2026, 11, 1, 1, 10)))
        # As does any backwards pair of instants
        self.assertEqual(site_range("2026-11-02T05:00:00Z", "2026-11-01T04:00:00Z"),
                         (T(2026, 11, 2, 0, 0), T(2026, 11, 1, 0, 0)))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            site_range("yesterday", "2026-11-01T00:00:00")
        with self.assertRaises(OverflowError):
            site_range("0001-01-01T00:00:00+05:00", "2026-11-01T00:00:00")


def sampling(site, parameter, when, value=1.0):
    return dict(site_id=site, creek_id="19431905", measurement_type=parameter, unit="u", value=value,
                recorded_at=when)


# Readings that share a time, in the order they must come out: site number ("2" before "10"), then parameter
# compared byte for byte ("Phosphorus" before "pH", which a locale-aware collation such as en_US.UTF-8 reverses).
TIED = [sampling("2", "E. coli", T(2026, 10, 31, 9, 40)), sampling("2", "Phosphorus", T(2026, 10, 31, 9, 40)),
        sampling("2", "pH", T(2026, 10, 31, 9, 40)), sampling("10", "E. coli", T(2026, 10, 31, 9, 40)),
        sampling("10", "pH", T(2026, 10, 31, 9, 40))]
# 23:30 on Oct 30 in Toronto is 03:30Z on Oct 31: outside a Toronto day of Oct 31, inside it read as UTC wall time
EDGE = [sampling("2", "pH", T(2026, 10, 30, 23, 30)), sampling("2", "pH", T(2026, 11, 1, 1, 0))]


class AppCase:
    """A Flask app on cls.uri, with the readings above stored once."""

    uri = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from config import Config
        # create_app copies the URI, so it's restored straight after and later test modules keep theirs
        saved_uri = Config.SQLALCHEMY_DATABASE_URI
        Config.SQLALCHEMY_DATABASE_URI = cls.uri
        try:
            from server import create_app
            cls.app = create_app()
        finally:
            Config.SQLALCHEMY_DATABASE_URI = saved_uri
        from db.database import db
        from db.models import SamplingMeasurement, SensorMeasurement
        cls.db = db
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        cls.prepare_engine()
        db.drop_all()   # a database shared with other tests may still hold their tables
        db.create_all()
        # Stored in reverse, so an order that only follows insertion would fail
        db.session.add_all(SamplingMeasurement(**r) for r in reversed(TIED + EDGE))
        for when, value in ((T(2026, 10, 30, 23, 50), 1.0), (T(2026, 10, 31, 0, 0), 2.0),
                            (T(2026, 10, 31, 23, 50), 3.0), (T(2026, 11, 1, 0, 0), 4.0)):
            db.session.add(SensorMeasurement(station_id="22051538", group_type="Weather", unit="°C", value=value,
                                             measurement_type="Air Temperature", recorded_at=when))
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def prepare_engine(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.drop_all()
        cls.db.engine.dispose()
        cls.ctx.pop()
        super().tearDownClass()

    def samples(self, start, end):
        r = self.client.get(f"/api/samples?start={start}&end={end}")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return [(x["recorded_at"], x["site_id"], x["measurement_type"]) for x in r.get_json()]

    def data(self, start, end):
        r = self.client.get(f"/api/data?start={start}&end={end}&group_type=Weather")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return [x["value"] for x in r.get_json()]

    def test_tied_sampling_rows_by_site_then_parameter(self):
        rows = self.samples("2026-10-31T00:00:00", "2026-10-31T23:59:59")
        self.assertEqual(rows, [(r["recorded_at"].isoformat(), r["site_id"], r["measurement_type"]) for r in TIED])

    def test_recent_in_the_same_order(self):
        r = self.client.get("/api/recent")
        rows = [(x["recorded_at"], x["site_id"], x["measurement_type"]) for x in r.get_json()]
        # The latest of each parameter: pH at 01:00 on Nov 1, the others on Oct 31
        self.assertEqual(rows, [("2026-10-31T09:40:00", "2", "E. coli"), ("2026-10-31T09:40:00", "2", "Phosphorus"),
                                ("2026-10-31T09:40:00", "10", "E. coli"), ("2026-11-01T01:00:00", "2", "pH")])

    def test_sampling_export_in_the_same_order(self):
        import csv
        import tempfile
        from api.services.exports import write_export_csv
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sampling.csv")
            write_export_csv({"domain": "sampling", "start": "2026-10-31T04:00:00.000Z",
                              "end": "2026-11-01T03:59:59.999Z"}, path)
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows[0][1], "recorded_at (America/Toronto)")
        self.assertEqual([(r[1], r[5], r[6]) for r in rows[1:]],
                         [(r["recorded_at"].isoformat(), r["site_id"], r["measurement_type"]) for r in TIED])

    def test_samples_bounds_with_an_offset_are_instants(self):
        local_day = self.samples("2026-10-31T00:00:00", "2026-10-31T23:59:59.999")
        self.assertEqual(len(local_day), len(TIED))
        # Oct 31 in Toronto (EDT), as the dashboard sends it, and with the offset written out
        self.assertEqual(self.samples("2026-10-31T04:00:00.000Z", "2026-11-01T03:59:59.999Z"), local_day)
        self.assertEqual(self.samples("2026-10-31T00:00:00-04:00", "2026-10-31T23:59:59.999-04:00"), local_day)
        # 03:00Z-06:00Z is 23:00 on Oct 30 to 02:00 on Oct 31 in Toronto: only the 23:30 reading
        self.assertEqual(self.samples("2026-10-31T03:00:00Z", "2026-10-31T06:00:00Z"),
                         [("2026-10-30T23:30:00", "2", "pH")])

    def test_data_bounds_with_an_offset_are_instants(self):
        self.assertEqual(self.data("2026-10-31T00:00:00", "2026-10-31T23:59:59"), [2.0, 3.0])
        self.assertEqual(self.data("2026-10-31T04:00:00.000Z", "2026-11-01T03:59:59.999Z"), [2.0, 3.0])
        self.assertEqual(self.data("2026-10-31T00:00:00-04:00", "2026-10-31T23:59:59-04:00"), [2.0, 3.0])

    def test_bad_bounds_are_refused(self):
        for route in ("/api/samples?start=x&end=y", "/api/data?start=x&end=y&group_type=Weather",
                      "/api/samples?start=0001-01-01T00:00:00%2B05:00&end=2026-11-01T00:00:00"):
            with self.subTest(route):
                self.assertEqual(self.client.get(route).status_code, 400)


class SqliteTests(AppCase, unittest.TestCase):
    uri = "sqlite://"


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the queries against PostgreSQL")
class PostgresSessionUtcTests(AppCase, unittest.TestCase):
    """On PostgreSQL with the session TimeZone UTC (a fresh server's default; the VM's is America/New_York), where
    an aware bound compared with recorded_at would be read 4-5 hours off."""

    uri = os.getenv("TEST_POSTGRES_URL")

    @classmethod
    def prepare_engine(cls):
        from sqlalchemy import event

        @event.listens_for(cls.db.engine, "connect")
        def set_session_zone(dbapi_connection, _record):
            cur = dbapi_connection.cursor()
            cur.execute("SET TIME ZONE 'UTC'")
            cur.close()
            dbapi_connection.commit()  # psycopg2 opened a transaction; a rollback would undo the SET

        cls.db.engine.dispose()  # connections made before the listener get replaced

    def test_session_zone_is_utc(self):
        from sqlalchemy import text
        self.assertEqual(self.db.session.execute(text("SHOW TimeZone")).scalar(), "UTC")


if __name__ == "__main__":
    unittest.main()
