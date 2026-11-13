# This script runs the worker's scheduled jobs: vendor API ingestion every 10 minutes, the weekly
# Borealis sampling download (Sundays 00:00) and the monthly Borealis upload (02:00 Toronto time: each
# month that has ended and isn't uploaded yet, so last month goes up on the 1st and a failed one is retried daily),
# followed by the same month's upload to SharePoint when SHAREPOINT_* is set (scripts/sharepoint_upload.py), with
# its own record of months, so either copy can fail and be retried without the other.
# It also builds the daily digest (scripts/daily_digest.py) at DIGEST_HOUR (default 07:00 Toronto time), and
# pings a Healthchecks.io check after each ingestion run, sampling download, monthly upload (Borealis and
# SharePoint each have their own) and digest (utils/heartbeat.py). Every night at 03:15 Toronto time it backs up
# the database with pg_dump (scripts/backup_db.py) and pings the backup check, and once a month (RESTORE_CHECK_DAY,
# default the 2nd, 05:30) it runs the restore drill (scripts/restore_check.py) and pings the restore check. After every
# ingestion run it checks for sensor and vendor problems and emails new ones (scripts/check_alerts.py).
# One scheduler loop starts each job in its own thread, and a job that is still running is never
# started again, so every job runs once per slot; each skipped run is logged in the job's heartbeat check, and
# SKIPS_BEFORE_FAIL in a row fail it. At start-up it names every heartbeat URL that isn't set. It logs to files
# under logs/.
# When SENTRY_DSN is set, every failure it logs is also reported to Sentry, tagged with the job (utils/sentry.py).
# On SIGTERM (docker compose stop, or a deploy recreating the worker) it starts nothing new, gives running jobs
# STOP_WAIT_S to finish, then stops their subprocesses and exits (shut_down).

import schedule
import time
import sys
import builtins
import signal
import subprocess
import math
import os
import pathlib
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from utils.sentry import init_sentry, capture_job_error, capture_job_warning  # noqa: E402

# Report errors to Sentry when SENTRY_DSN is set (utils/sentry.py). First, so they are tagged worker:
# inject_from_api imports server.py, which would otherwise start reporting as the API.
if __name__ == "__main__":
    init_sentry("worker")

from inject_from_api import inject_all_new_data  # noqa: E402
from utils.jobs import (  # noqa: E402
    run_in_background, run_bounded, download_status, stop_subprocesses,
    load_uploaded_months, record_uploaded_month, months_due_for_upload, month_key, parse_month_key, UPLOAD_HOUR,
    record_attention,
)
from utils.heartbeat import ping_heartbeat, unset_heartbeats  # noqa: E402
from utils.worklog import file_logger  # noqa: E402
from utils import sharepoint  # noqa: E402
import check_alerts  # noqa: E402

log_file_path = "logs/db_injections.log"
download_log_file_path = "logs/download_injections.log"
upload_log_file_path = "logs/db_uploads.log"
digest_log_file_path = "logs/daily_digest.log"
alerts_log_file_path = "logs/alerts.log"
backup_log_file_path = "logs/backup.log"
# Months already uploaded to Borealis, e.g. {"uploaded_months": ["2026-10"]}. It sits with the logs (a volume
# on the host), so it survives restarts and rebuilds.
uploaded_months_path = "logs/uploaded_months.json"
# The first month the scheduler uploads; earlier months are never sent (they went up, or didn't, before
# uploads were recorded). Override with BOREALIS_UPLOAD_FIRST_MONTH=YYYY-MM.
UPLOAD_FIRST_MONTH = os.getenv("BOREALIS_UPLOAD_FIRST_MONTH", "2026-10")
# The same for the SharePoint copy, which has its own record. Override with SHAREPOINT_UPLOAD_FIRST_MONTH=YYYY-MM.
sharepoint_uploaded_months_path = "logs/sharepoint_uploaded_months.json"
SHAREPOINT_FIRST_MONTH = os.getenv("SHAREPOINT_UPLOAD_FIRST_MONTH", UPLOAD_FIRST_MONTH)

# Site time. recorded_at is stored as Toronto wall-clock time, so months start and end there, not in UTC
# (the container's clock).
SITE_TZ = ZoneInfo("America/Toronto")

