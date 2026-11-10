import os
from datetime import timedelta

from celery.utils.log import get_task_logger
from sqlalchemy import or_

from api.services.exports import default_export_filename, write_export_csv
from config import Config
from db.database import db
from db.models import ExportJob
from server import create_app
from tasks.celery_app import celery_app
from utils.timezone import est_after, est_now

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="exports.generate_export_job")
def generate_export_job(self, job_id: str):
    app = create_app()
    with app.app_context():
        job = db.session.get(ExportJob, job_id)
        if not job:
            logger.error("Export job not found: %s", job_id)
            return

        try:
            job.status = "running"
            job.started_at = est_now()
            job.progress_pct = 0.0
            db.session.commit()

            artifact_name = default_export_filename(job.payload)
            # One folder per job: identical exports share a friendly file name, but must not share a file
            # (cleaning up one job would delete the other's download).
            artifact_path = os.path.join(Config.EXPORTS_DIR, job_id, artifact_name)

            def on_progress(produced_rows: int, total_rows: int):
                progress = 100.0 if total_rows <= 0 else min(100.0, (produced_rows / total_rows) * 100.0)
                progress_job = db.session.get(ExportJob, job_id)
                if not progress_job:
                    return
                progress_job.produced_rows = produced_rows
                progress_job.progress_pct = progress
                db.session.commit()

            rows_written = write_export_csv(
                payload=job.payload,
                output_path=artifact_path,
                progress_callback=on_progress,
                estimated_rows=job.estimated_rows,
            )

            complete_job = db.session.get(ExportJob, job_id)
            if not complete_job:
                return

            complete_job.status = "ready"
            complete_job.produced_rows = rows_written
            complete_job.progress_pct = 100.0
            complete_job.artifact_name = artifact_name
            complete_job.artifact_path = artifact_path
            complete_job.completed_at = est_now()
            complete_job.expires_at = est_after(Config.EXPORT_FILE_TTL_MINUTES)
            db.session.commit()

        except Exception as exc:
            logger.exception("Export job failed: %s", job_id)
            failed_job = db.session.get(ExportJob, job_id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)
                failed_job.completed_at = est_now()
                db.session.commit()
            raise


# Expiry times are naive local wall-clock times, compared here in SQL, and a wall time is never more than an hour
# off real time at a DST change. Only delete a file once its expiry is more than this far in the past, so a
# download window is never cut short, even one the download route reads as the later of a repeated fall-back hour.
DELETE_GRACE = timedelta(hours=1)


@celery_app.task(name="exports.cleanup_expired_artifacts")
def cleanup_expired_artifacts():
    """Delete export files whose download window has passed, and mark their jobs expired.

    - A file is kept while another job that hasn't expired still points at it (exports made before
      per-job folders could share one path).
    - A job keeps its path until its file is really gone, so a failed delete is retried next run.
    """
    app = create_app()
    with app.app_context():
        cutoff = est_now() - DELETE_GRACE
        candidates = (
            db.session.query(ExportJob)
            .filter(
                ExportJob.artifact_path.isnot(None),
                ExportJob.expires_at.isnot(None),
                ExportJob.expires_at < cutoff,
            )
            .all()
        )
        for job in candidates:
            path = job.artifact_path
            still_used = (
                db.session.query(ExportJob.id)
                .filter(
                    ExportJob.id != job.id,
                    ExportJob.artifact_path == path,
                    or_(ExportJob.expires_at.is_(None), ExportJob.expires_at >= cutoff),
                )
                .first()
            )
            if still_used is None and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    logger.warning("Failed to remove artifact path=%s; will retry on the next run", path)
                    continue
                _remove_empty_job_folder(path)
            job.status = "expired"
            job.artifact_path = None

        if candidates:
            db.session.commit()


def _remove_empty_job_folder(path):
    folder = os.path.dirname(path)
    if os.path.abspath(folder) == os.path.abspath(Config.EXPORTS_DIR):
        return  # an older export stored directly in EXPORTS_DIR
    try:
        os.rmdir(folder)
    except OSError:
        pass  # not empty, or already gone
