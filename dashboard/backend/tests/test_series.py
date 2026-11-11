"""Tests for /api/series (api/routes/series.py). Run from dashboard/backend: python -m unittest discover -s tests -t .

The SQL tests need PostgreSQL: set TEST_POSTGRES_URL to an empty, throwaway database (its tables are created and
dropped), e.g. a `docker run postgres:13` container. Without it they're skipped.
"""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.routes.series import LADDER, MAX_POINTS, columnar, pick_bucket  # noqa: E402
from utils.timezone import UTC, parse_instant  # noqa: E402

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

    def test_about_max_points_up_to_max_points_days(self):
        for days in (1, 3, 14, 45, 90, 180, 400, 900, 1500, MAX_POINTS):
            self.assertLessEqual(days * DAY / pick_bucket(days * DAY), MAX_POINTS, days)
        # past MAX_POINTS days (about 5.5 years) buckets stay daily, so there are more points
        self.assertGreater(3000 * DAY / pick_bucket(3000 * DAY), MAX_POINTS)


class BoundsTests(unittest.TestCase):
    """The route reads start/end with utils.timezone.parse_instant: an offset is an instant, none is Toronto time."""

    def test_aware_times_are_instants(self):
        self.assertEqual(parse_instant("2026-11-01T04:20:00Z"), dt.datetime(2026, 11, 1, 4, 20, tzinfo=UTC))
        self.assertEqual(parse_instant("2026-07-01T12:00:00-04:00"), dt.datetime(2026, 7, 1, 16, 0, tzinfo=UTC))

    def test_naive_times_are_taken_as_local(self):
        self.assertEqual(parse_instant("2026-11-01T00:20:00"), dt.datetime(2026, 11, 1, 4, 20, tzinfo=UTC))  # EDT

    def test_mixed_naive_and_aware_compare(self):
        start, end = parse_instant("2026-11-01T00:20:00"), parse_instant("2026-11-01T05:00:00Z")
        self.assertLess(start, end)  # comparing a naive with an aware time was a TypeError, and a 500


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

    def test_agg_says_what_avg_holds_and_null_min_max_pass_through(self):
        rows = [("Weather", "s", "Rain", "mm", 1000, 0.6, 0.0, 0.4),
                ("Weather", "s", "Wind Direction", "°", 1000, 0.0, None, None),
                ("Weather", "s", "Air Temperature", "°C", 1000, 11.0, 10.0, 12.0)]
        by = {s["measurement_type"]: s for s in columnar(rows)}
        self.assertEqual({m: s["agg"] for m, s in by.items()},
                         {"Rain": "sum", "Wind Direction": "vector_mean", "Air Temperature": "mean"})
        self.assertEqual((by["Wind Direction"]["min"], by["Wind Direction"]["max"]), ([None], [None]))


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the SQL against PostgreSQL")
class SeriesSqlTests(unittest.TestCase):
    # The session TimeZone every new database connection gets. The route must give the same answers whatever it
    # is, since nothing in the app sets it; UTC is what a fresh PostgreSQL (and the postgres image) defaults to.
    zone = "UTC"

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import event
        from config import Config

        # Set before importing server, which builds an app on import. create_app copies the URI, so it's restored
        # straight after and later test modules keep theirs.
        saved_uri = Config.SQLALCHEMY_DATABASE_URI
        Config.SQLALCHEMY_DATABASE_URI = os.environ["TEST_POSTGRES_URL"]
        try:
            from server import create_app
            cls.app = create_app()
        finally:
            Config.SQLALCHEMY_DATABASE_URI = saved_uri
        from db.database import db
        from db.models import SensorMeasurement
        cls.db = db
        cls.ctx = cls.app.app_context()
        cls.ctx.push()

        @event.listens_for(db.engine, "connect")
        def set_session_zone(dbapi_connection, _record):
            cur = dbapi_connection.cursor()
            cur.execute("SET TIME ZONE %s", (cls.zone,))
            cur.close()
            dbapi_connection.commit()  # psycopg2 opened a transaction; a rollback would undo the SET

        db.create_all()

        def add(measurement, unit, when, value, group="Weather", station="22051538"):
            db.session.add(SensorMeasurement(station_id=station, group_type=group, measurement_type=measurement,
                                             unit=unit, value=value, recorded_at=when))
        t0 = dt.datetime(2026, 11, 1, 0, 0)  # naive: Toronto wall-clock time (EDT here), stored as its instant
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
        cls.db.engine.dispose()
        cls.ctx.pop()

    def add_readings(self, measurement, unit, start, values, station="22051538"):
        from db.models import SensorMeasurement
        for i, value in enumerate(values):
            self.db.session.add(SensorMeasurement(station_id=station, group_type="Weather", unit=unit, value=value,
                                                  measurement_type=measurement,
                                                  recorded_at=start + dt.timedelta(minutes=10 * i)))
        self.db.session.commit()

    def delete_readings(self, measurement, since):
        from db.models import SensorMeasurement
        SensorMeasurement.query.filter(SensorMeasurement.measurement_type == measurement,
                                       SensorMeasurement.recorded_at >= since).delete()
        self.db.session.commit()

    def series(self, start, end, *groups):
        q = "&".join([f"start={start}", f"end={end}"] + [f"group_type={g}" for g in groups])
        r = self.client.get(f"/api/series?{q.replace('+', '%2B')}")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        return body, {s["measurement_type"]: s for s in body["series"]}

    def session_zone(self):
        from sqlalchemy import text
        return self.db.session.execute(text("SHOW TimeZone")).scalar()

    @staticmethod
    def utc(ms):
        return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)

    def test_session_zone_is_utc(self):
        self.assertEqual(self.session_zone(), "UTC")

    def test_one_day_is_raw_and_times_are_utc_instants(self):
        body, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Weather")
        self.assertEqual((body["bucket_seconds"], body["aggregated"]), (600, False))
        air = by["Air Temperature"]
        self.assertEqual(air["avg"], [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        # 00:00 Toronto time on 2026-11-01 (EDT) is 04:00 UTC
        self.assertEqual(self.utc(air["t"][0]), dt.datetime(2026, 11, 1, 4, 0, tzinfo=dt.timezone.utc))

    def test_z_suffixed_range_is_converted_to_local_time(self):
        # 04:20Z-05:00Z is 00:20-01:00 in Toronto (EDT): the last four readings, compared as instants.
        body, by = self.series("2026-11-01T04:20:00Z", "2026-11-01T05:00:00Z", "Weather")
        air = by["Air Temperature"]
        self.assertEqual(air["avg"], [12.0, 13.0, 14.0, 15.0])
        self.assertEqual(self.utc(air["t"][0]), dt.datetime(2026, 11, 1, 4, 20, tzinfo=dt.timezone.utc))
        _, by = self.series("2026-11-01T00:20:00-04:00", "2026-11-01T01:00:00-04:00", "Weather")
        self.assertEqual(by["Air Temperature"]["avg"], [12.0, 13.0, 14.0, 15.0])

    def test_same_answer_whatever_the_session_zone(self):
        ranges = (("2026-11-01T04:00:00Z", "2026-11-02T05:00:00Z"),  # an aware range
                  ("2026-11-01T00:00:00", "2026-11-02T00:00:00"))  # the same local day, naive
        expected = [self.series(start, end, "Weather")[0] for start, end in ranges]
        self.assertEqual(expected[0], expected[1])
        self.assertEqual(len(expected[0]["series"]), 3)  # Air Temperature, Rain, Wind Direction
        type(self).zone = "Asia/Tokyo"
        self.db.session.remove()
        self.db.engine.dispose()  # new connections, in the new zone
        try:
            self.assertEqual(self.session_zone(), "Asia/Tokyo")
            self.assertEqual([self.series(start, end, "Weather")[0] for start, end in ranges], expected)
        finally:
            type(self).zone = "UTC"
            self.db.session.remove()
            self.db.engine.dispose()

    def test_mixed_naive_and_aware_bounds(self):
        for start, end in (("2026-11-01T00:20:00", "2026-11-01T05:00:00Z"),
                           ("2026-11-01T04:20:00Z", "2026-11-01T01:00:00")):
            _, by = self.series(start, end, "Weather")
            self.assertEqual(by["Air Temperature"]["avg"], [12.0, 13.0, 14.0, 15.0], (start, end))

    def test_both_copies_of_the_fall_back_hour_are_kept_apart(self):
        # 01:00-01:30 happened twice on 2026-11-01: 05:00Z-05:30Z (EDT) and 06:00Z-06:30Z (EST). recorded_at holds both,
        # and 10-minute buckets are on real time, so each reading is its own bucket at its own instant.
        edt = dt.datetime(2026, 11, 1, 5, 0, tzinfo=UTC)
        self.add_readings("Air Temperature", "°C", edt, (20.0, 21.0, 22.0, 23.0))
        self.add_readings("Air Temperature", "°C", edt + dt.timedelta(hours=1), (30.0, 31.0, 32.0, 33.0))
        try:
            start, end = edt, edt + dt.timedelta(hours=2)
            body, by = self.series("2026-11-01T05:00:00Z", "2026-11-01T07:00:00Z", "Weather")
            self.assertEqual(body["bucket_seconds"], 600)
            air = by["Air Temperature"]
            self.assertEqual(air["avg"], [20.0, 21.0, 22.0, 23.0, 30.0, 31.0, 32.0, 33.0])
            self.assertEqual([self.utc(t) for t in air["t"]],
                             [edt + dt.timedelta(minutes=m) for m in (0, 10, 20, 30, 60, 70, 80, 90)])
            self.assertTrue(all(start <= self.utc(t) <= end for t in air["t"]))
            # A 40-minute range whose wall-clock times run backwards (01:30 EDT to 01:10 EST) is valid: it is
            # compared as instants, and holds 05:30Z, 06:00Z and 06:10Z, in that order.
            body, by = self.series("2026-11-01T05:30:00Z", "2026-11-01T06:10:00Z", "Weather")
            self.assertEqual(by["Air Temperature"]["avg"], [23.0, 30.0, 31.0])
            self.assertEqual([self.utc(t) for t in by["Air Temperature"]["t"]],
                             [edt + dt.timedelta(minutes=m) for m in (30, 60, 70)])
            r = self.client.get("/api/series?start=2026-11-01T06:10:00Z&end=2026-11-01T05:30:00Z&group_type=Weather")
            self.assertEqual(r.status_code, 400)
        finally:
            self.delete_readings("Air Temperature", edt)

    def test_real_time_buckets_match_wall_clock_buckets_on_ordinary_days(self):
        # Buckets of up to an hour are on real time; on any day without a clock change (summer, winter, and the days
        # either side of the change) their edges are exactly the wall-clock ones, because the offsets are whole hours.
        from sqlalchemy import text
        mismatches = self.db.session.execute(text("""
            SELECT count(*) FROM unnest(ARRAY[timestamptz '2026-07-01 04:00Z', '2026-01-15 05:00Z',
                                              '2026-10-31 04:00Z', '2026-11-02 05:00Z']) AS day,
                 generate_series(day, day + interval '1 day' - interval '1 minute', interval '1 minute') AS t,
                 unnest(ARRAY[600, 1800, 3600]) AS b
            WHERE to_timestamp(floor(extract(epoch FROM t) / b) * b)
               <> (to_timestamp(floor(extract(epoch FROM (t AT TIME ZONE 'America/Toronto')) / b) * b)
                   AT TIME ZONE 'UTC') AT TIME ZONE 'America/Toronto'""")).scalar()
        self.assertEqual(mismatches, 0)

    def test_rain_is_summed_and_wind_direction_is_a_vector_mean(self):
        # 30 days -> 30-minute buckets: 00:00 holds the first three readings, 00:30 the next three
        body, by = self.series("2026-10-15T00:00:00", "2026-11-14T00:00:00", "Weather")
        self.assertEqual(body["bucket_seconds"], 1800)
        rain, wind, air = by["Rain"], by["Wind Direction"], by["Air Temperature"]
        self.assertEqual((rain["agg"], wind["agg"], air["agg"]), ("sum", "vector_mean", "mean"))
        self.assertEqual([round(v, 4) for v in rain["avg"]], [0.6, 1.2])
        self.assertEqual((rain["min"], rain["max"]), ([0.0, 0.0], [0.4, 1.0]))  # single readings, not totals
        self.assertEqual(air["avg"], [11.0, 14.0])
        self.assertEqual((air["min"], air["max"]), ([10.0, 13.0], [12.0, 15.0]))
        direction = wind["avg"][0]
        self.assertTrue(direction < 0.01 or direction > 359.99, direction)  # 350° and 10° -> north, not 180°
        self.assertEqual((wind["min"], wind["max"]), ([None], [None]))  # a linear min/max of angles means nothing

    def test_only_the_requested_groups(self):
        body, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Logger")
        self.assertEqual(list(by), ["Water Temperature"])
        self.assertEqual(by["Water Temperature"]["avg"], [4.0])
        self.assertEqual(by["Water Temperature"]["agg"], "mean")

    def test_bad_requests(self):
        self.assertEqual(self.client.get("/api/series?start=2026-11-01&end=2026-11-02").status_code, 400)
        self.assertEqual(self.client.get("/api/series?start=x&end=y&group_type=Weather").status_code, 400)
        self.assertEqual(self.client.get("/api/series?start=2026-11-02&end=2026-11-01&group_type=Weather").status_code, 400)
        # an aware end that is, in local time (01:00 EDT), before a naive start
        self.assertEqual(self.client.get("/api/series?start=2026-11-01T02:00:00&end=2026-11-01T05:00:00Z"
                                         "&group_type=Weather").status_code, 400)


if __name__ == "__main__":
    unittest.main()
