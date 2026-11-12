# This file defines the /api/samples route for retrieving and filtering creek/point sampling data, and
# /api/samples/template.csv, the template for sampling files.

import pathlib

from flask import request, jsonify, send_file
from db.database import db
from db.models import SamplingMeasurement
from datetime import datetime

SAMPLING_TEMPLATE = pathlib.Path(__file__).resolve().parents[2] / "sampling_template.csv"

# Query flag -> creek_id stored with each sample (the same IDs utils/sampling_csv.py assigns on import).
CREEK_ID_MAP = {
    "ancaster": "19431905",
    "tiffany": "20962187",
    "sulphur": "3212839",
    "coldwater": "336415129",
    "spencer": "19755185"
}

def register_samples_route(app):
    @app.route("/api/samples", methods=["GET"])
    def get_filtered_samples():
        """Sampling rows with recorded_at between start and end (ISO, inclusive, naive America/Toronto wall time),
        ordered by time. Creek flags (?ancaster=true&...) narrow it to those creeks; with none set, every creek."""
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

        return jsonify(data)

    @app.route("/api/samples/template.csv", methods=["GET"])
    def sampling_csv_template():
        # The blank-with-examples template researchers fill in (format: docs/sampling-csv-format.md)
        return send_file(SAMPLING_TEMPLATE, mimetype="text/csv", as_attachment=True,
                         download_name="well_sampling_template.csv", max_age=3600)
