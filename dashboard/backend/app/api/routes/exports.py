# This file defines the /api/exports routes behind the dashboard's Download panel: a row estimate, a direct CSV
# download for small exports, and background jobs (run by the Celery worker, tasks/exports.py) for large ones.
# Job timestamps (created_at, expires_at) are naive America/Toronto wall time, like the sensor readings.
#
# Limits that keep exports from filling the disk the database shares: every export that writes a file is refused
# (507) when the disk would drop below EXPORT_MIN_FREE_MB with the file's estimated size (its rows times its
# columns, api/services/exports.export_size_bytes), and the writer stops any file that grows past what the disk can
# spare or EXPORT_MAX_FILE_MB anyway; each visitor may start EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER jobs an hour
# (429); and a request for an export that is already ready gets that job back instead of a new one.
#
# Only the validation messages written for the user (ExportValidationError) are passed on in a 400; any other error
# gets a fixed message, so nothing from the database driver or the code reaches the browser.
import hashlib
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

from flask import after_this_request, jsonify, request, send_file
from sqlalchemy import text

from api.services.exports import (
    EXPORT_QUEUE_DOWN_MESSAGE,
    ExportAborted,
    ExportValidationError,
    default_export_filename,
    disk_space_error,
    estimate_rows,
    jobs_started_since,
    live_jobs,
    normalize_export_payload,
    reusable_job,
    settle_if_stuck,
    write_budget,
    write_export_csv,
)
from config import Config
from db.database import db
from db.models import ExportJob
from utils.sentry import capture_job_error
from utils.timezone import est_now, est_passed

log = logging.getLogger(__name__)
INSUFFICIENT_STORAGE = 507


def _payload():
    """The request's JSON body, or {} when there is none or it isn't JSON. Anything else that isn't an object (a
    list, a string) is passed on as it is, so normalize_export_payload refuses it with a 400."""
    payload = request.get_json(silent=True)
    return {} if payload is None else payload


def _invalid(exc):
    """The 400 for a request that isn't a valid export: its message when it is one written for the user."""
    message = str(exc) if isinstance(exc, ExportValidationError) else "This export request isn't valid."
    return jsonify({"error": message}), 400


def _low_disk(row_count, filters):
    """The 507 answer when the exports disk is too full for this export of row_count readings, else None."""
    message = disk_space_error(row_count, filters)
    if message is None:
        return None
    log.warning("export refused: the exports disk is below EXPORT_MIN_FREE_MB")
    return jsonify({"error": message}), INSUFFICIENT_STORAGE


def _remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass   # best effort: the hourly cleanup removes leftover sync_export_* files


