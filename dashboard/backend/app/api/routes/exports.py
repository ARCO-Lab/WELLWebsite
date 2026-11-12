# This file defines the /api/exports routes behind the dashboard's Download panel: a row estimate, a direct CSV
# download for small exports, and background jobs (run by the Celery worker, tasks/exports.py) for large ones.
# Job timestamps (created_at, expires_at) are naive America/Toronto wall time, like the sensor readings.
import hashlib
import os
import tempfile
import uuid

from flask import after_this_request, jsonify, request, send_file
from sqlalchemy import text

from api.services.exports import (
    default_export_filename,
    estimate_rows,
    live_jobs,
    normalize_export_payload,
    settle_if_stuck,
    write_export_csv,
)
from config import Config
from db.database import db
from db.models import ExportJob
from utils.timezone import est_now, est_passed


def register_export_routes(app):
    @app.route("/api/exports/estimate", methods=["POST"])
    def estimate_export_rows():
        """Counts the readings an export would contain and says whether to download it directly ("sync") or as a
        background job ("async"), so the page can choose before asking for the file."""
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
        """Builds the CSV in this request and sends it as a download. Refuses (413) above
        EXPORT_SYNC_ROW_THRESHOLD readings, which must use a background job instead."""
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
        """Queues a background export (202 with the job id). Refuses exports above EXPORT_MAX_ROWS (413), and
        new jobs when this visitor or the whole server already has too many running (429)."""
        payload = request.get_json(silent=True) or {}

        try:
            filters = normalize_export_payload(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        row_count = estimate_rows(filters)
        if row_count > Config.EXPORT_MAX_ROWS:
            return (
                jsonify(
                    {
                        "error": (
                            f"This export is too large ({row_count:,} readings; the limit is "
                            f"{Config.EXPORT_MAX_ROWS:,}). Choose a shorter date range or fewer measurements."
                        ),
                        "estimated_rows": row_count,
                        "max_rows": Config.EXPORT_MAX_ROWS,
                    }
                ),
                413,
            )

        job_id = str(uuid.uuid4())
        requester_fingerprint = _request_fingerprint()

        # Two requests at once could both pass the limits below before either job is saved; on PostgreSQL a
        # transaction lock (released at the commit or rollback) makes them take turns.
        if db.engine.dialect.name == "postgresql":
            db.session.execute(text("SELECT pg_advisory_xact_lock(hashtext('export_jobs_limits'))"))

        live = live_jobs()
        mine = sum(1 for live_job in live if live_job.requester_fingerprint == requester_fingerprint)
        if mine >= Config.EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "error": (
                            "You already have exports being prepared. Please wait for them to finish, "
                            "then try again."
                        )
                    }
                ),
                429,
            )
        if len(live) >= Config.EXPORT_MAX_ACTIVE_JOBS:
            db.session.rollback()
            return (
                jsonify({"error": "The server is busy preparing other exports. Please try again in a few minutes."}),
                429,
            )

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
        """A job's status and progress, polled by the page until it is ready, failed or expired."""
        job = db.session.get(ExportJob, job_id)
        if not job:
            return jsonify({"error": "Export job not found"}), 404

        # A job whose worker died (killed for memory, say) would read "running" until the hourly cleanup; settle
        # it here so the page stops waiting. The cleanup still deletes whatever it left behind.
        if settle_if_stuck(job):
            db.session.commit()

        response = job.to_dict()
        response["download_ready"] = job.status == "ready"
        return jsonify(response)

    @app.route("/api/exports/jobs/<job_id>/download", methods=["GET"])
    def download_export_artifact(job_id: str):
        """Sends a finished job's CSV: 409 while it isn't ready, 410 once it has expired or the file is gone."""
        job = db.session.get(ExportJob, job_id)
        if not job:
            return jsonify({"error": "Export job not found"}), 404

        if job.status != "ready":
            return jsonify({"error": "Export is not ready", "status": job.status}), 409

        if job.expires_at and est_passed(job.expires_at):
            job.status = "expired"  # keep artifact_path: the hourly cleanup deletes the file and clears it
            db.session.commit()
            return jsonify({"error": "Export artifact has expired"}), 410

        if not job.artifact_path or not os.path.exists(job.artifact_path):
            return jsonify({"error": "Export artifact missing"}), 410

        filename = job.artifact_name or default_export_filename(job.payload)
        return send_file(job.artifact_path, as_attachment=True, download_name=filename, mimetype="text/csv")


def client_ip() -> str:
    """The visitor's IP address. Flask has no public port: requests come from the dashboard's Next.js API routes,
    which send one address in X-Forwarded-For (lib/proxyBackend.ts). Which address that is, and when a reverse
    proxy's X-Forwarded-For is believed (only from TRUSTED_PROXY_IPS), is decided in lib/clientIp.ts. The last
    hop is taken here in case anything in between appends one."""
    hops = [hop.strip() for hop in request.headers.get("X-Forwarded-For", "").split(",") if hop.strip()]
    return hops[-1] if hops else (request.remote_addr or "")


def _request_fingerprint() -> str:
    # The IP alone, hashed so the address itself isn't stored: a User-Agent is set freely, so including it would
    # let one visitor get around the per-visitor job limit by changing it.
    return hashlib.sha256(client_ip().encode("utf-8")).hexdigest()
