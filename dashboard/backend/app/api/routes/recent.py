# This file defines the /api/recent route: the latest creek sampling results, for the dashboard's sampling cards.
# For each measurement type it returns every row taken at that type's latest recorded_at (usually one sampling day,
# so one row per site). recorded_at is naive America/Toronto wall time.

from flask import jsonify
from db.database import db
from db.models import SamplingMeasurement

def register_recent_route(app):
    @app.route("/api/recent", methods=["GET"])
    def get_recent_sampling_metrics():
        # Subquery to get latest timestamp per measurement_type
        subquery = db.session.query(
            SamplingMeasurement.measurement_type,
            db.func.max(SamplingMeasurement.recorded_at).label("max_time")
        ).group_by(SamplingMeasurement.measurement_type).subquery()

        # Main query joins on measurement_type and latest timestamp
        query = db.session.query(SamplingMeasurement).join(
            subquery,
            db.and_(
                SamplingMeasurement.measurement_type == subquery.c.measurement_type,
                SamplingMeasurement.recorded_at == subquery.c.max_time
            )
        )

        # Format query results as a list of dicts
        results = [
            {
                "site_id": r.site_id,
                "creek_id": r.creek_id,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }
            for r in query.all()
        ]

        return jsonify(results)
