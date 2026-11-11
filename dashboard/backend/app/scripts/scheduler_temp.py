# This script runs the worker's scheduled jobs: vendor API ingestion every 10 minutes, the weekly
# Borealis sampling download (Sundays 00:00) and the monthly Borealis upload (02:00 Toronto time: each
# month that has ended and isn't uploaded yet, so last month goes up on the 1st and a failed one is retried daily),
# followed by the same month's upload to SharePoint when SHAREPOINT_* is set (scripts/sharepoint_upload.py), with
# its own record of months, so either copy can fail and be retried without the other.
# It also builds the daily digest (scripts/daily_digest.py) at DIGEST_HOUR (default 07:00 Toronto time), and
# pings a Healthchecks.io check after each ingestion run, sampling download, monthly upload (Borealis and
# SharePoint each have their own) and digest
# (utils/heartbeat.py).
# One scheduler loop starts each job in its own thread, and a job that is still running is never
# started again, so every job runs once per slot. It logs to files under logs/.
# When SENTRY_DSN is set, every failure it logs is also reported to Sentry, tagged with the job (utils/sentry.py).

import schedule
import time
import sys
import builtins
import subprocess
import os
import pathlib
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from utils.sentry import init_sentry, capture_job_error  # noqa: E402

# Report errors to Sentry when SENTRY_DSN is set (utils/sentry.py). First, so they are tagged worker:
# inject_from_api imports server.py, which would otherwise start reporting as the API.
if __name__ == "__main__":
    init_sentry("worker")

from inject_from_api import inject_all_new_data  # noqa: E402
from utils.jobs import (  # noqa: E402
    run_in_background, run_bounded, download_status,
    load_uploaded_months, record_uploaded_month, months_due_for_upload, month_key, parse_month_key, UPLOAD_HOUR,
)
from utils.heartbeat import ping_heartbeat  # noqa: E402
from utils import sharepoint  # noqa: E402

log_file_path = "logs/db_injections.log"
download_log_file_path = "logs/download_injections.log"
upload_log_file_path = "logs/db_uploads.log"
digest_log_file_path = "logs/daily_digest.log"
# Months already uploaded to Borealis, e.g. {"uploaded_months": ["2026-10"]}. It sits with the logs (a volume
# on the host), so it survives restarts and rebuilds.
uploaded_months_path = "logs/uploaded_months.json"
# The first month the scheduler uploads; earlier months are never sent (they went up, or didn't, before
# uploads were recorded). Override with BOREALIS_UPLOAD_FIRST_MONTH=YYYY-MM.
UPLOAD_FIRST_MONTH = os.getenv("BOREALIS_UPLOAD_FIRST_MONTH", "2026-10")
# The same for the SharePoint copy, which has its own record. Override with SHAREPOINT_UPLOAD_FIRST_MONTH=YYYY-MM.
sharepoint_uploaded_months_path = "logs/sharepoint_uploaded_months.json"
SHAREPOINT_FIRST_MONTH = os.getenv("SHAREPOINT_UPLOAD_FIRST_MONTH", UPLOAD_FIRST_MONTH)

# Site time. Monthly uploads cover Toronto calendar months (the CSV shows Toronto time), so months start and end there, not in UTC
# (the container's clock).
SITE_TZ = ZoneInfo("America/Toronto")

# Hard limits for the Borealis subprocesses. A run that hangs is stopped, so it can't hold its
# job's lock (see utils.jobs.run_in_background) and block every later run.
DOWNLOAD_TIMEOUT_S = 2 * 60 * 60
UPLOAD_TIMEOUT_S = 2 * 60 * 60
LIST_FILES_TIMEOUT_S = 5 * 60
DIGEST_TIMEOUT_S = 10 * 60

# The hour (site time, 0-23) the daily digest is built and sent; checked when it is due, so a bad value is
# logged there instead of stopping the scheduler. Not 1 or 2: clocks change at 02:00, so on those days 01:00
# happens twice (two digests) or 02:00 not at all (none).
DIGEST_HOUR = os.getenv("DIGEST_HOUR", "7").strip()

