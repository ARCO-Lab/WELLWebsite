"""Heartbeat pings to Healthchecks.io (or any service with the same URL scheme), so a job that stops running or
keeps failing is reported by email from there, without SMTP of our own.

Each job has its own check, whose ping URL is in HEALTHCHECK_URL_<NAME> (e.g. HEALTHCHECK_URL_INGESTION).
Unset means no ping, so a job, or the whole worker, could stop with nobody told: the worker names every unset
one in a warning when it starts, and the daily digest lists them (unset_heartbeats). A ping never raises and gives
up after a few seconds: monitoring must not break, or hold up, the job it watches. The URL holds the check's
secret id, so it is never logged.
"""
import os

import requests

HEARTBEAT_TIMEOUT_S = 5
# Healthchecks.io: the bare URL reports success; /fail and /start are the other signals, and /log records a
# message in the check's event log without changing its state.
SUFFIXES = {"success": "", "fail": "/fail", "start": "/start", "log": "/log"}
# Healthchecks.io keeps the first 100 kB of a ping's body; a message here is far shorter, this only bounds it.
MESSAGE_LIMIT = 10_000

# The checks the worker pings (scripts/scheduler_temp.py). "sharepoint" only counts while the SharePoint copy is
# configured: with it off there is nothing to watch.
WORKER_HEARTBEATS = ("ingestion", "alerts", "download", "upload", "digest", "backup", "restore")


def heartbeat_setting(name):
    """The environment variable that holds job `name`'s ping URL."""
    return f"HEALTHCHECK_URL_{name.upper()}"


def heartbeat_url(name, env=None):
    # The ping URL for job `name` from HEALTHCHECK_URL_<NAME>, or "" when unset.
    env = os.environ if env is None else env
    return (env.get(heartbeat_setting(name)) or "").strip()


def unset_heartbeats(env=None, sharepoint_on=False):
    """The HEALTHCHECK_URL_* settings of the worker's jobs that aren't set, in WORKER_HEARTBEATS order (then
    HEALTHCHECK_URL_SHAREPOINT when `sharepoint_on`). [] when every job is watched."""
    names = list(WORKER_HEARTBEATS) + (["sharepoint"] if sharepoint_on else [])
    return [heartbeat_setting(name) for name in names if not heartbeat_url(name, env)]


def ping_heartbeat(name, status="success", timeout=HEARTBEAT_TIMEOUT_S, env=None, get=None, message=None,
                   post=None):
    """Ping the check for job `name` ("ingestion", "upload", "backup", "digest", ...) with `status`
    ("success", "fail", "start" or "log"). With `message`, it is sent as the ping's body (POST), which the check
    shows in its event log. True if the ping was accepted; False if it is unset, failed or timed out."""
    try:
        url = heartbeat_url(name, env)
        if not url:
            return False
        suffix = SUFFIXES.get(status, "/fail")   # an unknown status is a bug in the caller; don't report success
        target = url.rstrip("/") + suffix
        if message is None:
            response = (get or requests.get)(target, timeout=timeout)
        else:
            response = (post or requests.post)(target, data=str(message)[:MESSAGE_LIMIT].encode("utf-8"),
                                               timeout=timeout)
        return 200 <= response.status_code < 300
    except Exception:
        return False
