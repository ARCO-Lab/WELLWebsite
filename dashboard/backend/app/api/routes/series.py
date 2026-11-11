# This file defines the /api/series route: sensor readings for charts, aggregated in PostgreSQL to about two
# thousand points per series, so any date range (even the whole history) loads in about a second.
#
# GET /api/series?start=<ISO>&end=<ISO>&group_type=Weather&group_type=Logger...
# -> {"bucket_seconds": 43200, "aggregated": true,
#     "series": [{"group_type", "station_id", "measurement_type", "unit", "agg",
#                 "t": [epoch ms, UTC], "avg": [...], "min": [...], "max": [...]}, ...]}
#
# start/end: an ISO time with an offset (e.g. ...Z) is a real instant; one without is local wall-clock time
# (utils.timezone.parse_instant). recorded_at is an instant (timestamptz); readings are bucketed on its America/Toronto
# wall-clock time from 3-hour buckets up, so those follow local time (daily buckets are local days); buckets of up to an
# hour are on real time, which gives the same edges (Toronto's offsets are whole hours) and keeps the two readings of
# the hour repeated when clocks fall back apart. `t` is each bucket's start as a real instant. The zone is named in
# the SQL, so the result doesn't depend on the session's TimeZone setting.
#
# `agg` says what each series' `avg` holds:
#   "mean"        the mean of the readings in the bucket; min/max are the smallest and largest reading.
#   "sum"         (Rain) the bucket's total, since the gauge reports mm per interval; min/max are still the
#                 smallest and largest single reading, not totals.
#   "vector_mean" (Wind Direction) the mean of the directions as unit vectors, so 350° and 10° give 0°, not 180°;
#                 min/max are null, because a linear min/max of angles (10° and 350° for a northerly) means nothing.
#
# Caching: start is rounded up and end down to a 10-minute mark. Readings fall on those marks, so this selects the
# same readings as the request (no bucket is added at either edge), while visitors who open the same view a few
# minutes apart share one cache key. The answer is kept in Redis (utils/response_cache.py) for 5 minutes for a
# range that ended over an hour ago, 1 minute otherwise, and browsers may reuse it for what is left of that time.

from datetime import datetime, timedelta, timezone

from flask import current_app, jsonify, request
from sqlalchemy import bindparam, text

from db.database import db
from db.models import Instant
from utils import response_cache
from utils.timezone import EST_TZ, parse_instant

# Bucket sizes, smallest first. Every sensor reports every 10 minutes, so 600 s is the raw resolution.
LADDER = (600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600)
MAX_POINTS = 2000
GROUPS = {"Weather", "Quality", "Logger"}
AGG = {"Rain": "sum", "Wind Direction": "vector_mean"}  # every other measurement: "mean"
LOCAL_ZONE = EST_TZ.key  # 'America/Toronto', the site's zone
SNAP = timedelta(minutes=10)
RECENT = timedelta(hours=1)  # a range ending less long ago than this is still filling in, so reuse it briefly
MAX_AGE_RECENT, MAX_AGE_PAST = 60, 300  # seconds a response may be reused, by the cache and by browsers

SQL = text(f"""
WITH b AS (
  SELECT group_type, station_id, measurement_type, unit, value,
         -- Up to an hour, buckets on real time: Toronto's offsets are whole hours, so the edges are the same as on
         -- the wall clock, and the two copies of the hour repeated when clocks fall back stay apart. From 3 h,
         -- buckets on the wall clock, so they start at local 00:00, 03:00, ... (daily buckets are local days).
         CASE WHEN :b <= 3600 THEN to_timestamp(floor(extract(epoch FROM recorded_at) / :b) * :b)
              ELSE (to_timestamp(floor(extract(epoch FROM (recorded_at AT TIME ZONE '{LOCAL_ZONE}')) / :b) * :b)
                    AT TIME ZONE 'UTC') AT TIME ZONE '{LOCAL_ZONE}' END AS bucket
  FROM sensor_measurements
  WHERE recorded_at BETWEEN :s AND :e AND group_type = ANY(:g) AND value IS NOT NULL
)
SELECT group_type, station_id, measurement_type, unit,
       (extract(epoch FROM bucket) * 1000)::bigint AS t,
       CASE WHEN measurement_type = 'Rain' THEN sum(value)
            WHEN measurement_type = 'Wind Direction'
              THEN mod((degrees(atan2(avg(sin(radians(value))), avg(cos(radians(value))))) + 360)::numeric, 360)::float
            ELSE avg(value) END AS v,
       CASE WHEN measurement_type = 'Wind Direction' THEN NULL ELSE min(value) END AS lo,
       CASE WHEN measurement_type = 'Wind Direction' THEN NULL ELSE max(value) END AS hi
FROM b
GROUP BY group_type, station_id, measurement_type, unit, bucket
ORDER BY group_type, station_id, measurement_type, unit, bucket
""").bindparams(bindparam("s", type_=Instant), bindparam("e", type_=Instant))  # the bounds as instants


