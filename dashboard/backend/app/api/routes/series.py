# This file defines the /api/series route: sensor readings for charts, aggregated in PostgreSQL to at most a
# couple of thousand points per series, so any date range (even the whole history) loads in about a second.
#
# GET /api/series?start=<ISO>&end=<ISO>&group_type=Weather&group_type=Logger...
# -> {"bucket_seconds": 43200, "aggregated": true,
#     "series": [{"group_type", "station_id", "measurement_type", "unit",
#                 "t": [epoch ms, UTC], "avg": [...], "min": [...], "max": [...]}, ...]}
#
# Buckets follow local wall-clock time (recorded_at is stored as naive local time in the database's TimeZone,
# America/New_York), so daily buckets are local days; `t` converts each bucket start back to a real instant. Rain is summed per bucket (the gauge reports mm per interval) and wind direction is a vector
# mean, so 350° and 10° average to 0°, not 180°.

from datetime import datetime

from flask import jsonify, request
from sqlalchemy import text

from db.database import db

# Bucket sizes, smallest first. Every sensor reports every 10 minutes, so 600 s is the raw resolution.
LADDER = (600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600)
MAX_POINTS = 2000
GROUPS = {"Weather", "Quality", "Logger"}

SQL = text("""
WITH b AS (
  SELECT group_type, station_id, measurement_type, unit, value,
         to_timestamp(floor(extract(epoch FROM recorded_at) / :b) * :b) AT TIME ZONE 'UTC' AS bucket_local
  FROM sensor_measurements
  WHERE recorded_at BETWEEN :s AND :e AND group_type = ANY(:g) AND value IS NOT NULL
)
SELECT group_type, station_id, measurement_type, unit,
       (extract(epoch FROM (bucket_local AT TIME ZONE current_setting('TimeZone'))) * 1000)::bigint AS t,
       CASE WHEN measurement_type = 'Rain' THEN sum(value)
            WHEN measurement_type = 'Wind Direction'
              THEN mod((degrees(atan2(avg(sin(radians(value))), avg(cos(radians(value))))) + 360)::numeric, 360)::float
            ELSE avg(value) END AS v,
       min(value) AS lo, max(value) AS hi
FROM b
GROUP BY group_type, station_id, measurement_type, unit, bucket_local
ORDER BY group_type, station_id, measurement_type, unit, bucket_local
""")


def pick_bucket(span_seconds, max_points=MAX_POINTS):
    """The smallest bucket that keeps a series of this span at or under max_points points."""
    for bucket in LADDER:
        if span_seconds / bucket <= max_points:
            return bucket
    return LADDER[-1]


def columnar(rows):
    """Query rows -> one {metadata, t, avg, min, max} object per series, in row order."""
    series, out = {}, []
    for g, station, measurement, unit, t, v, lo, hi in rows:
        key = (g, station, measurement, unit)
        s = series.get(key)
        if s is None:
            s = series[key] = {"group_type": g, "station_id": station, "measurement_type": measurement,
                               "unit": unit, "t": [], "avg": [], "min": [], "max": []}
            out.append(s)
        s["t"].append(int(t))
        s["avg"].append(round(float(v), 4))
        s["min"].append(round(float(lo), 4))
        s["max"].append(round(float(hi), 4))
    return out


def register_series_route(app):
    @app.route("/api/series", methods=["GET"])
    def get_series():
        start, end = request.args.get("start"), request.args.get("end")
        groups = [g for g in request.args.getlist("group_type") if g in GROUPS]
        if not start or not end or not groups:
            return jsonify({"error": "Missing required parameters: start, end and at least one group_type"}), 400
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
        if end_dt <= start_dt:
            return jsonify({"error": "end must be after start"}), 400

        bucket = pick_bucket((end_dt - start_dt).total_seconds())
        db.session.execute(text("SET LOCAL work_mem = '64MB'"))  # keeps the GROUP BY sort in memory (~3x faster)
        rows = db.session.execute(SQL, {"b": bucket, "s": start_dt, "e": end_dt, "g": groups}).fetchall()
        return jsonify({"bucket_seconds": bucket, "aggregated": bucket > LADDER[0], "series": columnar(rows)})
