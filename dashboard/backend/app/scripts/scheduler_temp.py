# This script runs the worker's scheduled jobs: vendor API ingestion every 10 minutes, the weekly
# Borealis sampling download (Sundays 00:00) and the monthly Borealis upload (the 1st, 02:00).
# One scheduler loop starts each job in its own thread, and a job that is still running is never
# started again, so every job runs once per slot. It logs to files under logs/.

import schedule
import time
import sys
import builtins
import subprocess
import os
import pathlib
from inject_from_api import inject_all_new_data

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from utils.jobs import run_in_background, download_status  # noqa: E402

log_file_path = "logs/db_injections.log"
download_log_file_path = "logs/download_injections.log"
upload_log_file_path = "logs/db_uploads.log"

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

def run_download_data():
    """Run download_data.py. It downloads every new Borealis file and imports each one itself
    (via inject_sampling.py), then reports a status such as PROCESSED_2_FILES or NO_NEW_FILES."""
    cmd = [sys.executable, "scripts/download_data.py"]
    timestamped_print_download(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        timestamped_print_download(f"download_data.py stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_download(f"download_data.py stderr: {result.stderr}")
        status = download_status(result.stdout)
        timestamped_print_download(f"download_data.py finished with status {status or 'none reported'}")
        return status
    except subprocess.CalledProcessError as e:
        timestamped_print_download(f"[ERROR] download_data.py failed with exit code {e.returncode}: {e}")
        timestamped_print_download(f"download_data.py stdout: {e.stdout}")
        timestamped_print_download(f"download_data.py stderr: {e.stderr}")
        # Run --list-files to debug dataset issues
        try:
            list_cmd = [sys.executable, "scripts/download_data.py", "--list-files"]
            timestamped_print_download(f"Running debug command: {' '.join(list_cmd)}")
            list_result = subprocess.run(list_cmd, capture_output=True, text=True)
            timestamped_print_download(f"--list-files stdout: {list_result.stdout}")
            if list_result.stderr:
                timestamped_print_download(f"--list-files stderr: {list_result.stderr}")
        except Exception as le:
            timestamped_print_download(f"[ERROR] Failed to run --list-files: {le}")
        return None
    except Exception as e:
        timestamped_print_download(f"[ERROR] Unexpected error running download_data.py: {e}")
        return None

def run_upload_data():
    """Run upload_data.py for the previous month's data."""
    try:
        # Run upload_data.py without arguments (defaults to last month)
        cmd = [sys.executable, "scripts/upload_data.py"]
        timestamped_print_upload(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        timestamped_print_upload(f"upload_data.py stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_upload(f"upload_data.py stderr: {result.stderr}")
        timestamped_print_upload("Success: upload_data.py completed")
    except subprocess.CalledProcessError as e:
        timestamped_print_upload(f"[ERROR] upload_data.py failed with exit code {e.returncode}: {e}")
        timestamped_print_upload(f"upload_data.py stdout: {e.stdout}")
        timestamped_print_upload(f"upload_data.py stderr: {e.stderr}")
    except Exception as e:
        timestamped_print_upload(f"[ERROR] Unexpected error running upload_data.py: {e}")

def download_job():
    """Weekly job: download and import any new Borealis sampling files."""
    timestamped_print_download("========== DOWNLOAD JOB STARTED ==========")
    run_download_data()
    timestamped_print_download("========== DOWNLOAD JOB COMPLETED ==========")

def upload_job():
    """Monthly job: upload the previous month's sensor data to Borealis."""
    timestamped_print_upload("========== UPLOAD JOB STARTED ==========")
    run_upload_data()
    timestamped_print_upload("========== UPLOAD JOB COMPLETED ==========")

def monthly_upload_check():
    """Runs daily at 02:00 (schedule has no monthly interval) and uploads on the 1st of the month."""
    if time.strftime("%d") == "01":
        upload_job()

def api_injection_job():
    """Every 10 minutes: fetch new vendor API data and store it."""
    try:
        print("========== API INJECTION STARTED ==========")
        print("Calling inject_all_new_data() function...")
        inject_all_new_data()
        print("inject_all_new_data() function completed")
        print("========== API INJECTION COMPLETED ==========")
    except Exception as e:
        print(f"========== API INJECTION FAILED ==========")
        print(f"[ERROR] inject_all_new_data failed: {e}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        print("========== API INJECTION ERROR END ==========")

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

    scheduler = schedule.Scheduler()
    scheduler.every(10).minutes.do(api_run)
    scheduler.every().sunday.at("00:00").do(download_run)
    scheduler.every().day.at("02:00").do(upload_run)

    print("Schedule: API injection every 10 minutes; Borealis download Sundays 00:00; "
          "Borealis upload on the 1st at 02:00.")
    timestamped_print_download("Download scheduler ready: Sundays at 00:00. Nothing runs at startup; "
                               "run `python scripts/download_data.py` by hand to fetch now.")
    timestamped_print_upload("Upload scheduler ready: the 1st of each month at 02:00. Nothing runs at startup; "
                             "run `python scripts/upload_data.py --year Y --month M` by hand to upload a month.")

    # Catch up on vendor data right away after a restart; the Borealis jobs wait for their slots.
    api_run()

    try:
        while True:
            scheduler.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down the scheduler...")