def pick_bucket(span_seconds, max_points=MAX_POINTS):
    """The smallest bucket that gives a series of this span about max_points points or fewer.

    Bucket edges don't line up with the range, so a series can get one point more than span / bucket. Spans
    longer than max_points days (about 5.5 years for 2,000) get daily buckets, the coarsest, and more points.
    """
    for bucket in LADDER:
        if span_seconds / bucket <= max_points:
            return bucket
    return LADDER[-1]


def floor_mark(t):
    """`t` rounded down to a 10-minute mark (the same marks in UTC and in Toronto: its offsets are whole hours)."""
    return t - timedelta(minutes=t.minute % 10, seconds=t.second, microseconds=t.microsecond)


def snap_range(start, end):
    """The range narrowed to 10-minute marks: start rounded up, end rounded down (unchanged if already on one).
    A range with no mark inside comes out with start after end, which matches nothing, as the request would."""
    start_up = floor_mark(start)
    if start_up != start:
        try:
            start_up += SNAP
        except OverflowError:  # within 10 minutes of datetime.max
            start_up = start
    return start_up, floor_mark(end)


def max_age(end, now):
    """How long an answer for a range ending at `end` may be reused; both are instants (aware UTC)."""
    return MAX_AGE_PAST if end < now - RECENT else MAX_AGE_RECENT


def cache_key(bucket, start, end, groups):
    """Everything the answer depends on: the query's parameters, after snap_range. The bounds are instants, so the
    two copies of the hour repeated when clocks fall back have different keys."""
    return f"series:v2:{bucket}:{start.isoformat()}:{end.isoformat()}:{','.join(sorted(set(groups)))}"


def _num(x):
    return None if x is None else round(float(x), 4)


def columnar(rows):
    """Query rows -> one {metadata, agg, t, avg, min, max} object per series, in row order."""
    series, out = {}, []
    for g, station, measurement, unit, t, v, lo, hi in rows:
        key = (g, station, measurement, unit)
        s = series.get(key)
        if s is None:
            s = series[key] = {"group_type": g, "station_id": station, "measurement_type": measurement,
                               "unit": unit, "agg": AGG.get(measurement, "mean"),
                               "t": [], "avg": [], "min": [], "max": []}
            out.append(s)
        s["t"].append(int(t))
        s["avg"].append(_num(v))
        s["min"].append(_num(lo))
        s["max"].append(_num(hi))
    return out


def register_series_route(app):
    @app.route("/api/series", methods=["GET"])
    def get_series():
        start, end = request.args.get("start"), request.args.get("end")
        groups = [g for g in request.args.getlist("group_type") if g in GROUPS]
        if not start or not end or not groups:
            return jsonify({"error": "Missing required parameters: start, end and at least one group_type"}), 400
        try:
            # Real instants, compared as such even inside the repeated fall-back hour (05:30Z then 06:10Z is
            # 01:30 EDT then 01:10 EST: later, though its wall clock reads earlier)
            start_dt, end_dt = parse_instant(start), parse_instant(end)
        except (ValueError, OverflowError):  # OverflowError: e.g. 0001-01-01T00:00+05:00 has no UTC time
            return jsonify({"error": "Invalid date format"}), 400
        if end_dt <= start_dt:
            return jsonify({"error": "end must be after start"}), 400

        bucket = pick_bucket((end_dt - start_dt).total_seconds())
        age = max_age(end_dt, datetime.now(timezone.utc))
        start_dt, end_dt = snap_range(start_dt, end_dt)
        key = cache_key(bucket, start_dt, end_dt, groups)
        hit = response_cache.get(key)
        if hit is not None:
            body, seconds_left = hit
            response = current_app.response_class(body, mimetype="application/json")
            age = min(age, seconds_left)  # so browsers don't keep it past the moment it expires here
        else:
            db.session.execute(text("SET LOCAL work_mem = '64MB'"))  # keeps the GROUP BY sort in memory (~3x faster)
            rows = db.session.execute(SQL, {"b": bucket, "s": start_dt, "e": end_dt, "g": groups}).fetchall()
            response = jsonify({"bucket_seconds": bucket, "aggregated": bucket > LADDER[0], "series": columnar(rows)})
            response_cache.put(key, response.get_data(), age)
        response.headers["Cache-Control"] = f"public, max-age={age}"
        return response
