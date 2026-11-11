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

from flask import jsonify, request
from sqlalchemy import text

from db.database import db
from .series import local_naive, parse_iso

SECTORS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
# Upper edges of the speed classes (m/s); a speed of exactly an edge belongs to the class above it.
SPEED_EDGES = [0.5, 2, 4, 6, 8, 10]
SPEEDS = ("Wind Speed", "Gust Speed")
STATEMENT_TIMEOUT = "15s"  # a range this query can't count in time gets a clear error instead of tying up the DB


def speed_classes():
    lows = [0] + SPEED_EDGES
    highs = SPEED_EDGES + [None]
    return [{"name": f"<{hi} m/s" if lo == 0 else f">{lo} m/s" if hi is None else f"{lo}-{hi} m/s",
             "from": lo, "to": hi} for lo, hi in zip(lows, highs)]


# width_bucket(x, edges) is 0 below the first edge and len(edges) at or above the last: the speed class index.
# The direction is first wrapped into [0, 360), so 360° and -10° count as N and NNW.
SQL = text("""
WITH dir AS (
  SELECT station_id, recorded_at, value AS deg
  FROM sensor_measurements
  WHERE group_type = 'Weather' AND measurement_type = 'Wind Direction'
    AND recorded_at BETWEEN :s AND :e AND value IS NOT NULL AND value <> 'NaN'
), spd AS (
  SELECT station_id, recorded_at, measurement_type, value AS ms
  FROM sensor_measurements
  WHERE group_type = 'Weather' AND measurement_type = ANY(:m)
    AND recorded_at BETWEEN :s AND :e AND value IS NOT NULL AND value <> 'NaN' AND value >= 0
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


def register_windrose_route(app):
    @app.route("/api/windrose", methods=["GET"])
    def get_windrose():
        start, end = request.args.get("start"), request.args.get("end")
        asked = request.args.getlist("speed")
        speeds = [s for s in SPEEDS if s in asked] if asked else list(SPEEDS)
        if not start or not end or not speeds:
            return jsonify({"error": "Missing required parameters: start, end (and speed, if given, must be "
                                     "Wind Speed or Gust Speed)"}), 400
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

        db.session.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        try:
            rows = db.session.execute(SQL, {"s": start_dt, "e": end_dt, "m": speeds, "edges": SPEED_EDGES}).fetchall()
        except Exception as error:  # noqa: BLE001 - only a cancelled (timed-out) statement gets its own answer
            db.session.rollback()
            if "statement timeout" in str(error):
                return jsonify({"error": "That range took too long to count. Please pick a shorter one."}), 503
            raise
        return jsonify({"sectors": SECTORS, "speed_classes": speed_classes(), "roses": tabulate(rows, speeds)})
