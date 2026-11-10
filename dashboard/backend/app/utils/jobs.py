"""Helpers for the worker's scheduler (scripts/scheduler_temp.py). Pure: no database or vendor settings."""
import os
import re
import signal
import subprocess
import threading
import time


def run_in_background(job, log=print, name=None):
    """Wrap `job` so each call starts it in its own thread and returns at once.

    If the previous run of the same job is still going, the call is skipped and logged instead,
    so a slow run can never overlap the next one. The skip message says how long the run has been
    going, so a hung job shows up in the log; jobs must bound their own I/O (request and subprocess
    timeouts), since a run that never returns keeps the lock. Returning at once matters too: the
    `schedule` library only moves a job's next run time after the scheduled callable returns, so a
    job that blocks the loop looks "still due" to anything else polling the scheduler meanwhile.
    """
    lock = threading.Lock()
    started_at = [None]
    label = name or getattr(job, "__name__", "job")

    def start():
        if not lock.acquire(blocking=False):
            minutes = (time.monotonic() - started_at[0]) / 60 if started_at[0] else 0
            log(f"[WARN] {label} is still running (started {minutes:.0f} min ago); skipping this run")
            return None
        started_at[0] = time.monotonic()

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


def run_bounded(cmd, timeout, grace=10):
    """Like subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout), except that a
    timeout stops the command *and everything it started*, then raises subprocess.TimeoutExpired.

    The command runs in its own process group (POSIX), so a child it spawned, e.g. download_data.py
    running inject_sampling.py, can't outlive it and keep writing after the scheduler thinks the run
    is over. The group gets SIGTERM first, then SIGKILL after `grace` seconds.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _signal_group(proc.pid, signal.SIGTERM)
        try:
            out, err = proc.communicate(timeout=grace)
        except subprocess.TimeoutExpired:
            _signal_group(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
        _signal_group(proc.pid, signal.SIGKILL)  # anything in the group that ignored SIGTERM
        raise subprocess.TimeoutExpired(cmd, timeout, output=out, stderr=err)
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=out, stderr=err)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass  # the whole group has already exited


def download_status(stdout):
    """The status download_data.py reports on its last `OUTPUT: <status>` line, e.g. "PROCESSED_2_FILES",
    "NO_NEW_FILES", "NO_FILES" or "NO_FILES_PROCESSED". None if it printed no status.

    download_data.py imports every file it downloads itself, so this is a status, never a file path.
    """
    found = re.findall(r"^OUTPUT: (\S+)\s*$", stdout or "", flags=re.MULTILINE)
    return found[-1] if found else None