# Hard limits for the Borealis subprocesses. A run that hangs is stopped, so it can't hold its
# job's lock (see utils.jobs.run_in_background) and block every later run.
DOWNLOAD_TIMEOUT_S = 2 * 60 * 60
UPLOAD_TIMEOUT_S = 2 * 60 * 60
LIST_FILES_TIMEOUT_S = 5 * 60
DIGEST_TIMEOUT_S = 10 * 60
BACKUP_TIMEOUT_S = 2 * 60 * 60   # backup_db.py bounds its own steps to 80 + 10 + 15 min (DUMP_TIMEOUT_S etc.)
RESTORE_TIMEOUT_S = 4 * 60 * 60  # restore_check.py stops pg_restore after 3 h; counting both databases is the rest
LEFTOVERS_TIMEOUT_S = 5 * 60     # restore_check.py --drop-leftovers: a few DROP DATABASE statements

# The nightly backup runs at BACKUP_HOUR:15 Toronto time: after the 02:00 uploads, before the working day, and an
# hour that happens exactly once on DST change days (02:00 is skipped or repeated, 03:00 never is).
BACKUP_HOUR = 3

# The monthly restore drill (scripts/restore_check.py) runs at RESTORE_HOUR:30 Toronto time on RESTORE_CHECK_DAY
# (1-28, default the 2nd; "off" turns it off): after that night's backup has finished (it is stopped after 2 h, so
# by 05:15), and away from the 1st, when the monthly uploads run.
RESTORE_HOUR = 5
RESTORE_CHECK_DAY = os.getenv("RESTORE_CHECK_DAY", "2").strip()

# A job whose runs are skipped this many times in a row (the previous run is still going) pings its heartbeat with
# /fail and is reported to Sentry: it is stuck, not just slow (skip_reporter). Fewer skips are only logged there.
# For ingestion (every 10 minutes, its requests bounded on their own) 3 skips is half an hour, its check's grace. The
# jobs run under a time limit get one more skip than a run can last (skips_before_fail), so a slow run that is still
# within its limit is never reported as stuck.
SKIPS_BEFORE_FAIL = 3


def skips_before_fail(timeout_s, interval_s):
    """How many skipped runs in a row mean a job is stuck: one more than a run within `timeout_s` can cover when the
    job is started every `interval_s`."""
    return math.ceil(timeout_s / interval_s) + 1

# The hour (site time, 0-23) the daily digest is built and sent; checked when it is due, so a bad value is
# logged there instead of stopping the scheduler. Not 1 or 2: clocks change at 02:00, so on those days 01:00
# happens twice (two digests) or 02:00 not at all (none).
DIGEST_HOUR = os.getenv("DIGEST_HOUR", "7").strip()

# Control whether to also mirror file logs to stdout (Docker logs)
# Set WORKER_LOG_TO_STDOUT=1|true to enable
LOG_TO_STDOUT = os.getenv("WORKER_LOG_TO_STDOUT", "").lower() in ("1", "true", "yes", "on")

# One print-like function per log file: a timestamp on each line, rotation by size (5 MB, 3 older copies kept), and
# a line that can't be written is dropped rather than stopping the job (utils/worklog.py).
timestamped_print = file_logger(log_file_path, LOG_TO_STDOUT)                    # API ingestion (and plain print)
timestamped_print_download = file_logger(download_log_file_path, LOG_TO_STDOUT)  # weekly Borealis download
timestamped_print_upload = file_logger(upload_log_file_path, LOG_TO_STDOUT)      # monthly Borealis/SharePoint upload
timestamped_print_digest = file_logger(digest_log_file_path, LOG_TO_STDOUT)      # daily digest
timestamped_print_alerts = file_logger(alerts_log_file_path, LOG_TO_STDOUT)      # alert check
timestamped_print_backup = file_logger(backup_log_file_path, LOG_TO_STDOUT)      # nightly backup

# Touched by the scheduler loop every ALIVE_EVERY_S; docker-compose.yml's healthcheck reports the worker unhealthy
# when it is older than a few minutes (the loop has stopped or hangs). Outside logs/, so nothing on the host sees it.
ALIVE_PATH = os.getenv("WORKER_ALIVE_PATH", "/tmp/well-scheduler.alive")
ALIVE_EVERY_S = 30

# On SIGTERM, how long running jobs get to finish before their subprocesses are stopped, and how long those get to
# exit after SIGTERM. Together with a few seconds for the jobs to log it, under docker-compose.yml's
# stop_grace_period for the worker (60 s), after which Docker kills everything.
STOP_WAIT_S = 40
STOP_SUBPROCESS_GRACE_S = 10
STOP_FINAL_WAIT_S = 5

stopping = threading.Event()   # set by the SIGTERM handler; the loop then starts nothing new


def request_stop(signum, frame):
    """SIGTERM/SIGINT handler: only sets `stopping`, so the loop ends after its current one-second sleep."""
    stopping.set()


