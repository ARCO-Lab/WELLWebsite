# This file defines the /api/latest route: the newest reading of every series, where a series is one
# (station_id, measurement_type) pair. The dashboard's Latest Data panel calls it on every page view and every
# 10 minutes per open tab, so it has to stay cheap as sensor_measurements grows.

from flask import jsonify
from db.database import db

# Walks the (station_id, measurement_type, recorded_at) unique index instead of reading the whole table:
# the recursive part hops from one series to the next (one index probe per series), and the final join
# picks each series' newest row (another probe). Nothing is bounded by time, so a series that stopped
# reporting long ago (such as Logger 5, last seen in 2025) still shows its last reading.
# Rows without a measurement_type are skipped; the previous GROUP BY join dropped them too (NULL never matched).
LATEST_PER_SERIES_SQL = db.text("""
WITH RECURSIVE series(station_id, measurement_type) AS (
    SELECT station_id, measurement_type FROM (
        SELECT station_id, measurement_type FROM sensor_measurements
        WHERE measurement_type IS NOT NULL
        ORDER BY station_id, measurement_type
        LIMIT 1
    ) AS first_series
    UNION ALL
    SELECT
        (SELECT n.station_id FROM sensor_measurements n
         WHERE n.measurement_type IS NOT NULL
           AND (n.station_id, n.measurement_type) > (s.station_id, s.measurement_type)
         ORDER BY n.station_id, n.measurement_type LIMIT 1),
        (SELECT n.measurement_type FROM sensor_measurements n
         WHERE n.measurement_type IS NOT NULL
           AND (n.station_id, n.measurement_type) > (s.station_id, s.measurement_type)
         ORDER BY n.station_id, n.measurement_type LIMIT 1)
    FROM series s
    WHERE s.station_id IS NOT NULL
)
SELECT m.station_id, m.group_type, m.measurement_type, m.value, m.unit, m.recorded_at
FROM series s
JOIN sensor_measurements m
  ON m.station_id = s.station_id
 AND m.measurement_type = s.measurement_type
 AND m.recorded_at = (
        SELECT max(x.recorded_at) FROM sensor_measurements x
        WHERE x.station_id = s.station_id AND x.measurement_type = s.measurement_type)
ORDER BY m.station_id, m.measurement_type
""").columns(recorded_at=db.DateTime)  # typed so SQLite (tests) also returns datetimes


def query_latest_per_series():
    """Newest row of each (station_id, measurement_type), as dicts in the /api/latest response shape."""
    return [
        {
            "station_id": r.station_id,
            "group_type": r.group_type,
            "measurement_type": r.measurement_type,
            "value": r.value,
            "unit": r.unit,
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in db.session.execute(LATEST_PER_SERIES_SQL)
    ]


# routes/__init__.py still passes a latest_metrics_cache; it is accepted and ignored, because nothing reads it.
def register_latest_route(app, latest_metrics_cache=None):
    @app.route("/api/latest", methods=["GET"])
    def get_latest_metrics():
        response = jsonify(query_latest_per_series())
        # The same for everyone, and readings arrive every 10 minutes: browsers may reuse it for up to a minute.
        # Nothing on the server caches it, so it is never more than a minute behind the database.
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
