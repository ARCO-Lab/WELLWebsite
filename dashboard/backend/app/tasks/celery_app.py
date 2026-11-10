from celery import Celery
from config import Config


def create_celery_app() -> Celery:
    celery = Celery(
        "well_exports",
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND,
    )
    celery.conf.update(
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        timezone="UTC",
        enable_utc=True,
        imports=("tasks.exports",),
        # Run by the beat scheduler embedded in export_worker (`celery ... worker -B` in docker-compose.yml):
        # delete export files whose download window (EXPORT_FILE_TTL_MINUTES) has passed.
        beat_schedule={
            "cleanup-expired-exports": {"task": "exports.cleanup_expired_artifacts", "schedule": 60 * 60},
        },
    )
    return celery


celery_app = create_celery_app()
