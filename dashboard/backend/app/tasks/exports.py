import os
import shutil
import time
from datetime import timedelta

from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from sqlalchemy import or_

from api.services.exports import (
    EXPORT_FAILED_MESSAGE,
    EXPORT_TOO_SLOW_MESSAGE,
    default_export_filename,
    live_job_condition,
    settle_if_stuck,
    write_export_csv,
)
from config import Config
from db.database import db
from db.models import ExportJob
from server import create_app
from tasks.celery_app import celery_app
from utils.timezone import est_after, est_now

logger = get_task_logger(__name__)

# EXPORT_FAILED_MESSAGE and EXPORT_TOO_SLOW_MESSAGE (api/services/exports.py) are the other failure messages.
# For a job whose task was started before and didn't finish (its worker process died, most likely of running out
# of memory). It isn't run again, since it would likely die the same way.
EXPORT_INTERRUPTED_MESSAGE = "This export was interrupted. Try a shorter date range."


def user_facing_error(exc: Exception) -> str:
    """The error_message to store for a failed job. The job status API returns it to the browser, so only a plain
    ValueError (the payload validation messages, written for the user) is kept. Anything else, a database error
    for one, can hold SQL, parameters or server paths: it gets a generic message and is logged in full instead.
    Subclasses such as JSONDecodeError are not validation messages and get the generic one too."""
    if isinstance(exc, SoftTimeLimitExceeded):
        return EXPORT_TOO_SLOW_MESSAGE
    if type(exc) is ValueError and str(exc):
        return str(exc)
    return EXPORT_FAILED_MESSAGE


