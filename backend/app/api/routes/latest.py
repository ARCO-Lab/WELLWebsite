from flask import request, jsonify
import pandas as pd
from config import Config
from db.database import db
from db.models import SensorMeasurement

def register_latest_route(app, latest_metrics_cache):
    @app.route("/api/latest", methods=["GET"])
    def get_latest_metrics():
        subquery = db.session.query(
            SensorMeasurement.measurement_type,
            db.func.max(SensorMeasurement.recorded_at).label("max_time")
        ).group_by(SensorMeasurement.measurement_type).subquery()

        query = db.session.query(SensorMeasurement).join(
            subquery,
            db.and_(
                SensorMeasurement.measurement_type == subquery.c.measurement_type,
                SensorMeasurement.recorded_at == subquery.c.max_time
            )
        )

        results = [
            {
                "station_id": r.station_id,
                "group_type": r.group_type,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }
            for r in query.all()
        ]

        latest_metrics_cache["data"] = results

        return jsonify(results)