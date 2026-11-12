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
from api.routes.series import (  # noqa: E402
    LADDER, MAX_POINTS, browser_cache_control, cache_key, columnar, parse_bucket, parse_filters, pick_bucket,
    to_local_naive)
from werkzeug.datastructures import MultiDict  # noqa: E402

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


class ParseBucketTests(unittest.TestCase):
    def test_only_ladder_values(self):
        self.assertIsNone(parse_bucket(None))
        self.assertIsNone(parse_bucket(""))
        for b in LADDER:
            self.assertEqual(parse_bucket(str(b)), b)
        for bad in ("601", "0", "-600", "600.0", "abc", "1e3", " 600"):
            with self.assertRaises(ValueError, msg=bad):
                parse_bucket(bad)


class BrowserCacheControlTests(unittest.TestCase):
    now = dt.datetime(2026, 11, 11, 12, 0)

    def test_settled_ranges_for_a_few_hours(self):
        self.assertEqual(browser_cache_control(self.now - dt.timedelta(days=2), self.now), "public, max-age=10800")
        self.assertEqual(browser_cache_control(self.now - dt.timedelta(days=2), self.now, seconds_left=5),
                         "public, max-age=10800")  # not immutable: a backfill can still change old readings

    def test_anything_newer_a_minute_at_most(self):
        self.assertEqual(browser_cache_control(self.now - dt.timedelta(hours=23), self.now), "public, max-age=60")
        self.assertEqual(browser_cache_control(self.now, self.now, seconds_left=42), "public, max-age=42")
        self.assertEqual(browser_cache_control(self.now, self.now, seconds_left=300), "public, max-age=60")


class CacheKeyTests(unittest.TestCase):
    start, end = dt.datetime(2026, 11, 1), dt.datetime(2026, 11, 2)

    def key(self, query):
        filters, groups = parse_filters(MultiDict(query))
        return cache_key(600, self.start, self.end, ["Logger", *groups], filters)

    def test_one_value_with_a_separator_cant_stand_for_two(self):
        # Two measurements, as a chart asks; then one value that joined with "," used to give the same key
        two = self.key([("measurement_type", "Level"), ("measurement_type", "Water Temperature")])
        with self.assertRaises(ValueError):
            self.key([("measurement_type", "Level,Water Temperature")])
        one = self.key([("measurement_type", "Level")])
        self.assertNotEqual(one, two)
        # The key covers every part: groups, filters, bucket and range
        self.assertNotEqual(self.key([("station_id", "1")]), self.key([("measurement_type", "1")]))
        self.assertNotEqual(cache_key(600, self.start, self.end, ["Logger"]), cache_key(1800, self.start, self.end, ["Logger"]))
        self.assertEqual(two, self.key([("measurement_type", "Water Temperature"), ("measurement_type", "Level")]))

    def test_separators_in_values_are_refused(self):
        for query in ([("station_id", "1|2")], [("station_id", "1,2")], [("measurement_type", "a|b")],
                      [("series", "Logger|1,2|Level")], [("series", "Logger|1|Level,Rain")]):
            with self.assertRaises(ValueError, msg=query):
                parse_filters(MultiDict(query))


class ToLocalNaiveTests(unittest.TestCase):
    def test_aware_times_become_toronto_wall_clock(self):
        self.assertEqual(to_local_naive("2026-11-01T04:20:00Z"), dt.datetime(2026, 11, 1, 0, 20))  # EDT
        self.assertEqual(to_local_naive("2026-11-02T05:00:00+00:00"), dt.datetime(2026, 11, 2, 0, 0))  # EST
        self.assertEqual(to_local_naive("2026-07-01T12:00:00-04:00"), dt.datetime(2026, 7, 1, 12, 0))

    def test_naive_times_are_taken_as_local(self):
        self.assertEqual(to_local_naive("2026-11-01T00:20:00"), dt.datetime(2026, 11, 1, 0, 20))

    def test_mixed_naive_and_aware_compare(self):
        start, end = to_local_naive("2026-11-01T00:20:00"), to_local_naive("2026-11-01T05:00:00Z")
        self.assertIsNone(start.tzinfo)
        self.assertIsNone(end.tzinfo)
        self.assertLess(start, end)  # comparing a naive with an aware time was a TypeError, and a 500


