# This file defines the /api/windrose route: how often the wind blew from each of 16 directions at each speed, for
# a date range, counted in PostgreSQL. The wind rose chart used to download every raw reading to count them in the
# browser, which was slow and refused (413) for long ranges; this answers any range with a few hundred numbers.
#
# GET /api/windrose?start=<ISO>&end=<ISO>[&speed=Wind Speed][&speed=Gust Speed]
# -> {"sectors": ["N", "NNE", ...16],
#     "speed_classes": [{"name": "<0.5 m/s", "from": 0, "to": 0.5}, ..., {"name": ">10 m/s", "from": 10, "to": null}],
#     "roses": {"Wind Speed": {"total": 1234, "counts": [[16 ints] per speed class],
#                              "percent": [[16 floats] per speed class]}, "Gust Speed": {...}}}
#
# A reading counts when the station recorded a direction and the speed at the same time (as the browser did).
# Sector i covers i * 22.5° ± 11.25° (so N is 348.75°-11.25°). Percentages are of all the readings of that speed
# type, rounded to 0.1. start/end follow /api/series: an ISO time with an offset is a real instant, one without
# is Toronto wall-clock time.
#
# Caching, as /api/series does it: the range is narrowed to 10-minute marks (where readings fall, so the counts don't
# change), and the answer is kept in Redis (utils/response_cache.py) for as long as /api/series keeps one for a range
# ending at the same time, under a hash of the narrowed range and the speed types. An answer is a few kilobytes.

import hashlib
import json
from datetime import datetime

from flask import current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from db.database import db
from utils import response_cache
from utils.parsers import SENTINEL_MAX
from utils.timezone import EST_TZ
from .series import browser_cache_control, local_naive, max_age, parse_iso, snap_range

SECTORS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
# Upper edges of the speed classes (m/s); a speed of exactly an edge belongs to the class above it.
SPEED_EDGES = [0.5, 2, 4, 6, 8, 10]
SPEEDS = ("Wind Speed", "Gust Speed")
STATEMENT_TIMEOUT = "15s"  # a range this query can't count in time gets a clear error instead of tying up the DB
QUERY_CANCELED = "57014"  # PostgreSQL's SQLSTATE for a statement cancelled by statement_timeout


def speed_classes():
    lows = [0] + SPEED_EDGES
    highs = SPEED_EDGES + [None]
    return [{"name": f"<{hi} m/s" if lo == 0 else f">{lo} m/s" if hi is None else f"{lo}-{hi} m/s",
             "from": lo, "to": hi} for lo, hi in zip(lows, highs)]


# width_bucket(x, edges) is 0 below the first edge and len(edges) at or above the last: the speed class index.
# The direction is first wrapped into [0, 360), so 360° and -20° count as N and NNW. NaN and ±Infinity readings are
# left out (numeric can't hold an infinity), and so are directions at or below the vendors' "no reading" sentinel
# (-100000, stored before ingestion skipped it), which would otherwise wrap to a real direction.
SQL = text(f"""
WITH dir AS (
  SELECT station_id, recorded_at, value AS deg
  FROM sensor_measurements
  WHERE group_type = 'Weather' AND measurement_type = 'Wind Direction'
    AND recorded_at BETWEEN :s AND :e AND value IS NOT NULL AND value <> ALL ('{{NaN,Infinity,-Infinity}}'::float8[])
    AND value > {SENTINEL_MAX}
), spd AS (
  SELECT station_id, recorded_at, measurement_type, value AS ms
  FROM sensor_measurements
  WHERE group_type = 'Weather' AND measurement_type = ANY(:m)
    AND recorded_at BETWEEN :s AND :e AND value IS NOT NULL AND value <> ALL ('{{NaN,Infinity,-Infinity}}'::float8[]) AND value >= 0
)
SELECT spd.measurement_type,
       (floor((((dir.deg::numeric % 360) + 360) % 360 + 11.25) / 22.5)::int % 16) AS sector,
       width_bucket(spd.ms, CAST(:edges AS float8[])) AS speed_class,
       count(*) AS n
FROM dir JOIN spd USING (station_id, recorded_at)
GROUP BY 1, 2, 3
""")


def tabulate(rows, speeds):
    """Query rows (speed type, sector, class, count) -> one rose per requested speed type, zero-filled."""
    n_classes = len(SPEED_EDGES) + 1
    roses = {s: {"total": 0, "counts": [[0] * len(SECTORS) for _ in range(n_classes)]} for s in speeds}
    for measurement, sector, speed_class, n in rows:
        rose = roses.get(measurement)
        if rose is None:
            continue
        rose["counts"][int(speed_class)][int(sector)] += int(n)
        rose["total"] += int(n)
    for rose in roses.values():
        total = rose["total"]
        rose["percent"] = [[round(c * 100 / total, 1) if total else 0 for c in row] for row in rose["counts"]]
    return roses


def cache_key(start, end, speeds):
    """The Redis key for a narrowed range and its speed types: a hash of their JSON, as in series.cache_key."""
    parts = [start.isoformat(), end.isoformat(), sorted(speeds)]
    return "windrose:v1:" + hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def register_windrose_route(app):
    @app.route("/api/windrose", methods=["GET"])
    def get_windrose():
        start, end = request.args.get("start"), request.args.get("end")
        asked = request.args.getlist("speed")
        if not start or not end:
            return jsonify({"error": "Missing required parameters: start and end"}), 400
        if any(s not in SPEEDS for s in asked):
            return jsonify({"error": "speed must be Wind Speed or Gust Speed"}), 400
        speeds = [s for s in SPEEDS if s in asked] if asked else list(SPEEDS)
        try:
            start_in, end_in = parse_iso(start), parse_iso(end)
            start_dt, end_dt = local_naive(start_in), local_naive(end_in)
        except (ValueError, OverflowError):
            return jsonify({"error": "Invalid date format"}), 400
        if start_in.tzinfo and end_in.tzinfo:
            # Compared as instants; inside the hour repeated when clocks fall back the wall-clock bounds can run
            # backwards, so they're put in order for the query (as /api/series does).
            if end_in <= start_in:
                return jsonify({"error": "end must be after start"}), 400
            start_dt, end_dt = min(start_dt, end_dt), max(start_dt, end_dt)
        elif end_dt <= start_dt:
            return jsonify({"error": "end must be after start"}), 400

        now = datetime.now(EST_TZ).replace(tzinfo=None)
        age = max_age(end_dt, now)
        start_dt, end_dt = snap_range(start_dt, end_dt)
        key = cache_key(start_dt, end_dt, speeds)
        hit = response_cache.get(key)
        seconds_left = None
        if hit is not None:
            body, seconds_left = hit
            response = current_app.response_class(body, mimetype="application/json")
        else:
            db.session.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
            try:
                rows = db.session.execute(SQL, {"s": start_dt, "e": end_dt, "m": speeds,
                                                "edges": SPEED_EDGES}).fetchall()
            except OperationalError as error:
                db.session.rollback()
                if getattr(error.orig, "pgcode", None) == QUERY_CANCELED:
                    return jsonify({"error": "That range took too long to count. Please pick a shorter one."}), 504
                raise
            response = jsonify({"sectors": SECTORS, "speed_classes": speed_classes(),
                                "roses": tabulate(rows, speeds)})
            response_cache.put(key, response.get_data(), age)
        response.headers["Cache-Control"] = browser_cache_control(end_dt, now, seconds_left)
        return response