def touch_alive(path=None):
    """Update the alive file's time (creating it if needed). Never raises: the healthcheck reports a failure."""
    try:
        with open(path or ALIVE_PATH, "a"):
            pass
        os.utime(path or ALIVE_PATH)
    except OSError:
        # the file then goes stale and the healthcheck reports the worker unhealthy, as it should
        pass


def shut_down(jobs, log, wait_s=STOP_WAIT_S, grace_s=STOP_SUBPROCESS_GRACE_S, final_wait_s=STOP_FINAL_WAIT_S):
    """Let the running jobs in `jobs` (run_in_background wrappers) finish within `wait_s` seconds. Any still going
    are abandoned: their subprocesses (backup, upload, download, digest) get SIGTERM, then SIGKILL after `grace_s`,
    and the jobs get `final_wait_s` more to log the result and ping their heartbeat. Ingestion runs in this process,
    so an unfinished run simply ends with it; its next run starts from the newest stored reading. Returns the labels
    of the jobs that were still running at the end."""
    def running():
        return [job.__name__.removeprefix("run_") for job in jobs if job.is_running()]

    deadline = time.monotonic() + wait_s
    if running():
        log(f"[shutdown] Waiting up to {wait_s} s for: {', '.join(running())}")
    while running() and time.monotonic() < deadline:
        time.sleep(0.5)
    if running():
        log(f"[shutdown] Still running after {wait_s} s, stopping: {', '.join(running())}")
        stopped = stop_subprocesses(grace_s)
        log(f"[shutdown] Sent SIGTERM to {stopped} subprocess group(s)")
        deadline = time.monotonic() + final_wait_s
        while running() and time.monotonic() < deadline:
            time.sleep(0.5)
    left = running()
    log(f"[shutdown] Exiting{'; abandoned: ' + ', '.join(left) if left else ''}")
    return left

def report_attention(stdout):
    """Send download_data.py's ATTENTION: lines (stored rows a newer file no longer has, kept for a person to
    decide) to Sentry as warnings, and record them for the daily digest (utils/jobs.record_attention), which lists
    them; the run itself still succeeded."""
    lines = (stdout or "").splitlines()
    for line in lines:
        if line.startswith("ATTENTION:"):
            capture_job_warning(line)
    try:
        record_attention(lines, datetime.now(SITE_TZ))
    except OSError as e:   # they are in this log and in Sentry still
        timestamped_print_download(f"[WARN] Couldn't record the ATTENTION: lines for the daily digest: {e}")

