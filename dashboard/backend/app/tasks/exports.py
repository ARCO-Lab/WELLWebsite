import os
from datetime import timedelta

from celery.utils.log import get_task_logger

from api.services.exports import default_export_filename, write_export_csv
from config import Config
from db.database import db
from db.models import ExportJob
from server import create_app
from tasks.celery_app import celery_app
from utils.timezone import est_now

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
            artifact_path = os.path.join(Config.EXPORTS_DIR, artifact_name)

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
            complete_job.expires_at = est_now() + timedelta(minutes=Config.EXPORT_FILE_TTL_MINUTES)
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


@celery_app.task(name="exports.cleanup_expired_artifacts")
def cleanup_expired_artifacts():
    app = create_app()
    with app.app_context():
        now = est_now()
        expired_jobs = (
            db.session.query(ExportJob)
            .filter(ExportJob.expires_at.isnot(None), ExportJob.expires_at < now)
            .all()
        )

        for job in expired_jobs:
            if job.artifact_path and os.path.exists(job.artifact_path):
                try:
                    os.remove(job.artifact_path)
                except OSError:
                    logger.warning("Failed to remove artifact path=%s", job.artifact_path)
            job.status = "expired"
            job.artifact_path = None

        if expired_jobs:
            db.session.commit()