class ColumnarTests(unittest.TestCase):
    def test_groups_rows_into_series_in_order(self):
        rows = [("Weather", "s", "Rain", "mm", 1000, 0.2, 0.0, 0.2, 3),
                ("Weather", "s", "Rain", "mm", 2000, 0.0, 0.0, 0.0, 6),
                ("Logger", "l", "Water Temperature", "°C", 1000, 5.12345, 5.0, 5.3, 1)]
        out = columnar(rows)
        self.assertEqual([(s["group_type"], s["measurement_type"]) for s in out],
                         [("Weather", "Rain"), ("Logger", "Water Temperature")])
        self.assertEqual(out[0]["t"], [1000, 2000])
        self.assertEqual(out[1]["avg"], [5.1235])
        self.assertEqual((out[1]["min"], out[1]["max"]), ([5.0], [5.3]))
        self.assertEqual((out[0]["n"], out[1]["n"]), ([3, 6], [1]))  # readings per bucket

    def test_agg_says_what_avg_holds_and_null_min_max_pass_through(self):
        rows = [("Weather", "s", "Rain", "mm", 1000, 0.6, 0.0, 0.4, 3),
                ("Weather", "s", "Wind Direction", "°", 1000, 0.0, None, None, 2),
                ("Weather", "s", "Air Temperature", "°C", 1000, 11.0, 10.0, 12.0, 3)]
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
        t0 = dt.datetime(2026, 11, 1, 0, 0)  # naive Toronto wall-clock time, as ingestion stores it (EDT here)
        for i, mm in enumerate((0.2, 0.4, 0.0, 1.0, 0.0, 0.2)):  # one hour of 10-minute rain readings
            add("Rain", "mm", t0 + dt.timedelta(minutes=10 * i), mm)
        add("Wind Direction", "°", t0, 350.0)
        add("Wind Direction", "°", t0 + dt.timedelta(minutes=10), 10.0)
        for i in range(6):
            add("Air Temperature", "°C", t0 + dt.timedelta(minutes=10 * i), 10.0 + i)
        add("Water Temperature", "°C", t0, 4.0, group="Logger", station="2577531")
        # Quality readings around a vendor "no reading" sentinel (-100000, as stored on 2026-06-12) and values that
        # aren't finite (rows stored before ingestion skipped them); /api/series must leave all of those out.
        for i, value in enumerate((8.0, -100000.0, 9.0, float("nan"), float("-inf"), float("inf"))):
            add("ODO", "mg/L", t0 + dt.timedelta(minutes=10 * i), value, group="Quality", station="4501")
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
        # 04:20Z-05:00Z is 00:20-01:00 in Toronto (EDT): the last four readings. Bound as aware times, PostgreSQL
        # would have read them in the session zone (UTC here) and matched nothing.
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

    def test_aware_range_inside_the_fall_back_hour(self):
        # 05:30Z is 01:30 EDT and 06:10Z is 01:10 EST: a 40-minute range whose wall-clock times run backwards.
        # It's valid (compared as instants) and queries the naive 01:10-01:30 readings.
        self.add_readings("Air Temperature", "°C", dt.datetime(2026, 11, 1, 1, 0), (20.0, 21.0, 22.0, 23.0))
        try:
            body, by = self.series("2026-11-01T05:30:00Z", "2026-11-01T06:10:00Z", "Weather")
            self.assertEqual(body["bucket_seconds"], 600)
            self.assertEqual(by["Air Temperature"]["avg"], [21.0, 22.0, 23.0])
            r = self.client.get("/api/series?start=2026-11-01T06:10:00Z&end=2026-11-01T05:30:00Z&group_type=Weather")
            self.assertEqual(r.status_code, 400)
        finally:
            self.delete_readings("Air Temperature", dt.datetime(2026, 11, 1, 1, 0))

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

    def test_readings_per_bucket(self):
        _, by = self.series("2026-10-15T00:00:00", "2026-11-14T00:00:00", "Weather")  # 30-minute buckets
        self.assertEqual(by["Air Temperature"]["n"], [3, 3])
        self.assertEqual(by["Rain"]["n"], [3, 3])
        self.assertEqual(by["Wind Direction"]["n"], [2])  # counted though its min/max are null
        _, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Weather")  # raw: one reading each
        self.assertEqual(by["Air Temperature"]["n"], [1] * 6)

    def test_sentinel_and_non_finite_values_are_left_out(self):
        _, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Quality")
        odo = by["ODO"]
        self.assertEqual((odo["avg"], odo["n"]), ([8.0, 9.0], [1, 1]))  # 00:00 and 00:20; 00:10 was -100000
        _, by = self.series("2026-10-15T00:00:00", "2026-11-14T00:00:00", "Quality")
        odo = by["ODO"]
        self.assertEqual((odo["avg"], odo["min"], odo["max"], odo["n"]), ([8.5], [8.0], [9.0], [2]))

    def test_only_the_requested_groups(self):
        body, by = self.series("2026-11-01T00:00:00", "2026-11-02T00:00:00", "Logger")
        self.assertEqual(list(by), ["Water Temperature"])
        self.assertEqual(by["Water Temperature"]["avg"], [4.0])
        self.assertEqual(by["Water Temperature"]["agg"], "mean")

    def test_answers_are_cached_by_rounded_range_and_marked_cacheable(self):
        from unittest import mock
        from utils import response_cache
        bodies, ttls = {}, {}

        def put(key, body, ttl):
            bodies[key], ttls[key] = body, ttl

        def get(key):
            return (bodies[key], ttls[key]) if key in bodies else None

        with mock.patch.object(response_cache, "get", side_effect=get), \
                mock.patch.object(response_cache, "put", side_effect=put):
            # A range that ended over a day ago: stored for an hour, and browsers may keep it for a day.
            r = self.client.get("/api/series?start=2026-11-01T00:03:00&end=2026-11-01T00:58:00&group_type=Weather")
            self.assertEqual(r.headers["Cache-Control"], "public, max-age=10800")
            (key, body), = bodies.items()
            self.assertEqual(ttls[key], 3600)
            # rounded inward to 10-min marks
            self.assertEqual(key, cache_key(600, dt.datetime(2026, 11, 1, 0, 10), dt.datetime(2026, 11, 1, 0, 50),
                                            ["Weather"], {"st": None, "m": None, "k": None}))
            self.assertEqual(body, r.get_data())
            self.assertEqual(r.get_json()["series"][0]["avg"], [11.0, 12.0, 13.0, 14.0, 15.0])  # as unrounded

            # A request a few minutes apart is the same rounded range, answered from the cache, not the database.
            bodies[key], ttls[key] = b'{"cached": true}', 42
            r = self.client.get("/api/series?start=2026-11-01T00:08:00&end=2026-11-01T00:51:00&group_type=Weather")
            self.assertEqual(r.get_json(), {"cached": True})
            self.assertEqual(r.headers["Cache-Control"], "public, max-age=10800")

            # A range that ended two hours ago: stored for 5 minutes; browsers get a minute at most, and no longer
            # than the cached copy has left.
            now = dt.datetime.now(dt.timezone.utc)
            started, ended = ((now - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:00Z") for h in (5, 2))
            bodies.clear()
            r = self.client.get(f"/api/series?start={started}&end={ended}&group_type=Weather")
            self.assertEqual(r.headers["Cache-Control"], "public, max-age=60")
            (key,) = bodies
            self.assertEqual(ttls[key], 300)
            ttls[key] = 42
            r = self.client.get(f"/api/series?start={started}&end={ended}&group_type=Weather")
            self.assertEqual(r.headers["Cache-Control"], "public, max-age=42")

            # The bucket and every filter are part of the key
            bodies.clear()
            for q in ("", "&bucket=1800", "&series=Weather|22051538|Rain", "&station_id=22051538",
                      "&measurement_type=Rain"):
                self.client.get(f"/api/series?start=2026-11-01T00:00:00&end=2026-11-01T01:00:00&group_type=Weather{q}")
            self.assertEqual(len(bodies), 5)

        # A range that runs to now: a minute only.
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self.client.get(f"/api/series?start=2026-11-01T00:00:00Z&end={now}&group_type=Weather")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Cache-Control"], "public, max-age=60")

    def test_an_end_just_before_a_bucket_adds_no_point(self):
        # Charts send end = range end - 1 ms; the next bucket's first reading must not appear as an extra point.
        _, by = self.series("2026-10-31T00:00:00", "2026-10-31T23:59:59.999", "Weather")
        self.assertNotIn("Air Temperature", by)  # its first reading is at 2026-11-01 00:00
        _, by = self.series("2026-11-01T00:00:00", "2026-11-01T00:29:59.999", "Weather")
        self.assertEqual(by["Air Temperature"]["avg"], [10.0, 11.0, 12.0])

    def get(self, query):
        return self.client.get(f"/api/series?{query.replace('+', '%2B')}")

    def test_an_asked_bucket_is_used(self):
        body = self.get("start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Weather&bucket=1800").get_json()
        self.assertEqual((body["bucket_seconds"], body["aggregated"]), (1800, True))
        air = next(s for s in body["series"] if s["measurement_type"] == "Air Temperature")
        self.assertEqual((air["avg"], air["n"]), ([11.0, 14.0], [3, 3]))
        body = self.get("start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Weather&bucket=600").get_json()
        self.assertEqual(body["bucket_seconds"], 600)

    def test_bucket_must_be_on_the_ladder_and_points_are_capped(self):
        base = "start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Weather"
        for bad in ("601", "abc", "0", "-600"):
            r = self.get(f"{base}&bucket={bad}")
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("bucket", r.get_json()["error"])
        # 28 days of 10-minute buckets is 4,032 points per series: too many. 27 days (3,888) is allowed.
        r = self.get("start=2026-10-01T00:00:00&end=2026-10-29T00:00:00&group_type=Weather&bucket=600")
        self.assertEqual(r.status_code, 400)
        self.assertIn("4000", r.get_json()["error"])
        self.assertEqual(self.get("start=2026-10-01T00:00:00&end=2026-10-28T00:00:00&group_type=Weather"
                                  "&bucket=600").status_code, 200)
        # Without a bucket: a span so long that even daily buckets are too many (over ~11 years)
        r = self.get("start=2000-01-01T00:00:00&end=2026-01-01T00:00:00&group_type=Weather")
        self.assertEqual(r.status_code, 400)

    def test_series_keys_pick_exact_series_without_group_type(self):
        body = self.get("start=2026-11-01T00:00:00&end=2026-11-02T00:00:00"
                        "&series=Weather|22051538|Rain&series=Logger|2577531|Water Temperature").get_json()
        self.assertEqual(sorted((s["group_type"], s["measurement_type"]) for s in body["series"]),
                         [("Logger", "Water Temperature"), ("Weather", "Rain")])
        # A key names one series exactly: the quality station's ODO isn't the weather station's
        body = self.get("start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&series=Weather|4501|ODO").get_json()
        self.assertEqual(body["series"], [])

    def test_station_and_measurement_filters(self):
        q = "start=2026-11-01T00:00:00&end=2026-11-02T00:00:00&group_type=Weather&group_type=Logger"
        body = self.get(f"{q}&station_id=2577531").get_json()
        self.assertEqual([s["measurement_type"] for s in body["series"]], ["Water Temperature"])
        body = self.get(f"{q}&measurement_type=Rain&measurement_type=Wind Direction").get_json()
        self.assertEqual(sorted(s["measurement_type"] for s in body["series"]), ["Rain", "Wind Direction"])
        body = self.get(f"{q}&station_id=22051538&measurement_type=Water Temperature").get_json()
        self.assertEqual(body["series"], [])

    def test_bad_filters(self):
        base = "start=2026-11-01T00:00:00&end=2026-11-02T00:00:00"
        too_many = "group_type=Weather&" + "&".join(f"station_id={i}" for i in range(41))
        for bad in ("series=Weather", "series=Weather|22051538", "series=Nope|1|Rain", "series=Weather||Rain",
                    "series=Weather|1|Rain|x", too_many, "group_type=Logger&measurement_type=Level,Water Temperature",
                    "group_type=Logger&station_id=1|2"):
            self.assertEqual(self.get(f"{base}&{bad}").status_code, 400, bad)

    def test_bad_requests(self):
        self.assertEqual(self.client.get("/api/series?start=2026-11-01&end=2026-11-02").status_code, 400)
        self.assertEqual(self.client.get("/api/series?start=x&end=y&group_type=Weather").status_code, 400)
        self.assertEqual(self.client.get("/api/series?start=2026-11-02&end=2026-11-01&group_type=Weather").status_code, 400)
        # an aware end that is, in local time (01:00 EDT), before a naive start
        self.assertEqual(self.client.get("/api/series?start=2026-11-01T02:00:00&end=2026-11-01T05:00:00Z"
                                         "&group_type=Weather").status_code, 400)


if __name__ == "__main__":
    unittest.main()