@celery_app.task(bind=True, name="exports.generate_export_job")
def generate_export_job(self, job_id: str):
    app = create_app()
    with app.app_context():
        job = db.session.get(ExportJob, job_id)
        if not job:
            logger.error("Export job not found: %s", job_id)
            return

        # Only a queued job is run. "running" means this task was delivered before and that attempt never
        # finished (Redis hands an unacknowledged task out again once its worker is gone), so fail it instead of
        # trying again. Anything else was already settled, by the cleanup for one.
        if job.status != "queued":
            if job.status == "running":
                logger.warning("Export job %s was interrupted on an earlier attempt; marking it failed", job_id)
                job.status = "failed"
                job.error_message = EXPORT_INTERRUPTED_MESSAGE
                job.completed_at = est_now()
                db.session.commit()
                _remove_job_folder(job_id)
            else:
                logger.info("Export job %s is already %s; not running it", job_id, job.status)
            return

        artifact_path = None  # set once known, so a failed export can delete what it wrote
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
            # The failure may have left the session's transaction broken (a database error, or the time limit
            # landing mid-commit); start a fresh one so the job can still be marked failed.
            db.session.rollback()
            # No row points at a failed export's file (the path is saved only on success), so the hourly cleanup
            # would never find it: delete it now.
            if artifact_path:
                try:
                    if os.path.exists(artifact_path):
                        os.remove(artifact_path)
                except OSError:
                    logger.warning("Failed to remove the file of a failed export path=%s", artifact_path)
                _remove_empty_job_folder(artifact_path)
            failed_job = db.session.get(ExportJob, job_id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.error_message = user_facing_error(exc)
                failed_job.completed_at = est_now()
                db.session.commit()
            raise


# Expiry times are naive local wall-clock times, compared here in SQL, and a wall time is never more than an hour
# off real time at a DST change. Only delete a file once its expiry is more than this far in the past, so a
# download window is never cut short, even one the download route reads as the later of a repeated fall-back hour.
DELETE_GRACE = timedelta(hours=1)


# Export job rows are kept this long (for a look back at what was exported), then deleted.
JOB_ROW_RETENTION = timedelta(days=30)


def orphan_file_age() -> timedelta:
    """A file in EXPORTS_DIR no job points at is deleted once it is this old: well past any download window
    (EXPORT_FILE_TTL_MINUTES, plus DELETE_GRACE), so it can't be one still being written or downloaded."""
    return timedelta(minutes=Config.EXPORT_FILE_TTL_MINUTES) + timedelta(hours=2)


@celery_app.task(name="exports.cleanup_expired_artifacts")
def cleanup_expired_artifacts():
    """The hourly export housekeeping:

    1. Mark failed the jobs that will never finish (queued past QUEUED_STALE_AFTER, or running past the hard time
       limit), and delete what they wrote.
    2. Delete export files whose download window has passed, and mark their jobs expired.
       - A file is kept while another job that hasn't expired still points at it (exports made before
         per-job folders could share one path).
       - A job keeps its path until its file is really gone, so a failed delete is retried next run.
    3. Delete job rows older than JOB_ROW_RETENTION.
    4. Delete files in EXPORTS_DIR that no job points at once they are older than orphan_file_age(): sync
       exports a crashed request didn't remove, and files of jobs that died mid-export.
    """
    app = create_app()
    with app.app_context():
        _fail_stuck_jobs()
        _expire_artifacts()
        _prune_old_jobs()
        _remove_orphaned_files()


def _fail_stuck_jobs():
    now = est_now()
    candidates = (
        db.session.query(ExportJob)
        .filter(ExportJob.status.in_(("queued", "running")), ~live_job_condition(now))
        .all()
    )
    stuck = [job for job in candidates if settle_if_stuck(job, now)]
    for job in stuck:
        logger.warning("Export job %s will never finish; marked it failed", job.id)
    if stuck:
        db.session.commit()
    for job in stuck:
        _remove_job_folder(job.id)


def _expire_artifacts():
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


def _prune_old_jobs():
    """Delete settled job rows older than JOB_ROW_RETENTION. A row that still points at a file is kept, so a file
    whose delete keeps failing isn't forgotten. A failure here (the database user lacking DELETE on export_jobs,
    say) is logged and doesn't stop the rest of the cleanup."""
    try:
        deleted = (
            db.session.query(ExportJob)
            .filter(
                ExportJob.created_at < est_now() - JOB_ROW_RETENTION,
                ExportJob.status.notin_(("queued", "running")),
                ExportJob.artifact_path.is_(None),
            )
            .delete(synchronize_session=False)
        )
        db.session.commit()
        if deleted:
            logger.info("Deleted %d export job rows older than %s", deleted, JOB_ROW_RETENTION)
    except Exception:
        db.session.rollback()
        logger.exception("Could not delete old export job rows; will retry on the next run")


def _remove_orphaned_files():
    """Delete old files in EXPORTS_DIR that no job points at (step 4 of the cleanup), then empty job folders."""
    root = os.path.abspath(Config.EXPORTS_DIR)
    if not os.path.isdir(root):
        return
    referenced = {
        os.path.abspath(path)
        for (path,) in db.session.query(ExportJob.artifact_path).filter(ExportJob.artifact_path.isnot(None))
    }
    # The folders of jobs still being prepared, which may not have pointed at their file yet.
    live_folders = {
        os.path.join(root, job_id)
        for (job_id,) in db.session.query(ExportJob.id).filter(ExportJob.status.in_(("queued", "running")))
    }
    cutoff = time.time() - orphan_file_age().total_seconds()

    for folder, subfolders, files in os.walk(root, topdown=False):
        folder = os.path.abspath(folder)
        if folder in live_folders:
            continue
        removed_any = False
        for name in files:
            path = os.path.join(folder, name)
            try:
                if os.path.islink(path) or path in referenced or os.path.getmtime(path) >= cutoff:
                    continue
                os.remove(path)
                removed_any = True
                logger.info("Removed orphaned export file path=%s", path)
            except OSError:
                logger.warning("Failed to remove orphaned export file path=%s; will retry on the next run", path)
        if folder != root:
            try:
                # Only a folder that held old files or is old itself, so a new job's folder isn't removed between
                # being made and written to. rmdir only succeeds once the folder is empty.
                if removed_any or os.path.getmtime(folder) < cutoff:
                    os.rmdir(folder)
            except OSError:
                pass  # not empty yet (a file it holds is kept), or already gone


def _remove_job_folder(job_id):
    """Delete the folder a job wrote its export to (EXPORTS_DIR/<job id>), if there is one."""
    if not job_id or os.path.basename(job_id) != job_id or job_id in (".", ".."):
        return  # never a path outside EXPORTS_DIR
    folder = os.path.join(Config.EXPORTS_DIR, job_id)
    if os.path.isdir(folder) and not os.path.islink(folder):
        shutil.rmtree(folder, ignore_errors=True)


def _remove_empty_job_folder(path):
    folder = os.path.dirname(path)
    if os.path.abspath(folder) == os.path.abspath(Config.EXPORTS_DIR):
        return  # an older export stored directly in EXPORTS_DIR
    try:
        os.rmdir(folder)
    except OSError:
        pass  # not empty, or already gone