def run_download_data():
    """Run download_data.py. It downloads every new Borealis file and imports each one itself
    (via inject_sampling.py), then reports a status such as PROCESSED_2_FILES or NO_NEW_FILES."""
    cmd = [sys.executable, "scripts/download_data.py"]
    timestamped_print_download(f"Running command: {' '.join(cmd)}")
    try:
        result = run_bounded(cmd, DOWNLOAD_TIMEOUT_S)
        timestamped_print_download(f"download_data.py stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_download(f"download_data.py stderr: {result.stderr}")
        report_attention(result.stdout)
        status = download_status(result.stdout)
        timestamped_print_download(f"download_data.py finished with status {status or 'none reported'}")
        return status
    except subprocess.TimeoutExpired as e:
        timestamped_print_download(f"[ERROR] download_data.py was stopped after {DOWNLOAD_TIMEOUT_S // 60} min without finishing")
        capture_job_error(e)
        timestamped_print_download(f"download_data.py stdout so far: {e.stdout}")
        return None
    except subprocess.CalledProcessError as e:
        status = download_status(e.stdout)
        timestamped_print_download(f"download_data.py stdout: {e.stdout}")
        report_attention(e.stdout)
        if e.stderr:
            timestamped_print_download(f"download_data.py stderr: {e.stderr}")
        if status and status.startswith(("REJECTED_", "FAILED_")):
            # It ran to the end but refused (invalid) or couldn't import some files; the dataset itself is fine
            timestamped_print_download(f"[ERROR] download_data.py finished with status {status}: see the problems "
                                       f"listed above. A refused file is imported once a corrected file is uploaded.")
            capture_job_error(e)
            return status
        timestamped_print_download(f"[ERROR] download_data.py failed with exit code {e.returncode}: {e}")
        capture_job_error(e)
        # Run --list-files to debug dataset issues
        try:
            list_cmd = [sys.executable, "scripts/download_data.py", "--list-files"]
            timestamped_print_download(f"Running debug command: {' '.join(list_cmd)}")
            try:
                list_result = run_bounded(list_cmd, LIST_FILES_TIMEOUT_S)
            except subprocess.CalledProcessError as list_error:  # --list-files exits 1 when it finds nothing
                list_result = list_error
            timestamped_print_download(f"--list-files stdout: {list_result.stdout}")
            if list_result.stderr:
                timestamped_print_download(f"--list-files stderr: {list_result.stderr}")
        except Exception as le:
            timestamped_print_download(f"[ERROR] Failed to run --list-files: {le}")
        return None
    except Exception as e:
        timestamped_print_download(f"[ERROR] Unexpected error running download_data.py: {e}")
        capture_job_error(e)
        return None

def run_upload_script(script, year, month):
    """Run an upload script (scripts/<script>) for one month. True only if it exited 0 and reported the file as
    uploaded."""
    try:
        cmd = [sys.executable, f"scripts/{script}", "--year", str(year), "--month", str(month)]
        timestamped_print_upload(f"Running command: {' '.join(cmd)}")
        result = run_bounded(cmd, UPLOAD_TIMEOUT_S)
        timestamped_print_upload(f"{script} stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_upload(f"{script} stderr: {result.stderr}")
        if "Successfully uploaded" not in result.stdout:
            timestamped_print_upload(f"[ERROR] {script} finished but didn't report an upload")
            return False
        timestamped_print_upload(f"Success: {script} completed")
        return True
    except subprocess.TimeoutExpired as e:
        timestamped_print_upload(f"[ERROR] {script} was stopped after {UPLOAD_TIMEOUT_S // 60} min without finishing")
        capture_job_error(e)
        timestamped_print_upload(f"{script} stdout so far: {e.stdout}")
    except subprocess.CalledProcessError as e:
        timestamped_print_upload(f"[ERROR] {script} failed with exit code {e.returncode}: {e}")
        capture_job_error(e)
        timestamped_print_upload(f"{script} stdout: {e.stdout}")
        timestamped_print_upload(f"{script} stderr: {e.stderr}")
    except Exception as e:
        timestamped_print_upload(f"[ERROR] Unexpected error running {script}: {e}")
        capture_job_error(e)
    return False


def run_upload_data(year, month):
    """Upload one month to Borealis (scripts/upload_data.py)."""
    return run_upload_script("upload_data.py", year, month)


def run_sharepoint_upload(year, month):
    """Upload one month to SharePoint (scripts/sharepoint_upload.py)."""
    return run_upload_script("sharepoint_upload.py", year, month)

def download_job():
    """Weekly job: download and import any new Borealis sampling files."""
    timestamped_print_download("========== DOWNLOAD JOB STARTED ==========")
    status = run_download_data()
    ok = status is not None and not status.startswith(("REJECTED_", "FAILED_"))
    ping_heartbeat("download", "success" if ok else "fail")
    timestamped_print_download("========== DOWNLOAD JOB COMPLETED ==========")

def upload_job(year, month, target="Borealis", run=None):
    """Upload one month's sensor data to `target` with `run` (default run_upload_data). True if it succeeded."""
    run = run or run_upload_data
    timestamped_print_upload(f"========== {target.upper()} UPLOAD JOB STARTED ({month_key(year, month)}) ==========")
    ok = run(year, month)
    timestamped_print_upload(f"========== {target.upper()} UPLOAD JOB {'COMPLETED' if ok else 'FAILED'} ==========")
    return ok


def upload_due_months(now, target, record_path, first_month_text, first_month_setting, run, heartbeat):
    """Upload, oldest first, each month from `first_month_text` on that has ended and isn't recorded in
    `record_path`, and record each one that goes up. Pings the `heartbeat` check once if anything was due."""
    try:
        first_month = parse_month_key(first_month_text)
        uploaded = load_uploaded_months(record_path)
    except Exception as e:
        timestamped_print_upload(f"[ERROR] Not uploading to {target}: {type(e).__name__}: {e} "
                                 f"(check {first_month_setting} and {record_path})")
        capture_job_error(e)
        ping_heartbeat(heartbeat, "fail")
        return
    due = months_due_for_upload(now, uploaded, first_month)
    failed = 0
    for year, month in due:
        if upload_job(year, month, target, run):
            try:
                record_uploaded_month(record_path, year, month)
            except Exception as e:
                # The month went up, but unrecorded it is tried again tomorrow (an identical file isn't sent
                # again, so that is harmless); a full or read-only logs/ still has to reach someone.
                failed += 1
                timestamped_print_upload(f"[ERROR] {month_key(year, month)} was uploaded to {target}, but recording "
                                         f"it in {record_path} failed: {type(e).__name__}: {e}")
                capture_job_error(e)
                continue
            timestamped_print_upload(f"Recorded {month_key(year, month)} as uploaded in {record_path}")
        else:
            failed += 1
            timestamped_print_upload(f"{month_key(year, month)} was not uploaded to {target}; "
                                     f"trying again tomorrow at 02:00")
    if due:   # the upload check expects one ping a month, so days with nothing to upload don't ping
        ping_heartbeat(heartbeat, "fail" if failed else "success")


def sharepoint_upload_check(now):
    """The SharePoint copy of each month, after the Borealis one. Does nothing while no SHAREPOINT_* setting is
    set; with some but not all, logs which are missing and reports a failure (once a day, at 02:00)."""
    state, missing = sharepoint.status()
    if state == "off":
        return
    if state == "incomplete":
        error = RuntimeError(f"SharePoint settings incomplete: {', '.join(missing)} not set")
        timestamped_print_upload(f"[ERROR] Not uploading to SharePoint: {error}")
        capture_job_error(error)
        ping_heartbeat("sharepoint", "fail")
        return
    upload_due_months(now, "SharePoint", sharepoint_uploaded_months_path, SHAREPOINT_FIRST_MONTH,
                      "SHAREPOINT_UPLOAD_FIRST_MONTH", run_sharepoint_upload, "sharepoint")


def monthly_upload_check():
    """Runs every hour and acts only at 02:00 Toronto time. It uploads to Borealis, oldest first, each month from
    UPLOAD_FIRST_MONTH on that has ended and isn't recorded in uploaded_months_path, and records each one that
    goes up; then does the same for SharePoint (sharepoint_upload_check). So a missed slot (the worker was down) or
    a failed upload is retried the next day, a month that went up is never sent again, and errors are logged once
    a day, not every hour."""
    now = datetime.now(SITE_TZ)
    if now.hour != UPLOAD_HOUR:
        return
    upload_due_months(now, "Borealis", uploaded_months_path, UPLOAD_FIRST_MONTH, "BOREALIS_UPLOAD_FIRST_MONTH",
                      run_upload_data, "upload")
    sharepoint_upload_check(now)

def digest_hour():
    """DIGEST_HOUR as an hour 0-23 other than 1 and 2 (the DST hours). ValueError otherwise."""
    if not DIGEST_HOUR.isdigit() or int(DIGEST_HOUR) > 23 or int(DIGEST_HOUR) in (1, 2):
        raise ValueError(f"DIGEST_HOUR must be an hour from 0 to 23 other than 1 and 2 (DST changes at 02:00), "
                         f"got {DIGEST_HOUR!r}")
    return int(DIGEST_HOUR)

def daily_digest_check():
    """Runs every hour and acts only at DIGEST_HOUR Toronto time: builds the daily digest, which emails or
    prints itself (scripts/daily_digest.py), and logs its output."""
    try:
        hour = digest_hour()
    except ValueError as e:
        if datetime.now(SITE_TZ).hour == 0:   # once a day, not every hour
            timestamped_print_digest(f"[ERROR] No daily digest: {e}")
            capture_job_error(e)
        return
    if datetime.now(SITE_TZ).hour != hour:
        return
    cmd = [sys.executable, "scripts/daily_digest.py"]
    timestamped_print_digest(f"Running command: {' '.join(cmd)}")
    try:
        result = run_bounded(cmd, DIGEST_TIMEOUT_S)
        timestamped_print_digest(f"daily_digest.py stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_digest(f"daily_digest.py stderr: {result.stderr}")
        ok = True
    except subprocess.TimeoutExpired as e:
        timestamped_print_digest(f"[ERROR] daily_digest.py was stopped after {DIGEST_TIMEOUT_S // 60} min without finishing")
        capture_job_error(e)
        timestamped_print_digest(f"daily_digest.py stdout so far: {e.stdout}")
        ok = False
    except subprocess.CalledProcessError as e:
        timestamped_print_digest(f"[ERROR] daily_digest.py failed with exit code {e.returncode}")
        capture_job_error(e)
        timestamped_print_digest(f"daily_digest.py stdout: {e.stdout}")
        timestamped_print_digest(f"daily_digest.py stderr: {e.stderr}")
        ok = False
    ping_heartbeat("digest", "success" if ok else "fail")

def nightly_backup_check(log=None, run=None):
    """Runs every hour at :15 and acts only at BACKUP_HOUR Toronto time: backs up the database
    (scripts/backup_db.py: pg_dump, a check of the dump, then retention), logs its output and pings the backup
    check, /fail if it failed. Returns True/False when it ran, None outside its hour."""
    log = log or timestamped_print_backup
    run = run or run_bounded
    if datetime.now(SITE_TZ).hour != BACKUP_HOUR:
        return None
    cmd = [sys.executable, "scripts/backup_db.py"]
    log("========== DATABASE BACKUP STARTED ==========")
    ping_heartbeat("backup", "start")
    try:
        result = run(cmd, BACKUP_TIMEOUT_S)
        log(f"backup_db.py stdout: {result.stdout}")
        if result.stderr:
            log(f"backup_db.py stderr: {result.stderr}")
        for line in (result.stderr or "").splitlines():
            if line.startswith("WARNING:"):   # the backup worked, but e.g. deleting old dumps didn't
                capture_job_warning(line)
        ok = True
    except subprocess.TimeoutExpired as e:
        log(f"[ERROR] backup_db.py was stopped after {BACKUP_TIMEOUT_S // 60} min without finishing")
        capture_job_error(e)
        log(f"backup_db.py stdout so far: {e.stdout}")
        ok = False
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] backup_db.py failed with exit code {e.returncode}")
        capture_job_error(e)
        log(f"backup_db.py stdout: {e.stdout}")
        log(f"backup_db.py stderr: {e.stderr}")
        ok = False
    except Exception as e:
        log(f"[ERROR] Unexpected error running backup_db.py: {e}")
        capture_job_error(e)
        ok = False
    ping_heartbeat("backup", "success" if ok else "fail")
    log(f"========== DATABASE BACKUP {'COMPLETED' if ok else 'FAILED'} ==========")
    return ok


def restore_check_day():
    """RESTORE_CHECK_DAY as a day of the month (1-28, so every month has it), or None when it is "off".
    ValueError otherwise."""
    if RESTORE_CHECK_DAY.lower() == "off":
        return None
    if not RESTORE_CHECK_DAY.isdigit() or not 1 <= int(RESTORE_CHECK_DAY) <= 28:
        raise ValueError(f"RESTORE_CHECK_DAY must be a day from 1 to 28, or off, got {RESTORE_CHECK_DAY!r}")
    return int(RESTORE_CHECK_DAY)


def monthly_restore_check(log=None, run=None):
    """Runs every hour at :30 and acts only at RESTORE_HOUR:30 Toronto time on RESTORE_CHECK_DAY: the restore drill
    (scripts/restore_check.py) restores the newest dump into a throwaway database, compares its row counts with
    those recorded when the dump was taken and with the live ones, and drops it. Pings the restore check (/start,
    then success or /fail). Returns True/False when it ran, None otherwise."""
    log = log or timestamped_print_backup
    run = run or run_bounded
    now = datetime.now(SITE_TZ)
    try:
        day = restore_check_day()
    except ValueError as e:
        if now.hour == RESTORE_HOUR:   # once a day, not every hour
            log(f"[ERROR] No restore drill: {e}")
            capture_job_error(e)
            ping_heartbeat("restore", "fail")
        return None
    if day is None or now.day != day or now.hour != RESTORE_HOUR:
        return None
    cmd = [sys.executable, "scripts/restore_check.py"]
    log("========== RESTORE DRILL STARTED ==========")
    ping_heartbeat("restore", "start")
    try:
        result = run(cmd, RESTORE_TIMEOUT_S)
        log(f"restore_check.py stdout: {result.stdout}")
        if result.stderr:
            log(f"restore_check.py stderr: {result.stderr}")
        ok = True
    except subprocess.TimeoutExpired as e:
        log(f"[ERROR] restore_check.py was stopped after {RESTORE_TIMEOUT_S // 60} min without finishing")
        capture_job_error(e)
        log(f"restore_check.py stdout so far: {e.stdout}")
        ok = False
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] restore_check.py failed with exit code {e.returncode}")
        capture_job_error(e)
        log(f"restore_check.py stdout: {e.stdout}")
        log(f"restore_check.py stderr: {e.stderr}")
        ok = False
    except Exception as e:
        log(f"[ERROR] Unexpected error running restore_check.py: {e}")
        capture_job_error(e)
        ok = False
    if not ok:   # a drill that was killed can't drop its own database, and it is a full copy of the live one
        drop_restore_leftovers(log, run)
    ping_heartbeat("restore", "success" if ok else "fail")
    log(f"========== RESTORE DRILL {'PASSED' if ok else 'FAILED'} ==========")
    return ok


def drop_restore_leftovers(log=None, run=None):
    """Drop the restore drill databases left by drills that didn't finish (scripts/restore_check.py
    --drop-leftovers; never one a running drill holds). At start-up and after a failed drill; the nightly backup
    does it too. A failure is logged and reported, and changes no heartbeat. True if it worked."""
    log = log or timestamped_print_backup
    run = run or run_bounded
    try:
        result = run([sys.executable, "scripts/restore_check.py", "--drop-leftovers"], LEFTOVERS_TIMEOUT_S)
        log(f"restore_check.py --drop-leftovers: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Dropping leftover restore drill databases failed: {(e.stderr or '').strip()}")
        capture_job_error(e)
    except Exception as e:   # TimeoutExpired and anything unexpected
        log(f"[ERROR] Dropping leftover restore drill databases failed: {type(e).__name__}: {e}")
        capture_job_error(e)
    return False


def skip_reporter(heartbeat, fail_after=SKIPS_BEFORE_FAIL):
    """An on_skip callback for run_in_background (utils/jobs.py): each run skipped because the previous one is still
    going is logged in the job's heartbeat check (/log, which changes nothing there), and from `fail_after` skips in
    a row on, the check gets /fail and Sentry a warning (once per stuck run), since the job is then stuck rather than
    slow. A job that starts again resets the count."""
    def on_skip(skips, message):
        if skips < fail_after:
            ping_heartbeat(heartbeat, "log", message=f"{message} ({skips} in a row)")
            return
        ping_heartbeat(heartbeat, "fail", message=f"{message}: {skips} runs in a row skipped, so it looks stuck")
        if skips == fail_after:
            capture_job_warning(f"{message}: {skips} runs in a row skipped, so it looks stuck")
    return on_skip


def report_unset_heartbeats(log, sentry_warning=None, env=None):
    """At start-up: name every HEALTHCHECK_URL_* of the worker's jobs that isn't set, in the log (and so, with
    WORKER_LOG_TO_STDOUT, in docker logs) and as one Sentry warning. Without them, a worker that stops, or a job
    that stops running, reports nothing anywhere. Returns the names."""
    state, _ = sharepoint.status(env)
    missing = unset_heartbeats(env, sharepoint_on=state != "off")   # leaves out the drill's while it is off
    if missing:
        message = (f"Heartbeats not set: {', '.join(missing)}. Those jobs report nothing if they stop or keep "
                   f"failing (README, Monitoring).")
        log(f"[WARN] {message}")
        (sentry_warning or capture_job_warning)(message)
    return missing

def api_injection_job():
    """Every 10 minutes: fetch new vendor API data and store it, ping the ingestion heartbeat (success, or /fail
    when either vendor failed: inject_all_new_data raises then), then run the alert check."""
    try:
        print("========== API INJECTION STARTED ==========")
        print("Calling inject_all_new_data() function...")
        inject_all_new_data()
        print("inject_all_new_data() function completed")
        print("========== API INJECTION COMPLETED ==========")
    except Exception as e:
        print("========== API INJECTION FAILED ==========")
        print(f"[ERROR] inject_all_new_data failed: {e}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        print("========== API INJECTION ERROR END ==========")
        capture_job_error(e)   # LI-COR and WQData failures are reported in inject_all_new_data itself
        ping_heartbeat("ingestion", "fail")
    else:
        ping_heartbeat("ingestion", "success")
    alert_check_job()   # after failed runs too: that's how a vendor outage is noticed

def alert_check_job():
    """Check for sensor and vendor problems and email new ones (scripts/check_alerts.py). Never raises: a crash is
    logged to logs/alerts.log and reported to Sentry, and pings the alerts heartbeat with /fail, as does an email
    that couldn't be sent."""
    try:
        from inject_from_api import app as ingestion_app   # its app (and connection pool) is reused, not rebuilt
        with ingestion_app.app_context():
            summary = check_alerts.run(log=timestamped_print_alerts)
        ok = summary["email"] not in ("failed", "waiting")   # waiting: an earlier send failed, retried later
    except Exception as e:
        timestamped_print_alerts(f"[ERROR] The alert check failed: {type(e).__name__}: {e}")
        capture_job_error(e)
        ok = False
    ping_heartbeat("alerts", "success" if ok else "fail")

if __name__ == "__main__":
    # Main entry point: one scheduler loop for all jobs
    # Ensure the log folder exists; if it can't be made, the jobs still run and their lines are dropped
    try:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"[scheduler] can't create {os.path.dirname(log_file_path)}: {e}\n")

    # docker compose stop (and every deploy that recreates the worker) sends SIGTERM; Ctrl-C sends SIGINT
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    touch_alive()

    # Save original print and override for API scheduler
    builtins._original_print = builtins.print
    builtins.print = timestamped_print

    # Initial startup message (file; optionally stdout)
    print("WELL Scheduler Container Started!")
    if LOG_TO_STDOUT:
        builtins._original_print("[scheduler] Mirroring logs to stdout is ENABLED via WORKER_LOG_TO_STDOUT.")
    else:
        builtins._original_print("[scheduler] Logs are written to /app/app/logs/*. Set WORKER_LOG_TO_STDOUT=1 to mirror to stdout.")

    # A dead worker can only be noticed through the heartbeats, so the unset ones are named in docker logs too
    def log_everywhere(line):
        print(line)
        if not LOG_TO_STDOUT:
            builtins._original_print(f"[scheduler] {line}")
    report_unset_heartbeats(log_everywhere)

    # Each job starts in its own thread and is skipped while its previous run is still going; a skip is logged in
    # the job's heartbeat check, and several in a row fail it (skip_reporter).
    hour, week = 60 * 60, 7 * 24 * 60 * 60
    api_run = run_in_background(api_injection_job, log=print, on_skip=skip_reporter("ingestion"))
    download_run = run_in_background(download_job, log=timestamped_print_download,
                                     on_skip=skip_reporter("download", skips_before_fail(DOWNLOAD_TIMEOUT_S, week)))
    # An upload run sends a month to Borealis, then to SharePoint, each under UPLOAD_TIMEOUT_S
    upload_run = run_in_background(monthly_upload_check, log=timestamped_print_upload,
                                   on_skip=skip_reporter("upload", skips_before_fail(2 * UPLOAD_TIMEOUT_S, hour)))
    digest_run = run_in_background(daily_digest_check, log=timestamped_print_digest,
                                   on_skip=skip_reporter("digest", skips_before_fail(DIGEST_TIMEOUT_S, hour)))
    backup_run = run_in_background(nightly_backup_check, log=timestamped_print_backup,
                                   on_skip=skip_reporter("backup", skips_before_fail(BACKUP_TIMEOUT_S, hour)))
    restore_run = run_in_background(monthly_restore_check, log=timestamped_print_backup,
                                    on_skip=skip_reporter("restore", skips_before_fail(RESTORE_TIMEOUT_S, hour)))
    # A drill killed with the last worker (or out of memory) left its database behind: drop it now, in the
    # background so ingestion catches up at once
    run_in_background(drop_restore_leftovers, log=timestamped_print_backup)()

    scheduler = schedule.Scheduler()
    scheduler.every(10).minutes.do(api_run)
    scheduler.every().sunday.at("00:00").do(download_run)
    scheduler.every().hour.at(":00").do(upload_run)  # acts only at 02:00 Toronto time (monthly_upload_check)
    scheduler.every().hour.at(":00").do(digest_run)  # acts only at DIGEST_HOUR Toronto time (daily_digest_check)
    scheduler.every().hour.at(":15").do(backup_run)  # acts only at 03:15 Toronto time (nightly_backup_check)
    scheduler.every().hour.at(":30").do(restore_run)  # acts only at 05:30 on RESTORE_CHECK_DAY (monthly_restore_check)

    print("Schedule: API injection every 10 minutes, each followed by the alert check; Borealis download Sundays 00:00; "
          "Borealis upload (then SharePoint, if configured) at 02:00 Toronto time of each ended month not yet "
          "uploaded; "
          f"daily digest at {DIGEST_HOUR}:00 Toronto time; database backup at {BACKUP_HOUR:02d}:15 Toronto time "
          f"and restore drill at {RESTORE_HOUR:02d}:30 on day {RESTORE_CHECK_DAY} of each month (logs/backup.log).")
    timestamped_print_download("Download scheduler ready: Sundays at 00:00. Nothing runs at startup; "
                               "run `python scripts/download_data.py` by hand to fetch now.")
    timestamped_print_upload("Upload scheduler ready: at 02:00 Toronto time, each month from "
                             f"{UPLOAD_FIRST_MONTH} on that has ended and isn't recorded in {uploaded_months_path} "
                             "is uploaded (so last month goes up on the 1st, and a failed month is retried daily). "
                             "Nothing runs at startup; run `python scripts/upload_data.py --year Y --month M` by hand "
                             "to upload a month.")
    sharepoint_state, sharepoint_missing = sharepoint.status()
    timestamped_print_upload({
        "off": "SharePoint copy: off (no SHAREPOINT_* settings).",
        "on": f"SharePoint copy: on, after Borealis, each month from {SHAREPOINT_FIRST_MONTH} not recorded in "
              f"{sharepoint_uploaded_months_path}.",
    }.get(sharepoint_state, f"[ERROR] SharePoint copy: settings incomplete, {', '.join(sharepoint_missing)} not set."))

    # Catch up on vendor data right away after a restart; the Borealis jobs wait for their slots.
    api_run()

    last_alive = time.monotonic()
    while not stopping.is_set():
        scheduler.run_pending()
        if time.monotonic() - last_alive >= ALIVE_EVERY_S:
            touch_alive()
            last_alive = time.monotonic()
        time.sleep(1)

    print("Shutting down the scheduler (stop requested); starting no new jobs")
    shut_down([api_run, download_run, upload_run, digest_run, backup_run, restore_run], print)
