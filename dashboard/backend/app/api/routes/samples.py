# This file defines the /api/samples route for retrieving and filtering creek/point sampling data.
# (AI ANALYSIS DISABLED: it used to start a background summary of the result for the AI routes; see below.)

from flask import request, jsonify
from db.database import db
from db.models import SamplingMeasurement
from datetime import datetime

CREEK_ID_MAP = {
    "ancaster": "19431905",
    "tiffany": "20962187",
    "sulphur": "3212839",
    "coldwater": "336415129",
    "spencer": "19755185"
}

def register_samples_route(app, latest_sampling_summaries):
    @app.route("/api/samples", methods=["GET"])
    def get_filtered_samples():
        # Parse query parameters for date range and selected creeks
        start = request.args.get("start")
        end = request.args.get("end")

        # Check which creek flags are true and get corresponding creek_ids
        selected_creek_ids = [
            creek_id for creek_flag, creek_id in CREEK_ID_MAP.items()
            if request.args.get(creek_flag) == "true"
        ]

        if not start or not end:
            return jsonify({"error": "Missing required parameters: start and end"}), 400

        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400

        # Query the database for matching sampling measurements
        query = db.session.query(SamplingMeasurement).filter(
            SamplingMeasurement.recorded_at.between(start_dt, end_dt)
        )
        
        if selected_creek_ids:
            query = query.filter(SamplingMeasurement.creek_id.in_(selected_creek_ids))

        # Format query results as a list of dicts
        data = [
            {
                "site_id": r.site_id,
                "creek_id": r.creek_id,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }
            for r in query.order_by(SamplingMeasurement.recorded_at).all()
        ]

        # AI ANALYSIS DISABLED: a per-request thread used to summarize `data` with pandas
        # (scripts/downsample.summarize_sampling_data) into latest_sampling_summaries for the AI routes.
        # Nothing reads it while those routes are off, so commit 5b501eb deleted it.
        return jsonify(data)
