"""Heartbeat pings to Healthchecks.io (or any service with the same URL scheme), so a job that stops running or
keeps failing is reported by email from there, without SMTP of our own.

Each job has its own check, whose ping URL is in HEALTHCHECK_URL_<NAME> (e.g. HEALTHCHECK_URL_INGESTION).
Unset means no ping. A ping never raises and gives up after a few seconds: monitoring must not break, or hold
up, the job it watches. The URL holds the check's secret id, so it is never logged.
"""
import os

import requests

HEARTBEAT_TIMEOUT_S = 5
# Healthchecks.io: the bare URL reports success; /fail and /start are the other signals.
SUFFIXES = {"success": "", "fail": "/fail", "start": "/start"}


def heartbeat_url(name, env=None):
    env = os.environ if env is None else env
    return (env.get(f"HEALTHCHECK_URL_{name.upper()}") or "").strip()


def ping_heartbeat(name, status="success", timeout=HEARTBEAT_TIMEOUT_S, env=None, get=None):
    """Ping the check for job `name` ("ingestion", "upload", "backup", "digest", ...) with `status`
    ("success", "fail" or "start"). True if the ping was accepted; False if it is unset, failed or timed out."""
    try:
        url = heartbeat_url(name, env)
        if not url:
            return False
        suffix = SUFFIXES.get(status, "/fail")   # an unknown status is a bug in the caller; don't report success
        response = (get or requests.get)(url.rstrip("/") + suffix, timeout=timeout)
        return 200 <= response.status_code < 300
    except Exception:
        return False
