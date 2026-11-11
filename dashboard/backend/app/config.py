# This file defines the Config dataclass for loading environment variables and application settings.
# It centralizes configuration for API endpoints, tokens, device IDs, and database URI.

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
    HOBO_API_URL = os.getenv("HOBOLINK_API_URL")
    HOBO_API_TOKEN = os.getenv("HOBOLINK_API_TOKEN")
    HOBO_LOGGERS = os.getenv("HOBOLINK_LOGGERS")

    WQ_API_URL = os.getenv("WQ_API_URL")
    WQ_API_KEY = os.getenv("WQ_API_KEY")
    WQ_DEVICE_ID = os.getenv("WQ_DEVICE_ID")
    
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Longest a single SQL statement may run before PostgreSQL cancels it; 0 = no limit. docker-compose.yml sets
    # it for the backend (API) container only, so a query nobody is waiting for any more can't keep running long
    # after the request has failed. The worker and export worker leave it unset: ingestion, backfills and big
    # exports may legitimately run for minutes. scripts/migrate.py makes its own connection and never uses it.
    DB_STATEMENT_TIMEOUT_MS = parse_timeout_ms("DB_STATEMENT_TIMEOUT_MS", os.getenv("DB_STATEMENT_TIMEOUT_MS"))
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

    EXPORTS_DIR = os.getenv("EXPORTS_DIR", "/app/app/exports")
    EXPORT_FILE_TTL_MINUTES = int(os.getenv("EXPORT_FILE_TTL_MINUTES", "60"))
    EXPORT_SYNC_ROW_THRESHOLD = int(os.getenv("EXPORT_SYNC_ROW_THRESHOLD", "100000"))
    EXPORT_POLL_INTERVAL_SECONDS = int(os.getenv("EXPORT_POLL_INTERVAL_SECONDS", "3"))

    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

