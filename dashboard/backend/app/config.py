# This file defines the Config dataclass for loading environment variables and application settings.
# It centralizes configuration for API endpoints, tokens, device IDs, and database URI.

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
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

