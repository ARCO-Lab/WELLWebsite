"""Heartbeat pings to Healthchecks.io (or any service with the same URL scheme), so a job that stops running or
keeps failing is reported by email from there, without SMTP of our own.

Each job has its own check, whose ping URL is in HEALTHCHECK_URL_<NAME> (e.g. HEALTHCHECK_URL_INGESTION).
Unset means no ping, so a job, or the whole worker, could stop with nobody told: the worker names every unset
one in a warning when it starts (to Sentry at most once a day, first_report_today), and the daily digest lists
them (unset_heartbeats). A ping never raises and gives up after a few seconds: monitoring must not break, or hold
up, the job it watches. The URL holds the check's secret id, so it is never logged.
"""
import json
import os
import time

import requests

HEARTBEAT_TIMEOUT_S = 5
# Healthchecks.io: the bare URL reports success; /fail and /start are the other signals, and /log records a
# message in the check's event log without changing its state.
SUFFIXES = {"success": "", "fail": "/fail", "start": "/start", "log": "/log"}
# Healthchecks.io keeps the first 100 kB of a ping's body; a message here is far shorter, this only bounds it.
MESSAGE_LIMIT = 10_000

# The checks the worker pings (scripts/scheduler_temp.py). "restore" only counts while the restore drill is on
# (RESTORE_CHECK_DAY isn't "off"), and "sharepoint" while the SharePoint copy is configured: with them off there is
# nothing to watch.
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
    HEALTHCHECK_URL_SHAREPOINT when `sharepoint_on`), leaving out the restore drill's while RESTORE_CHECK_DAY is
    "off". [] when every job is watched."""
    env = os.environ if env is None else env
    restore_on = (env.get("RESTORE_CHECK_DAY") or "").strip().lower() != "off"
    names = [name for name in WORKER_HEARTBEATS if restore_on or name != "restore"]
    names += ["sharepoint"] if sharepoint_on else []
    return [heartbeat_setting(name) for name in names if not heartbeat_url(name, env)]


# When the warning about unset heartbeats last went to Sentry, and for which settings (first_report_today); with the
# logs, so it survives the worker's restarts.
UNSET_REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs",
                                 "unset_heartbeats_reported.json")
UNSET_REPORT_EVERY_S = 24 * 60 * 60


def first_report_today(missing, path=None, now=None):
    """Whether the warning naming the unset settings `missing` should go to Sentry now: not if the same settings were
    reported in the last UNSET_REPORT_EVERY_S. A deploy restarts the worker several times, and each start used to send
    it again. If so, the time and the names are written to `path` (default UNSET_REPORT_PATH). A file that can't be
    read or written counts as no report yet: a repeated warning is better than none."""
    path = path or UNSET_REPORT_PATH
    now = time.time() if now is None else now
    names = sorted(missing)
    try:
        with open(path) as f:
            last = json.load(f)
        reported = last.get("missing") == names and 0 <= now - float(last.get("reported_at")) < UNSET_REPORT_EVERY_S
    except (OSError, ValueError, TypeError, AttributeError):
        reported = False   # no record yet, or a damaged one
    if reported:
        return False
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump({"missing": names, "reported_at": now}, f)
        os.replace(tmp, path)
    except OSError:
        return True   # logs/ isn't writable: report now, and again at the next start
    return True


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
