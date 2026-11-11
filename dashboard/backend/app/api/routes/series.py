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
# wall-clock time, so buckets follow local time (daily buckets are local days), and `t` is each bucket start converted
# back to a real instant. Both readings of the hour repeated when clocks fall back are counted; they share that
# hour's local buckets. The zone is named in the SQL, so the result doesn't depend on the session's TimeZone setting.
#
# `agg` says what each series' `avg` holds:
#   "mean"        the mean of the readings in the bucket; min/max are the smallest and largest reading.
#   "sum"         (Rain) the bucket's total, since the gauge reports mm per interval; min/max are still the
#                 smallest and largest single reading, not totals.
#   "vector_mean" (Wind Direction) the mean of the directions as unit vectors, so 350° and 10° give 0°, not 180°;
#                 min/max are null, because a linear min/max of angles (10° and 350° for a northerly) means nothing.

from flask import jsonify, request
from sqlalchemy import bindparam, text

from db.database import db
from db.models import Instant
from utils.timezone import EST_TZ, parse_instant

# Bucket sizes, smallest first. Every sensor reports every 10 minutes, so 600 s is the raw resolution.
LADDER = (600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600)
MAX_POINTS = 2000
GROUPS = {"Weather", "Quality", "Logger"}
AGG = {"Rain": "sum", "Wind Direction": "vector_mean"}  # every other measurement: "mean"
LOCAL_ZONE = EST_TZ.key  # 'America/Toronto', the site's zone

SQL = text(f"""
WITH b AS (
  SELECT group_type, station_id, measurement_type, unit, value,
         to_timestamp(floor(extract(epoch FROM (recorded_at AT TIME ZONE '{LOCAL_ZONE}')) / :b) * :b) AT TIME ZONE 'UTC'
           AS bucket_local
  FROM sensor_measurements
  WHERE recorded_at BETWEEN :s AND :e AND group_type = ANY(:g) AND value IS NOT NULL
)
SELECT group_type, station_id, measurement_type, unit,
       (extract(epoch FROM (bucket_local AT TIME ZONE '{LOCAL_ZONE}')) * 1000)::bigint AS t,
       CASE WHEN measurement_type = 'Rain' THEN sum(value)
            WHEN measurement_type = 'Wind Direction'
              THEN mod((degrees(atan2(avg(sin(radians(value))), avg(cos(radians(value))))) + 360)::numeric, 360)::float
            ELSE avg(value) END AS v,
       CASE WHEN measurement_type = 'Wind Direction' THEN NULL ELSE min(value) END AS lo,
       CASE WHEN measurement_type = 'Wind Direction' THEN NULL ELSE max(value) END AS hi
FROM b
GROUP BY group_type, station_id, measurement_type, unit, bucket_local
ORDER BY group_type, station_id, measurement_type, unit, bucket_local
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
        db.session.execute(text("SET LOCAL work_mem = '64MB'"))  # keeps the GROUP BY sort in memory (~3x faster)
        rows = db.session.execute(SQL, {"b": bucket, "s": start_dt, "e": end_dt, "g": groups}).fetchall()
        return jsonify({"bucket_seconds": bucket, "aggregated": bucket > LADDER[0], "series": columnar(rows)})
