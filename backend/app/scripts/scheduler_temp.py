import schedule
import time
import sys
import builtins
from inject_from_api import inject_all_new_data

log_file_path = "app/logs/db_injections.log"

# Override print to add timestamps
def timestamped_print(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    builtins._original_print(timestamp, *args, **kwargs)

if __name__ == "__main__":
    # Redirect stdout and stderr to log file
    sys.stdout = open(log_file_path, "a")
    sys.stderr = sys.stdout

    # Save original print and override
    builtins._original_print = builtins.print
    builtins.print = timestamped_print

    print("Scheduler started. Running every 10 minutes...\n")

    def job():
        try:
            inject_all_new_data()
        except Exception as e:
            print(f"[ERROR] Injection failed: {e}")

    job()
    schedule.every(10).minutes.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)
