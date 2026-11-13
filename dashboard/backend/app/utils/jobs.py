"""Helpers for the worker's scheduler (scripts/scheduler_temp.py). Pure: no database or vendor settings."""
import json
import os
import re
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta

import sentry_sdk

from utils.sentry import capture_job_error


def run_in_background(job, log=print, name=None, on_skip=None):
    """Wrap `job` so each call starts it in its own thread and returns at once.

    If the previous run of the same job is still going, the call is skipped and logged instead,
    so a slow run can never overlap the next one. The skip message says how long the run has been
    going, so a hung job shows up in the log; jobs must bound their own I/O (request and subprocess
    timeouts), since a run that never returns keeps the lock. Returning at once matters too: the
    `schedule` library only moves a job's next run time after the scheduled callable returns, so a
    job that blocks the loop looks "still due" to anything else polling the scheduler meanwhile.
    `on_skip(skips, message)`, if given, is called after each skip with the number of runs skipped in a row (back
    to 0 once a run starts), so the scheduler can report a job that stays stuck (scripts/scheduler_temp.py).
    """
    lock = threading.Lock()
    started_at = [None]
    skipped = [0]
    label = name or getattr(job, "__name__", "job")

    def start():
        if not lock.acquire(blocking=False):
            minutes = (time.monotonic() - started_at[0]) / 60 if started_at[0] else 0
            skipped[0] += 1
            message = f"{label} is still running (started {minutes:.0f} min ago); skipping this run"
            log(f"[WARN] {message}")
            if on_skip:
                try:
                    on_skip(skipped[0], message)
                except Exception as e:   # reporting a skip must never stop the scheduler loop
                    log(f"[ERROR] reporting the skipped {label} run failed: {e}")
            return None
        started_at[0] = time.monotonic()
        skipped[0] = 0

        def target():
            # Errors reported to Sentry during this run (utils/sentry.py; a no-op when it is off) carry the job name.
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("job", label)
                try:
                    job()
                except Exception as e:  # never let a failed run leave the lock held
                    log(f"[ERROR] {label} failed: {e}")
                    capture_job_error(e)
                finally:
                    lock.release()

        thread = threading.Thread(target=target, name=label, daemon=True)
        thread.start()
        return thread

    start.__name__ = f"run_{label}"
    start.is_running = lock.locked   # read by the scheduler's shutdown, to wait for the job to finish
    return start


def run_bounded(cmd, timeout, grace=10):
    """Like subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout), except that a
    timeout stops the command *and everything it started*, then raises subprocess.TimeoutExpired.

    The command runs in its own process group (POSIX), so a child it spawned, e.g. download_data.py
    running inject_sampling.py, can't outlive it and keep writing after the scheduler thinks the run
    is over. The group gets SIGTERM first, then SIGKILL after `grace` seconds.

    The command runs with SENTRY_DSN empty (empty, not unset, so load_dotenv can't fill it in from a .env), so
    it never reports to Sentry itself: the scheduler reports a failed run once, with its exit code and the end of
    its stderr (utils/sentry.capture_job_error). Otherwise a crash in, say, upload_data.py would arrive twice,
    as its own traceback and as the scheduler's CalledProcessError.
    """
    env = {**os.environ, "SENTRY_DSN": ""}
    with _groups_lock:
        if _stopping.is_set():   # the worker is shutting down (stop_subprocesses): start nothing new
            raise RuntimeError(f"not running {' '.join(map(str, cmd))}: the worker is shutting down")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True, env=env)
        _groups.add(proc.pid)
    try:
        return _wait_bounded(proc, cmd, timeout, grace)
    finally:
        with _groups_lock:
            _groups.discard(proc.pid)


def _wait_bounded(proc, cmd, timeout, grace):
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


# Process groups of the commands run_bounded is running now, so a worker that is stopping can end them
_groups = set()
_groups_lock = threading.Lock()
_stopping = threading.Event()


def stop_subprocesses(grace=10):
    """For a worker that is shutting down: refuse new run_bounded commands, send SIGTERM to the process group of
    each one running now, and SIGKILL any group still there after `grace` seconds. The jobs that ran them see
    them fail (CalledProcessError with exit code -15) and log it. Returns how many groups were signalled."""
    with _groups_lock:
        _stopping.set()
        groups = list(_groups)
    for pgid in groups:
        _signal_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        with _groups_lock:
            if not _groups:
                break
        time.sleep(0.2)
    with _groups_lock:
        left = list(_groups)
    for pgid in left:
        _signal_group(pgid, signal.SIGKILL)
    return len(groups)


