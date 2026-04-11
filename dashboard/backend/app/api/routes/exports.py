import hashlib
import os
import tempfile
import uuid

from flask import after_this_request, jsonify, request, send_file

from api.services.exports import normalize_export_payload, estimate_rows, write_export_csv, default_export_filename
from config import Config
from db.database import db
from db.models import ExportJob
from utils.timezone import est_now


def register_export_routes(app):
    @app.route("/api/exports/estimate", methods=["POST"])
    def estimate_export_rows():
        payload = request.get_json(silent=True) or {}
        print(f"[EXPORT API] /api/exports/estimate received payload keys: {payload.keys()}")
        print(f"[EXPORT API] /api/exports/estimate group_types: {payload.get('group_types', 'MISSING')}")
        try:
            filters = normalize_export_payload(payload)
            print(f"[EXPORT API] After normalization, group_types: {filters.get('group_types', 'MISSING')}")
            row_count = estimate_rows(filters)
            mode = "sync" if row_count <= Config.EXPORT_SYNC_ROW_THRESHOLD else "async"
            return jsonify(
                {
                    "estimated_rows": row_count,
                    "recommended_mode": mode,
                    "sync_threshold": Config.EXPORT_SYNC_ROW_THRESHOLD,
                    "poll_interval_seconds": Config.EXPORT_POLL_INTERVAL_SECONDS,
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/exports/sync", methods=["POST"])
    def export_sync():
        payload = request.get_json(silent=True) or {}
        print(f"[EXPORT API] /api/exports/sync received payload keys: {payload.keys()}")
        print(f"[EXPORT API] /api/exports/sync group_types: {payload.get('group_types', 'MISSING')}")

        try:
            filters = normalize_export_payload(payload)
            print(f"[EXPORT API] After normalization, group_types: {filters.get('group_types', 'MISSING')}")
            row_count = estimate_rows(filters)
            if row_count > Config.EXPORT_SYNC_ROW_THRESHOLD:
                return (
                    jsonify(
                        {
                            "error": "Export too large for sync mode",
                            "estimated_rows": row_count,
                            "sync_threshold": Config.EXPORT_SYNC_ROW_THRESHOLD,
                            "recommended_mode": "async",
                        }
                    ),
                    413,
                )

            os.makedirs(Config.EXPORTS_DIR, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix="sync_export_", suffix=".csv", dir=Config.EXPORTS_DIR)
            os.close(fd)

            write_export_csv(filters, tmp_path, estimated_rows=row_count)
            filename = default_export_filename(filters)

            @after_this_request
            def cleanup_file(response):
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except OSError:
                    pass
                return response

            return send_file(tmp_path, as_attachment=True, download_name=filename, mimetype="text/csv")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/exports/jobs", methods=["POST"])
    def create_export_job():
        payload = request.get_json(silent=True) or {}

        try:
            filters = normalize_export_payload(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        row_count = estimate_rows(filters)
        job_id = str(uuid.uuid4())
        requester_fingerprint = _request_fingerprint()

        job = ExportJob(
            id=job_id,
            status="queued",
            domain=filters["domain"],
            payload=filters,
            estimated_rows=row_count,
            produced_rows=0,
            progress_pct=0.0,
            requester_fingerprint=requester_fingerprint,
            created_at=est_now(),
        )
        db.session.add(job)
        db.session.commit()

        from tasks.exports import generate_export_job
        generate_export_job.delay(job_id)

        return (
            jsonify(
                {
                    "job_id": job_id,
                    "status": "queued",
                    "estimated_rows": row_count,
                    "poll_interval_seconds": Config.EXPORT_POLL_INTERVAL_SECONDS,
                }
            ),
            202,
        )

    @app.route("/api/exports/jobs/<job_id>", methods=["GET"])
    def get_export_job(job_id: str):
        job = db.session.get(ExportJob, job_id)
        if not job:
            return jsonify({"error": "Export job not found"}), 404

        response = job.to_dict()
        response["download_ready"] = job.status == "ready"
        return jsonify(response)

    @app.route("/api/exports/jobs/<job_id>/download", methods=["GET"])
    def download_export_artifact(job_id: str):
        job = db.session.get(ExportJob, job_id)
        if not job:
            return jsonify({"error": "Export job not found"}), 404

        if job.status != "ready":
            return jsonify({"error": "Export is not ready", "status": job.status}), 409

        if job.expires_at and est_now() > job.expires_at:
            job.status = "expired"
            job.artifact_path = None
            db.session.commit()
            return jsonify({"error": "Export artifact has expired"}), 410

        if not job.artifact_path or not os.path.exists(job.artifact_path):
            return jsonify({"error": "Export artifact missing"}), 410

        filename = job.artifact_name or default_export_filename(job.payload)
        return send_file(job.artifact_path, as_attachment=True, download_name=filename, mimetype="text/csv")


def _request_fingerprint() -> str:
    remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    user_agent = request.headers.get("User-Agent", "")
    raw = f"{remote_addr}|{user_agent}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
