"""Tests for /api/series (api/routes/series.py). Run from dashboard/backend: python -m unittest discover -s tests

The SQL tests need PostgreSQL: set TEST_POSTGRES_URL to an empty, throwaway database (its tables are created and
dropped), e.g. a `docker run postgres:13` container. Without it they're skipped.
"""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.routes.series import LADDER, columnar, pick_bucket  # noqa: E402

DAY = 86400


class PickBucketTests(unittest.TestCase):
    def test_raw_resolution_up_to_about_two_weeks(self):
        self.assertEqual(pick_bucket(7 * DAY), 600)
        self.assertEqual(pick_bucket(13 * DAY), 600)

    def test_coarser_buckets_for_longer_spans(self):
        self.assertEqual(pick_bucket(30 * DAY), 1800)
        self.assertEqual(pick_bucket(365 * DAY), 6 * 3600)
        self.assertEqual(pick_bucket(620 * DAY), 12 * 3600)  # "Mar 2025 -> now"

    def test_never_coarser_than_a_day(self):
        self.assertEqual(pick_bucket(20 * 365 * DAY), LADDER[-1])

    def test_points_stay_under_the_cap(self):
        for days in (1, 3, 14, 45, 90, 180, 400, 900, 1500):
            self.assertLessEqual(days * DAY / pick_bucket(days * DAY), 2000, days)


class ColumnarTests(unittest.TestCase):
    def test_groups_rows_into_series_in_order(self):
        rows = [("Weather", "s", "Rain", "mm", 1000, 0.2, 0.0, 0.2),
                ("Weather", "s", "Rain", "mm", 2000, 0.0, 0.0, 0.0),
                ("Logger", "l", "Water Temperature", "°C", 1000, 5.12345, 5.0, 5.3)]
        out = columnar(rows)
        self.assertEqual([(s["group_type"], s["measurement_type"]) for s in out],
                         [("Weather", "Rain"), ("Logger", "Water Temperature")])
        self.assertEqual(out[0]["t"], [1000, 2000])
        self.assertEqual(out[1]["avg"], [5.1235])
        self.assertEqual((out[1]["min"], out[1]["max"]), ([5.0], [5.3]))


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the SQL against PostgreSQL")
class SeriesSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine, text
        url = os.environ["TEST_POSTGRES_URL"]
        admin = create_engine(url, isolation_level="AUTOCOMMIT")
        with admin.connect() as c:  # every new connection uses New York time, as on the production database
            name = c.execute(text("select current_database()")).scalar()
            c.execute(text(f'ALTER DATABASE "{name}" SET timezone TO \'America/New_York\''))
        admin.dispose()

        from config import Config
        Config.SQLALCHEMY_DATABASE_URI = url
        from server import create_app
        from db.database import db
        from db.models import SensorMeasurement
        cls.db = db
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()

        def add(measurement, unit, when, value, group="Weather", station="22051538"):
            db.session.add(SensorMeasurement(station_id=station, group_type=group, measurement_type=measurement,
                                             unit=unit, value=value, recorded_at=when))
        t0 = dt.datetime(2026, 11, 1, 0, 0)
        for i, mm in enumerate((0.2, 0.4, 0.0, 1.0, 0.0, 0.2)):  # one hour of 10-minute rain readings
            add("Rain", "mm", t0 + dt.timedelta(minutes=10 * i), mm)
        add("Wind Direction", "°", t0, 350.0)
        add("Wind Direction", "°", t0 + dt.timedelta(minutes=10), 10.0)
        for i in range(6):
            add("Air Temperature", "°C", t0 + dt.timedelta(minutes=10 * i), 10.0 + i)
        add("Water Temperature", "°C", t0, 4.0, group="Logger", station="2577531")
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.drop_all()
        cls.ctx.pop()

    def series(self, start, end, *groups):
        q = "&".join([f"start={start}", f"end={end}"] + [f"group_type={g}" for g in groups])
        r = self.client.get(f"/api/series?{q}")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        return body, {s["measurement_type"]: s for s in body["series"]}

    def test_one_day_is_raw_and_times_are_utc_instants(self):
        body, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Weather")
        self.assertEqual((body["bucket_seconds"], body["aggregated"]), (600, False))
        air = by["Air Temperature"]
        self.assertEqual(air["avg"], [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        # 00:00 New York time on 2026-11-01 (EDT) is 04:00 UTC
        first = dt.datetime.fromtimestamp(air["t"][0] / 1000, dt.timezone.utc)
        self.assertEqual(first, dt.datetime(2026, 11, 1, 4, 0, tzinfo=dt.timezone.utc))

    def test_rain_is_summed_and_wind_direction_is_a_vector_mean(self):
        # 30 days -> 30-minute buckets: 00:00 holds the first three readings, 00:30 the next three
        body, by = self.series("2026-10-15T00:00:00", "2026-11-14T00:00:00", "Weather")
        self.assertEqual(body["bucket_seconds"], 1800)
        self.assertEqual([round(v, 4) for v in by["Rain"]["avg"]], [0.6, 1.2])
        self.assertEqual(by["Air Temperature"]["avg"], [11.0, 14.0])
        self.assertEqual((by["Air Temperature"]["min"], by["Air Temperature"]["max"]), ([10.0, 13.0], [12.0, 15.0]))
        direction = by["Wind Direction"]["avg"][0]
        self.assertTrue(direction < 0.01 or direction > 359.99, direction)  # 350° and 10° -> north, not 180°

    def test_only_the_requested_groups(self):
        body, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Logger")
        self.assertEqual(list(by), ["Water Temperature"])
        self.assertEqual(by["Water Temperature"]["avg"], [4.0])

    def test_bad_requests(self):
        self.assertEqual(self.client.get("/api/series?start=2026-11-01&end=2026-11-02").status_code, 400)
        self.assertEqual(self.client.get("/api/series?start=x&end=y&group_type=Weather").status_code, 400)
        self.assertEqual(self.client.get("/api/series?start=2026-11-02&end=2026-11-01&group_type=Weather").status_code, 400)


if __name__ == "__main__":
    unittest.main()
