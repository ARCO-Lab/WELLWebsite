# This file defines the /api/samples route for retrieving and filtering creek/point sampling data,
# /api/samples/template.csv (the template for sampling files), /api/samples/format (the canonical columns, sites and
# parameters) and /api/samples/validate (checks a CSV against the standard format without storing anything).

import pathlib

from flask import request, jsonify, send_file
from db.database import db
from db.models import SamplingMeasurement
from db.ordering import sampling_order
from utils.timezone import site_range
# The one source of truth for the sampling format (docs/sampling-csv-format.md renders it for people). validate_csv
# is pure: it reads no database and makes no network call, so /api/samples/validate below only checks, never stores.
from utils.sampling_csv import (
    CREEKS, OPTIONAL_COLUMNS, PARAMETERS, REQUIRED_COLUMNS, SITES, validate_csv,
)

SAMPLING_TEMPLATE = pathlib.Path(__file__).resolve().parents[2] / "sampling_template.csv"

# The most a /api/samples/validate request may carry. A real sampling CSV is a few KB to a few hundred KB (a year of
# readings is well under this); the cap keeps a pasted or dropped blob from using the backend's memory. The checker
# is a pre-upload convenience, so a file at the cap can still be checked for real by uploading it to Borealis.
MAX_VALIDATE_BYTES = 2_000_000

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
        """Sampling rows with recorded_at between start and end (ISO, inclusive). A time with an offset (...Z) is a
        real instant; one without is America/Toronto wall time, like recorded_at (utils/timezone.site_range).
        Ordered by time, then site, then parameter (db/ordering.py). Creek flags (?ancaster=true&...) narrow it to those creeks; with none set, every creek."""
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
            start_dt, end_dt = site_range(start, end)
        except (ValueError, OverflowError):
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
            for r in query.order_by(*sampling_order(db.engine.dialect.name)).all()
        ]

        return jsonify(data)

    @app.route("/api/samples/template.csv", methods=["GET"])
    def sampling_csv_template():
        # The blank-with-examples template researchers fill in (format: docs/sampling-csv-format.md)
        return send_file(SAMPLING_TEMPLATE, mimetype="text/csv", as_attachment=True,
                         download_name="well_sampling_template.csv", max_age=3600)

    @app.route("/api/samples/format", methods=["GET"])
    def sampling_format():
        """The canonical columns, sites and parameters, read straight from utils/sampling_csv, so the researcher
        upload guide renders its reference tables from the same lists the import checks against (never a second,
        hand-kept copy that could drift)."""
        return jsonify({
            "required_columns": list(REQUIRED_COLUMNS),
            "optional_columns": list(OPTIONAL_COLUMNS),
            "sites": [{"number": s.id, "name": s.name, "creek": CREEKS[s.creek][0]} for s in SITES],
            "parameters": [{"name": p.name, "unit": p.unit, "aliases": list(p.aliases)} for p in PARAMETERS],
        })

    @app.route("/api/samples/validate", methods=["POST"])
    def validate_sampling_csv():
        """Check sampling CSV text against the standard format and return every problem, with its row and column.
        Runs the real import validator (utils/sampling_csv.validate_csv), so the answer is exactly what the weekly
        Borealis import would say. It only checks: nothing is stored and the database is never touched. Used by the
        researcher upload-guide page's "Check my CSV format" tool.

        The CSV comes as JSON {"csv": "<text>"} or as the raw request body. The answer is
        {ok, problems: [{row, column, message}], summary, counts}."""
        too_large = (jsonify({"error": f"That file is too large to check here (the limit is "
                                       f"{MAX_VALIDATE_BYTES // 1000} KB). A sampling CSV is normally far smaller; "
                                       f"check the columns, or upload it to Borealis, which checks the file in "
                                       f"full."}), 413)
        if request.content_length and request.content_length > MAX_VALIDATE_BYTES:
            return too_large
        if request.is_json:
            payload = request.get_json(silent=True)
            text = payload.get("csv") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                return jsonify({"error": "Send the CSV as JSON {\"csv\": \"<file text>\"} or as the request body."}), 400
            data = text.encode("utf-8")
        else:
            data = request.get_data(cache=False, parse_form_data=False)
        if len(data) > MAX_VALIDATE_BYTES:
            return too_large

        result = validate_csv(data)
        return jsonify({
            "ok": result.ok,
            "problems": [{"row": e.row, "column": e.column, "message": e.message} for e in result.errors],
            "summary": result.summary() if result.ok else None,
            "counts": {
                "readings": len(result.records),
                "blank": result.blank,
                "rejected": result.rejected,
                "below_detection": result.below_detection,
            },
        })
