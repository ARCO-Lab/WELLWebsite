import schedule
import time
import sys
import builtins
import subprocess
import threading
import os
import re
from inject_from_api import inject_all_new_data

log_file_path = "app/logs/db_injections.log"
download_log_file_path = "app/logs/download_injections.log"
upload_log_file_path = "app/logs/db_uploads.log"

# Override print to add timestamps for API scheduler
def timestamped_print(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    builtins._original_print(timestamp, *args, **kwargs)
    sys.stdout.flush()

# Override print for download scheduler
def timestamped_print_download(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(download_log_file_path, "a") as f:
        builtins._original_print(timestamp, *args, file=f, **kwargs)
        f.flush()

# Override print for upload scheduler
def timestamped_print_upload(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(upload_log_file_path, "a") as f:
        builtins._original_print(timestamp, *args, file=f, **kwargs)
        f.flush()

def run_download_data(first_run=False):
    """Run download_data.py and return the temporary file path if new data was downloaded."""
    try:
        cmd = [sys.executable, "app/scripts/download_data.py"]
        if first_run:
            cmd.append("--force")
            timestamped_print_download(f"Running command: {' '.join(cmd)}")
        else:
            timestamped_print_download(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        timestamped_print_download(f"download_data.py stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_download(f"download_data.py stderr: {result.stderr}")
        
        # Check for OUTPUT line with temporary file path
        match = re.search(r'OUTPUT: (.+)', result.stdout)
        if match and "ERROR" not in result.stdout:
            tmp_file_path = match.group(1)
            timestamped_print_download(f"Success: download_data.py downloaded new file. Temporary file path: {tmp_file_path}")
            return tmp_file_path
        timestamped_print_download("No new file downloaded by download_data.py")
        return None
    except subprocess.CalledProcessError as e:
        timestamped_print_download(f"[ERROR] download_data.py failed with exit code {e.returncode}: {e}")
        timestamped_print_download(f"download_data.py stdout: {e.stdout}")
        timestamped_print_download(f"download_data.py stderr: {e.stderr}")
        # Run --list-files to debug dataset issues
        try:
            list_cmd = [sys.executable, "app/scripts/download_data.py", "--list-files"]
            timestamped_print_download(f"Running debug command: {' '.join(list_cmd)}")
            list_result = subprocess.run(
                list_cmd,
                capture_output=True,
                text=True
            )
            timestamped_print_download(f"--list-files stdout: {list_result.stdout}")
            if list_result.stderr:
                timestamped_print_download(f"--list-files stderr: {list_result.stderr}")
        except Exception as le:
            timestamped_print_download(f"[ERROR] Failed to run --list-files: {le}")
        return None
    except Exception as e:
        timestamped_print_download(f"[ERROR] Unexpected error running download_data.py: {e}")
        return None

def run_inject_sampling(tmp_file_path):
    """Run inject_sampling.py with the temporary file path."""
    try:
        cmd = [sys.executable, "app/scripts/inject_sampling.py", tmp_file_path]
        timestamped_print_download(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        timestamped_print_download(f"inject_sampling.py stdout: {result.stdout}")
        if result.stderr:
            timestamped_print_download(f"inject_sampling.py stderr: {result.stderr}")
        timestamped_print_download("Success: inject_sampling.py completed")
    except subprocess.CalledProcessError as e:
        timestamped_print_download(f"[ERROR] inject_sampling.py failed with exit code {e.returncode}: {e}")
        timestamped_print_download(f"inject_sampling.py stdout: {e.stdout}")
        timestamped_print_download(f"inject_sampling.py stderr: {e.stderr}")
    except Exception as e:
        timestamped_print_download(f"[ERROR] Unexpected error running inject_sampling.py: {e}")
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
                timestamped_print_download(f"DEBUG: Cleaned up temporary file: {tmp_file_path}")
        except Exception as e:
            timestamped_print_download(f"[ERROR] Failed to clean up temporary file {tmp_file_path}: {e}")

def run_upload_data():
    """Run upload_data.py for the previous month's data."""
    try:
        # Run upload_data.py without arguments (defaults to last month)
        cmd = [sys.executable, "app/scripts/upload_data.py"]
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

def download_job(first_run=False):
    """Weekly job: run download_data.py and inject_sampling.py if new data is found."""
    timestamped_print_download(f"Running download job (first_run={first_run})")
    tmp_file_path = run_download_data(first_run=first_run)
    if tmp_file_path:
        timestamped_print_download(f"New data file downloaded. Running inject_sampling.py with {tmp_file_path}...")
        run_inject_sampling(tmp_file_path)
    else:
        timestamped_print_download("No new data file downloaded. Skipping inject_sampling.py.")
    timestamped_print_download("Download job completed.")

def upload_job(first_run=False):
    """Monthly job: run upload_data.py for the previous month."""
    timestamped_print_upload(f"Running upload job (first_run={first_run})")
    run_upload_data()
    timestamped_print_upload("Upload job completed.")

def api_injection_job():
    """Original job: run inject_all_new_data every 10 minutes."""
    try:
        print("Starting inject_all_new_data")
        inject_all_new_data()
        print("Success: inject_all_new_data completed")
    except Exception as e:
        print(f"[ERROR] inject_all_new_data failed: {e}")

def run_api_scheduler():
    """Run the original API injection scheduler (every 10 minutes)."""
    print("API Scheduler started. Running every 10 minutes...\n")
    api_injection_job()
    schedule.every(10).minutes.do(api_injection_job)
    while True:
        schedule.run_pending()
        time.sleep(1)

def run_download_scheduler():
    """Run the download scheduler (weekly)."""
    timestamped_print_download("Download Scheduler started. Running every Sunday at 00:00...\n")
    timestamped_print_download("Executing immediate download job")
    download_job(first_run=True)
    timestamped_print_download("Immediate download job completed")
    schedule.every().sunday.at("00:00").do(download_job, first_run=False)
    while True:
        schedule.run_pending()
        time.sleep(60)

def run_upload_scheduler():
    """Run the upload scheduler (monthly)."""
    timestamped_print_upload("Upload Scheduler started. Running on the 1st of each month at 02:00...\n")
    timestamped_print_upload("Executing immediate upload job for last month's data")
    upload_job(first_run=True)
    timestamped_print_upload("Immediate upload job completed")
    
    # Schedule monthly runs on the 1st at 2 AM (to avoid conflicts with other jobs)
    schedule.every().month.do(upload_job, first_run=False)
    
    # Since schedule doesn't have built-in monthly support, we'll check daily
    # and run on the 1st of each month
    def check_monthly_upload():
        current_day = time.strftime("%d")
        if current_day == "01":
            upload_job(first_run=False)
    
    # Clear the monthly schedule and use daily check instead
    schedule.clear('upload')
    schedule.every().day.at("02:00").do(check_monthly_upload).tag('upload')
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Ensure log directories exist
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(download_log_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(upload_log_file_path), exist_ok=True)

    # Redirect stdout and stderr for API scheduler to original log file
    sys.stdout = open(log_file_path, "a")
    sys.stderr = sys.stdout

    # Save original print and override for API scheduler
    builtins._original_print = builtins.print
    builtins.print = timestamped_print

    # Log main thread start
    print("Main thread started. Starting all schedulers...")

    # Start API scheduler in one thread
    print("Starting API scheduler thread")
    api_thread = threading.Thread(target=run_api_scheduler, daemon=True)
    api_thread.start()

    # Start download scheduler in another thread
    timestamped_print_download("Starting download scheduler thread")
    download_thread = threading.Thread(target=run_download_scheduler, daemon=True)
    download_thread.start()

    # Start upload scheduler in a third thread
    timestamped_print_upload("Starting upload scheduler thread")
    upload_thread = threading.Thread(target=run_upload_scheduler, daemon=True)
    upload_thread.start()

    # Keep main thread alive
    try:
        print("Main thread running with 3 schedulers. Press Ctrl+C to stop.")
        print("- API injections: every 10 minutes")
        print("- Download jobs: every Sunday at 00:00")
        print("- Upload jobs: 1st of each month at 02:00")
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("Shutting down all schedulers...")
        timestamped_print_download("Shutting down download scheduler...")
        timestamped_print_upload("Shutting down upload scheduler...")
        sys.exit(0)