def register_export_routes(app):
    @app.route("/api/exports/estimate", methods=["POST"])
    def estimate_export_rows():
        """Counts the readings an export would contain and says whether to download it directly ("sync") or as a
        background job ("async"), so the page can choose before asking for the file."""
        try:
            filters = normalize_export_payload(_payload())
        except ValueError as exc:
            return _invalid(exc)
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

    @app.route("/api/exports/sync", methods=["POST"])
    def export_sync():
        """Builds the CSV in this request and sends it as a download. Refuses (413) above
        EXPORT_SYNC_ROW_THRESHOLD readings, which must use a background job instead, and stops (413 or 504) a file
        that outgrows the disk's room or EXPORT_MAX_FILE_MB, or takes over EXPORT_SYNC_MAX_SECONDS to build."""
        try:
            filters = normalize_export_payload(_payload())
        except ValueError as exc:
            return _invalid(exc)
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
        refused = _low_disk(row_count, filters)
        if refused:
            return refused

        os.makedirs(Config.EXPORTS_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="sync_export_", suffix=".csv", dir=Config.EXPORTS_DIR)
        os.close(fd)
        # From here the file is removed whatever happens: after the download is sent, or at once if building it
        # fails (a full disk, a statement timeout, the budget below), so a failure can't leave it behind.
        try:
            write_export_csv(filters, tmp_path, estimated_rows=row_count,
                             budget=write_budget(Config.EXPORT_SYNC_MAX_SECONDS))
        except ExportAborted as exc:
            _remove(tmp_path)
            log.warning("sync export stopped: %s", exc)
            return jsonify({"error": str(exc)}), exc.status
        except BaseException:
            _remove(tmp_path)
            raise
        filename = default_export_filename(filters)

        @after_this_request
        def cleanup_file(response):
            _remove(tmp_path)
            return response

        return send_file(tmp_path, as_attachment=True, download_name=filename, mimetype="text/csv")

    @app.route("/api/exports/jobs", methods=["POST"])
    def create_export_job():
        """Queues a background export (202 with the job id), or answers 200 with a ready job that already holds
        exactly this export. Refuses exports above EXPORT_MAX_ROWS (413), new jobs when this visitor or the whole
        server already has too many running or this visitor has started too many this hour (429), and exports the
        disk has no room for (507)."""
        try:
            filters = normalize_export_payload(_payload())
        except ValueError as exc:
            return _invalid(exc)

        ready = reusable_job(filters)
        if ready is not None:
            return jsonify({
                "job_id": ready.id,
                "status": ready.status,
                "estimated_rows": ready.estimated_rows,
                "poll_interval_seconds": Config.EXPORT_POLL_INTERVAL_SECONDS,
                "reused": True,
            }), 200

        requester_fingerprint = _request_fingerprint()
        # The per-visitor checks are cheap, so a visitor who is over a limit is refused before the row count, which
        # reads the whole range. They're made again below, under the lock, before a job is saved.
        refused = _job_limits(requester_fingerprint)
        if refused:
            db.session.rollback()
            return refused

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
        refused = _low_disk(row_count, filters)
        if refused:
            return refused

        job_id = str(uuid.uuid4())

        # Two requests at once could both pass the limits below before either job is saved; on PostgreSQL a
        # transaction lock (released at the commit or rollback) makes them take turns.
        if db.engine.dialect.name == "postgresql":
            db.session.execute(text("SELECT pg_advisory_xact_lock(hashtext('export_jobs_limits'))"))

        refused = _job_limits(requester_fingerprint)
        if refused:
            db.session.rollback()
            return refused

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
        try:
            generate_export_job.delay(job_id)
        except Exception as exc:
            # The queue (Redis) is unreachable. Left "queued", the job would count against the visitor's and the
            # global limits for an hour (QUEUED_STALE_AFTER); failed now, it frees its place at once. It isn't run
            # here instead: a large export can take minutes and hundreds of MB, too much for a web request.
            app.logger.error("export job %s not queued: %s", job_id, type(exc).__name__)
            capture_job_error(exc, source="api")
            job.status = "failed"
            job.error_message = EXPORT_QUEUE_DOWN_MESSAGE
            job.completed_at = est_now()
            db.session.commit()
            return jsonify({"error": EXPORT_QUEUE_DOWN_MESSAGE, "job_id": job_id}), 503

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

    # <uuid:...>: job ids are server-made UUIDs, so anything else (a NUL byte, say) is a 404 before the database.
    @app.route("/api/exports/jobs/<uuid:job_id>", methods=["GET"])
    def get_export_job(job_id: uuid.UUID):
        """A job's status and progress, polled by the page until it is ready, failed or expired."""
        job = db.session.get(ExportJob, str(job_id))
        if not job:
            return jsonify({"error": "Export job not found"}), 404

        # A job whose worker died (killed for memory, say) would read "running" until the hourly cleanup; settle
        # it here so the page stops waiting. The cleanup still deletes whatever it left behind.
        if settle_if_stuck(job):
            db.session.commit()

        response = job.to_dict()
        response["download_ready"] = job.status == "ready"
        return jsonify(response)

    @app.route("/api/exports/jobs/<uuid:job_id>/download", methods=["GET"])
    def download_export_artifact(job_id: uuid.UUID):
        """Sends a finished job's CSV: 409 while it isn't ready, 410 once it has expired or the file is gone."""
        job = db.session.get(ExportJob, str(job_id))
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


def _job_limits(requester_fingerprint):
    """The 429 answer (body, status, headers) when this visitor may not start a job now, else None.

    A visitor may have EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER jobs queued or running, and start
    EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER an hour. The server runs EXPORT_MAX_ACTIVE_JOBS at once in all, and a
    visitor who already has one gets another only while at least half of those places are free: otherwise a few
    visitors keeping two jobs each queued would hold every place, and everyone else would be refused."""
    live = live_jobs()
    mine = sum(1 for live_job in live if live_job.requester_fingerprint == requester_fingerprint)
    if mine >= Config.EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER:
        return (
            jsonify({"error": "You already have exports being prepared. Please wait for them to finish, then try "
                              "again."}),
            429,
            {},
        )
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    if jobs_started_since(requester_fingerprint, hour_ago) >= Config.EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER:
        return (
            jsonify({"error": "You've started a lot of exports in the last hour. Please try again later."}),
            429,
            {"Retry-After": "600"},
        )
    busy = len(live) >= Config.EXPORT_MAX_ACTIVE_JOBS
    if mine and len(live) * 2 > Config.EXPORT_MAX_ACTIVE_JOBS:
        busy = True   # a second job only while at least half the places are free
    if busy:
        return (
            jsonify({"error": "The server is busy preparing other exports. Please try again in a few minutes."}),
            429,
            {},
        )
    return None


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
