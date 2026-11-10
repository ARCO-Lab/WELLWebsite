"""Helpers for the worker's scheduler (scripts/scheduler_temp.py). Pure: no database or vendor settings."""
import re
import threading


def run_in_background(job, log=print, name=None):
    """Wrap `job` so each call starts it in its own thread and returns at once.

    If the previous run of the same job is still going, the call is skipped and logged instead,
    so a slow run can never overlap the next one. Returning at once matters too: the `schedule`
    library only moves a job's next run time after the scheduled callable returns, so a job that
    blocks the loop looks "still due" to anything else polling the scheduler meanwhile.
    """
    lock = threading.Lock()
    label = name or getattr(job, "__name__", "job")

    def start():
        if not lock.acquire(blocking=False):
            log(f"[WARN] {label} is still running from its last start; skipping this run")
            return None

        def target():
            try:
                job()
            except Exception as e:  # never let a failed run leave the lock held
                log(f"[ERROR] {label} failed: {e}")
            finally:
                lock.release()

        thread = threading.Thread(target=target, name=label, daemon=True)
        thread.start()
        return thread

    start.__name__ = f"run_{label}"
    return start


def download_status(stdout):
    """The status download_data.py reports on its last `OUTPUT: <status>` line, e.g. "PROCESSED_2_FILES",
    "NO_NEW_FILES", "NO_FILES" or "NO_FILES_PROCESSED". None if it printed no status.

    download_data.py imports every file it downloads itself, so this is a status, never a file path.
    """
    found = re.findall(r"^OUTPUT: (\S+)\s*$", stdout or "", flags=re.MULTILINE)
    return found[-1] if found else None
