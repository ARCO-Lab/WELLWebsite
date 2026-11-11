# This file defines the /api/data route for retrieving raw sensor measurements for the dashboard's charts.
# A range with more readings than the charts can handle is refused with a 413 instead of being loaded.
# A request can't notice that the browser left: once it passes the count, its gunicorn thread stays busy until
# the query and jsonify finish, even if nobody is waiting for the answer. The row cap bounds that time, along
# with DB_STATEMENT_TIMEOUT_MS (config.py), which cancels any one query that runs too long.

import logging
import os
from datetime import datetime

from flask import request, jsonify

from db.database import db
from db.models import SensorMeasurement

log = logging.getLogger(__name__)

# More readings than this make a JSON payload of ~50 MB and take the browser too long to draw; about 90 days
# of every sensor group. Larger ranges get a 413 that tells the user to narrow the range or use Download.
DEFAULT_MAX_ROWS = 300_000


def parse_max_rows(value):
    """DATA_MAX_ROWS as a positive int; anything else (unset, empty, "300k", 0, -5) means the default."""
    if value is None or value.strip() == "":
        return DEFAULT_MAX_ROWS
    try:
        rows = int(value)
    except ValueError:
        rows = 0
    if rows <= 0:
        log.warning("DATA_MAX_ROWS=%r is not a positive whole number; using %d", value, DEFAULT_MAX_ROWS)
        return DEFAULT_MAX_ROWS
    return rows


# Read once at import, so a bad value is reported once and can't make every request fail.
MAX_ROWS = parse_max_rows(os.getenv("DATA_MAX_ROWS"))


def register_data_route(app):
    @app.route("/api/data", methods=["GET"])
    def get_filtered_data():
        # Parse query parameters
        start = request.args.get("start")
        end = request.args.get("end")
        group_types = request.args.getlist("group_type")

        if not start or not end or not group_types:
            return jsonify({"error": "Missing required parameters"}), 400

        try:
            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400

        filters = (
            SensorMeasurement.group_type.in_(group_types),
            SensorMeasurement.recorded_at.between(start_dt, end_dt),
        )

        # Count first: cheap even for the whole table, and it refuses an oversized range before a worker spends
        # minutes loading and serializing it (and the browser drawing it).
        total = db.session.query(db.func.count(SensorMeasurement.id)).filter(*filters).scalar()
        limit = MAX_ROWS
        if total > limit:
            return jsonify({
                "error": (f"This range has {total:,} readings, more than the {limit:,} the charts can show at once. "
                          "Pick a shorter range or fewer sensor groups, or use Download for the full data."),
                "rows": total,
                "max_rows": limit,
            }), 413

        # Only the columns the charts use, as plain rows rather than ORM objects
        rows = (
            db.session.query(
                SensorMeasurement.station_id,
                SensorMeasurement.group_type,
                SensorMeasurement.measurement_type,
                SensorMeasurement.value,
                SensorMeasurement.unit,
                SensorMeasurement.recorded_at,
            )
            .filter(*filters)
            .order_by(SensorMeasurement.recorded_at)
            .all()
        )
        data = [
            {
                "station_id": r.station_id,
                "group_type": r.group_type,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat(),
            }
            for r in rows
        ]
        return jsonify(data)
