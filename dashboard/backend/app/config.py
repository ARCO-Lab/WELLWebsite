# This file defines the Config class: the backend's settings, read once from the environment (and .env) at import.
# It centralizes the vendor API endpoints and credentials, the database, Borealis, exports and Celery settings.
# docs/configuration.md describes each variable.

import logging
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def parse_timeout_ms(name, value):
    """A timeout setting in milliseconds: a whole number >= 0, where 0 (or unset/empty) means no timeout.
    Anything else logs a warning and means no timeout, so a typo can't make every query fail."""
    if value is None or value.strip() == "":
        return 0
    try:
        ms = int(value)
    except ValueError:
        ms = -1
    if ms < 0:
        logging.getLogger(__name__).warning("%s=%r is not a whole number of milliseconds; no timeout", name, value)
        return 0
    return ms


@dataclass(frozen=True)
class Config:
    # LI-COR Cloud (formerly HOBOlink): the weather station and water-level loggers.
    HOBO_API_URL = os.getenv("HOBOLINK_API_URL")
    HOBO_API_TOKEN = os.getenv("HOBOLINK_API_TOKEN")
    HOBO_LOGGERS = os.getenv("HOBOLINK_LOGGERS")

    # WQData: the water quality sonde.
    WQ_API_URL = os.getenv("WQ_API_URL")
    WQ_API_KEY = os.getenv("WQ_API_KEY")
    WQ_DEVICE_ID = os.getenv("WQ_DEVICE_ID")
    
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # The largest request body Flask reads (bytes); a bigger one is refused with a 413. The only bodies are export
    # requests, a few hundred bytes of JSON.
    MAX_CONTENT_LENGTH = 64 * 1024
    # Longest a single SQL statement may run before PostgreSQL cancels it; 0 = no limit. docker-compose.yml sets
    # it for the backend (API) container only, so a query nobody is waiting for any more can't keep running long
    # after the request has failed. The worker and export worker leave it unset: ingestion, backfills and big
    # exports may legitimately run for minutes. scripts/migrate.py makes its own connection and never uses it.
    DB_STATEMENT_TIMEOUT_MS = parse_timeout_ms("DB_STATEMENT_TIMEOUT_MS", os.getenv("DB_STATEMENT_TIMEOUT_MS"))
    # The name this process gives its PostgreSQL connections (application_name, shown in pg_stat_activity), so
    # each container's connections can be told apart: well-backend, well-worker or well-export_worker, from the
    # SENTRY_COMPONENT docker-compose.yml sets for the worker and export worker. DB_APPLICATION_NAME overrides it.
    DB_APPLICATION_NAME = (os.getenv("DB_APPLICATION_NAME", "").strip()
                           or "well-" + (os.getenv("SENTRY_COMPONENT", "").strip() or "backend"))
    # Redis database for the short-lived /api/series response cache (utils/response_cache.py); empty = no cache.
    API_CACHE_REDIS_URL = os.getenv("API_CACHE_REDIS_URL", "").strip()

    # Borealis (utils/borealis.py explains each). The DEMO_* names, which pointed at the demo server, are still
    # read when the new names are unset.
    BOREALIS_URL = os.getenv("BOREALIS_URL") or os.getenv("DEMO_BOREALIS_URL")
    BOREALIS_API_TOKEN = os.getenv("BOREALIS_API_TOKEN")
    BOREALIS_UPLOAD_PERSISTENT_ID = (os.getenv("BOREALIS_UPLOAD_PERSISTENT_ID")
                                     or os.getenv("DEMO_BOREALIS_WC_PERSISTENT_ID"))
    BOREALIS_SAMPLING_PERSISTENT_ID = (os.getenv("BOREALIS_SAMPLING_PERSISTENT_ID")
                                       or os.getenv("DEMO_BOREALIS_AW_PERSISTENT_ID"))
    BOREALIS_UPLOAD_DATAVERSE = os.getenv("BOREALIS_UPLOAD_DATAVERSE")
    BOREALIS_SAMPLING_DATAVERSE = os.getenv("BOREALIS_SAMPLING_DATAVERSE")
    # Publish each monthly upload (default). Off ("0"): the upload stays a draft for a curator to publish.
    BOREALIS_PUBLISH = os.getenv("BOREALIS_PUBLISH", "1").strip().lower() not in ("0", "false", "no", "off")

    # CSV exports: where files are written, how long a finished job's file is kept, the largest export sent
    # directly rather than as a background job (readings), and how often the page polls a job.
    EXPORTS_DIR = os.getenv("EXPORTS_DIR", "/app/app/exports")
    EXPORT_FILE_TTL_MINUTES = int(os.getenv("EXPORT_FILE_TTL_MINUTES", "60"))
    EXPORT_SYNC_ROW_THRESHOLD = int(os.getenv("EXPORT_SYNC_ROW_THRESHOLD", "100000"))
    EXPORT_POLL_INTERVAL_SECONDS = int(os.getenv("EXPORT_POLL_INTERVAL_SECONDS", "3"))
    # Limits on queued (async) exports, so one visitor, or many at once, can't tie up the export worker:
    # the largest export (in readings, as /api/exports/estimate counts them), and how many jobs may be queued or
    # running at once, in total and per visitor (by IP address).
    EXPORT_MAX_ROWS = int(os.getenv("EXPORT_MAX_ROWS", "5000000"))
    EXPORT_MAX_ACTIVE_JOBS = int(os.getenv("EXPORT_MAX_ACTIVE_JOBS", "6"))
    EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER = int(os.getenv("EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER", "2"))
    # How many jobs one visitor may start in an hour, finished ones included, so a loop that queues a new export as
    # soon as the last one finishes can't keep filling the disk. An identical export that is still ready is reused
    # and doesn't count.
    EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER = int(os.getenv("EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER", "6"))
    # Free space (MB) to leave on the exports disk after an export's estimated size; exports that would go below it
    # are refused (507). The database shares this disk on the VM.
    EXPORT_MIN_FREE_MB = int(os.getenv("EXPORT_MIN_FREE_MB", "2048"))
    # The largest file one export may write (MB; 0 = no limit besides the free space above), and how long a direct
    # (sync) download may take to build (seconds; under gunicorn's 60 s timeout). An export that passes either is
    # stopped part way and its file deleted, so a request the row estimate got wrong can't fill the disk or hold a
    # web thread for minutes. The largest export the dashboard allows (EXPORT_MAX_ROWS) is far smaller.
    EXPORT_MAX_FILE_MB = int(os.getenv("EXPORT_MAX_FILE_MB", "1024"))
    EXPORT_SYNC_MAX_SECONDS = int(os.getenv("EXPORT_SYNC_MAX_SECONDS", "45"))
    # How long one export may run, in seconds: past the soft limit it is stopped and marked failed; the hard
    # limit kills its worker process if it didn't stop.
    EXPORT_SOFT_TIME_LIMIT_SECONDS = int(os.getenv("EXPORT_SOFT_TIME_LIMIT_SECONDS", str(15 * 60)))
    EXPORT_HARD_TIME_LIMIT_SECONDS = int(os.getenv("EXPORT_HARD_TIME_LIMIT_SECONDS", str(20 * 60)))
    # A worker process is replaced after a task leaves it using more than this much memory (KiB).
    EXPORT_WORKER_MAX_MEMORY_KB = int(os.getenv("EXPORT_WORKER_MAX_MEMORY_KB", "512000"))

    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