def _signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass  # the whole group has already exited


def download_status(stdout):
    """The status download_data.py reports on its last `OUTPUT: <status>` line, e.g. "PROCESSED_2_FILES",
    "NO_NEW_FILES", "NO_FILES", "NO_FILES_PROCESSED", or REJECTED_<n>_FILES / FAILED_<n>_FILES (then it exits 1).
    None if it printed no status.

    download_data.py imports every file it downloads itself, so this is a status, never a file path.
    """
    found = re.findall(r"^OUTPUT: (\S+)\s*$", stdout or "", flags=re.MULTILINE)
    return found[-1] if found else None


def previous_month(now):
    """(year, month) of the month before `now`'s month."""
    return (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)


# The hour (site time) the monthly Borealis upload runs in: after midnight, once the month's last readings are in.
UPLOAD_HOUR = 2


def months_due_for_upload(now, uploaded, first_month):
    """The (year, month) pairs the Borealis upload should send now, oldest first.

    That is every month from `first_month` (a (year, month) pair) through the month before `now` that isn't in
    `uploaded` (keys like "2026-10"). So a month that keeps failing is tried again each day, even after later
    months have ended, and it doesn't hold them up; months before `first_month` are never sent. `now` is site
    time (America/Toronto), the same wall clock recorded_at is stored in, so a month counts as over only once
    it has ended there. Empty outside UPLOAD_HOUR.
    """
    if now.hour != UPLOAD_HOUR:
        return []
    due, (year, month), last = [], first_month, previous_month(now)
    while (year, month) <= last:
        if month_key(year, month) not in uploaded:
            due.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return due


def month_key(year, month):
    return f"{year:04d}-{month:02d}"


def parse_month_key(text):
    """(year, month) from "YYYY-MM"; ValueError if it isn't one."""
    match = re.fullmatch(r"(\d{4})-(\d{2})", (text or "").strip())
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise ValueError(f"expected a month like 2026-10, got {text!r}")
    return int(match.group(1)), int(match.group(2))


def load_uploaded_months(path):
    """The months recorded in `path` as uploaded; empty if the file doesn't exist yet.

    A file that can't be read raises instead of counting as empty, so a damaged record can't cause every
    month to be uploaded again.
    """
    try:
        with open(path) as f:
            return set(json.load(f).get("uploaded_months", []))
    except FileNotFoundError:
        return set()


def record_uploaded_month(path, year, month):
    """Add (year, month) to the record in `path`, written atomically so a crash can't leave half a file."""
    months = load_uploaded_months(path) | {month_key(year, month)}
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump({"uploaded_months": sorted(months)}, f, indent=2)
    os.replace(tmp, path)


# download_data.py's ATTENTION: lines (sampling rows a newer file no longer has, corrections held back), kept for the
# daily digest, which lists those of its 24 h; with the logs, so they survive a worker restart.
ATTENTION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs",
                              "sampling_attention.json")
ATTENTION_KEEP = timedelta(days=14)


def load_attention(path=ATTENTION_PATH):
    """The recorded ATTENTION: lines, [{"at": aware ISO time, "text": the line without "ATTENTION: "}], oldest first;
    empty if none were recorded. A damaged file raises ValueError."""
    try:
        with open(path) as f:
            entries = json.load(f)
    except FileNotFoundError:
        return []
    if not isinstance(entries, list) or not all(isinstance(e, dict) and "at" in e and "text" in e for e in entries):
        raise ValueError(f"{path} isn't a list of ATTENTION: entries")
    return entries


def record_attention(lines, now, path=ATTENTION_PATH):
    """Add the ATTENTION: lines among `lines` to `path` with the time `now` (aware), dropping entries older than
    ATTENTION_KEEP; written atomically. A damaged file is replaced (its lines were in the log and Sentry already).
    Returns how many were added. Raises OSError if it can't be written."""
    new = [{"at": now.isoformat(timespec="seconds"), "text": line[len("ATTENTION:"):].strip()}
           for line in lines if line.startswith("ATTENTION:")]
    if not new:
        return 0
    try:
        kept = [e for e in load_attention(path) if datetime.fromisoformat(e["at"]) >= now - ATTENTION_KEEP]
    except ValueError:
        kept = []
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(kept + new, f, indent=2)
    os.replace(tmp, path)
    return len(new)


def recent_attention(since, path=ATTENTION_PATH):
    """The ATTENTION: entries recorded since `since` (aware), oldest first."""
    return [e for e in load_attention(path) if datetime.fromisoformat(e["at"]) >= since]