# Control whether to also mirror file logs to stdout (Docker logs)
# Set WORKER_LOG_TO_STDOUT=1|true to enable
LOG_TO_STDOUT = os.getenv("WORKER_LOG_TO_STDOUT", "").lower() in ("1", "true", "yes", "on")

# Override print to add timestamps for API scheduler (file; optional stdout)
def timestamped_print(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    # Always write to file
    with open(log_file_path, "a") as f:
        builtins._original_print(timestamp, *args, file=f, **kwargs)
        f.flush()
    # Optionally mirror to stdout for debugging/visibility
    if LOG_TO_STDOUT:
        builtins._original_print(timestamp, *args, **kwargs)

# Override print for download scheduler
def timestamped_print_download(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(download_log_file_path, "a") as f:
        builtins._original_print(timestamp, *args, file=f, **kwargs)
        f.flush()
    if LOG_TO_STDOUT:
        builtins._original_print(timestamp, *args, **kwargs)

# Override print for upload scheduler
def timestamped_print_upload(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(upload_log_file_path, "a") as f:
        builtins._original_print(timestamp, *args, file=f, **kwargs)
        f.flush()
    if LOG_TO_STDOUT:
        builtins._original_print(timestamp, *args, **kwargs)

# Override print for the daily digest
def timestamped_print_digest(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(digest_log_file_path, "a") as f:
        builtins._original_print(timestamp, *args, file=f, **kwargs)
        f.flush()
    if LOG_TO_STDOUT:
        builtins._original_print(timestamp, *args, **kwargs)

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
            record_uploaded_month(record_path, year, month)
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

def api_injection_job():
    """Every 10 minutes: fetch new vendor API data and store it, then ping the ingestion heartbeat:
    success, or /fail when either vendor failed (inject_all_new_data raises then)."""
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
        return
    ping_heartbeat("ingestion", "success")

if __name__ == "__main__":
    # Main entry point: one scheduler loop for all jobs
    # Ensure log directories exist
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(download_log_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(upload_log_file_path), exist_ok=True)

    # Save original print and override for API scheduler
    builtins._original_print = builtins.print
    builtins.print = timestamped_print

    # Initial startup message (file; optionally stdout)
    print("WELL Scheduler Container Started!")
    if LOG_TO_STDOUT:
        builtins._original_print("[scheduler] Mirroring logs to stdout is ENABLED via WORKER_LOG_TO_STDOUT.")
    else:
        builtins._original_print("[scheduler] Logs are written to /app/app/logs/*. Set WORKER_LOG_TO_STDOUT=1 to mirror to stdout.")

    # Each job starts in its own thread and is skipped while its previous run is still going.
    api_run = run_in_background(api_injection_job, log=print)
    download_run = run_in_background(download_job, log=timestamped_print_download)
    upload_run = run_in_background(monthly_upload_check, log=timestamped_print_upload)
    digest_run = run_in_background(daily_digest_check, log=timestamped_print_digest)

    scheduler = schedule.Scheduler()
    scheduler.every(10).minutes.do(api_run)
    scheduler.every().sunday.at("00:00").do(download_run)
    scheduler.every().hour.at(":00").do(upload_run)  # acts only at 02:00 Toronto time (monthly_upload_check)
    scheduler.every().hour.at(":00").do(digest_run)  # acts only at DIGEST_HOUR Toronto time (daily_digest_check)

    print("Schedule: API injection every 10 minutes; Borealis download Sundays 00:00; "
          "Borealis upload (then SharePoint, if configured) at 02:00 Toronto time of each ended month not yet "
          "uploaded; "
          f"daily digest at {DIGEST_HOUR}:00 Toronto time.")
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

    try:
        while True:
            scheduler.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down the scheduler...")
