"""Error reporting to Sentry for the backend processes (API, worker scheduler, export worker).

Errors only, and nothing that identifies a visitor: no performance tracing, no request bodies, cookies,
headers, query strings or IP addresses, and no local variables in stack traces. It is off unless SENTRY_DSN
is set (tests and local development leave it unset), so every function here is then a no-op.

Settings (from the environment, e.g. dashboard/backend/app/.env on the VM):
  SENTRY_DSN          where to send errors; unset or empty turns reporting off
  SENTRY_ENVIRONMENT  e.g. production (default: production)
  SENTRY_COMPONENT    the process's `component` tag; docker-compose.yml sets it for worker and export_worker, so
                      a script run by hand in one of those containers is tagged with it too
  GIT_SHA             optional release name, so an error can be matched to a commit
"""
import os
import re
import subprocess
import threading
import time

import sentry_sdk

# The query string of a URL or a path, which can hold a vendor API key: WQData takes apiKey as a query
# parameter, so a failed request's error message includes it, as a full URL (HTTPError) or as a path
# ("Max retries exceeded with url: /devices/...?apiKey=...", ConnectionError).
_QUERY = re.compile(r"((?:https?://|/)[^\s?#'\"<>]*)\?[^\s#'\"<>]*")

# capture_job_error sends the same failure (job, source and error type) at most this often per process, so an
# outage that fails every 10-minute run doesn't use up the free tier's monthly event quota.
REPEAT_AFTER_S = 60 * 60
_last_sent = {}
_last_sent_lock = threading.Lock()
# Past this many remembered failures, the ones not seen within REPEAT_AFTER_S are forgotten (bounds the memory).
MAX_REMEMBERED = 1000

# How much of a failed subprocess's stderr (often a traceback) and of its stdout ERROR: lines goes with the event.
STDERR_TAIL_CHARS = 2000

# Numbers and hex ids (timestamps, ports, row and job ids), collapsed in failure_signature; an HTTP status is kept.
_NUMBERS = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]*\d[0-9a-f]*\b|\d+", re.IGNORECASE)
_HTTP_STATUS = re.compile(r"[1-5]\d\d")


def init_sentry(component):
    """Start reporting errors for this process, tagged with SENTRY_COMPONENT if it is set, else `component`
    (backend, worker or export_worker). Returns True if reporting is on, False (and does nothing) when
    SENTRY_DSN isn't set.

    The first call in a process wins: the worker and the export worker import server.py (which calls this for
    the API), so they call it first, before those imports, and the later call keeps their component."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    if sentry_sdk.is_initialized():
        return True
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "").strip() or "production",
        release=os.getenv("GIT_SHA", "").strip() or None,
        send_default_pii=False,
        traces_sample_rate=0,           # errors only: no performance tracing
        include_local_variables=False,  # locals can hold rows of data or credentials
        max_request_body_size="never",
        before_send=before_send,
        before_breadcrumb=before_breadcrumb,
    )
    # On the global scope, so every thread and request of this process carries it.
    sentry_sdk.get_global_scope().set_tag("component", os.getenv("SENTRY_COMPONENT", "").strip() or component)
    return True


def capture_job_error(exc, source=None):
    """Report an error that was caught and logged (so it would otherwise never reach Sentry), unless it was
    already reported, or the same failure (this thread's job, `source`, the error type and failure_signature)
    was sent in the last REPEAT_AFTER_S. A failed subprocess's exit code, the end of its stderr and its stdout
    `ERROR:` lines go with it. No-op when reporting is off."""
    if getattr(exc, "already_reported", False) or not sentry_sdk.is_initialized():
        return
    if not _first_in_a_while((threading.current_thread().name, source, type(exc).__name__, failure_signature(exc))):
        return
    with sentry_sdk.new_scope() as scope:
        if source:
            scope.set_tag("source", source)
        if _is_subprocess_error(exc):
            scope.set_context("subprocess", {
                "command": " ".join(map(str, exc.cmd)) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd),
                "exit_code": getattr(exc, "returncode", None),
                "stderr_tail": stderr_tail(exc),
                "error_lines": error_lines(exc),
            })
        sentry_sdk.capture_exception(exc)


def capture_job_warning(message):
    """Report a problem that didn't fail the job (e.g. the backup worked but old dumps weren't deleted) at warning
    level, at most once per REPEAT_AFTER_S for the same message. No-op when reporting is off."""
    if not sentry_sdk.is_initialized():
        return
    if not _first_in_a_while((threading.current_thread().name, "warning", _collapse_numbers(str(message)))):
        return
    sentry_sdk.capture_message(scrub_urls(str(message)), level="warning")


def _is_subprocess_error(exc):
    return isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired))


def _text(value):
    value = value or ""
    return value.decode(errors="replace") if isinstance(value, bytes) else str(value)


def _stderr(exc):
    return _text(getattr(exc, "stderr", None))


def _collapse_numbers(text):
    """`text` with numbers and hex ids replaced by #, except a standalone 100-599 (an HTTP status, which tells
    one failure from another: HTTP 401 and HTTP 503 are different problems)."""
    def replace(match):
        number, start, end = match.group(), match.start(), match.end()
        standalone = (start == 0 or not text[start - 1].isalnum()) and (end == len(text) or not text[end].isalnum())
        return number if standalone and _HTTP_STATUS.fullmatch(number) else "#"
    return _NUMBERS.sub(replace, text)


def failure_signature(exc):
    """What makes one failure the same as another, for the throttle: the first line of the message, with numbers
    and hex ids collapsed so timestamps, ports and ids don't make every repeat look new. For a failed subprocess:
    its arguments (e.g. which month it uploads, kept as they are), its exit code, and its last stderr line, or, when
    stderr is empty, its last stdout line starting with ERROR: or [ERROR] (the scripts print their handled errors
    there)."""
    if _is_subprocess_error(exc):
        lines = [line.strip() for line in _stderr(exc).splitlines() if line.strip()] or error_lines(exc)
        code = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else exc.returncode
        args = " ".join(map(str, exc.cmd[1:])) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        return f"{args} exit {code}: " + _collapse_numbers(scrub_urls(lines[-1]) if lines else "")[:300]
    lines = str(exc).strip().splitlines()
    return _collapse_numbers(lines[0] if lines else "")[:300]


def _tail(text):
    """The last STDERR_TAIL_CHARS of `text`, starting at a whole line when there is more than the cut-off one."""
    if len(text) <= STDERR_TAIL_CHARS:
        return text
    tail = text[-STDERR_TAIL_CHARS:]
    rest = tail.split("\n", 1)[1] if "\n" in tail else ""
    return rest if rest.strip() else tail


def stderr_tail(exc):
    """The end of a failed subprocess's stderr, scrubbed first (so a cut can't fall inside a URL and hide its query
    string from the filter)."""
    return _tail(scrub_urls(_stderr(exc)))


def error_lines(exc):
    """A failed subprocess's stdout lines that start with ERROR: (download_data.py, upload_data.py) or [ERROR]
    (daily_digest.py): the scripts print their handled failures there, e.g. "ERROR: No sensor data found ...".
    Scrubbed, the last STDERR_TAIL_CHARS of them.
    The rest of stdout (progress and data) isn't sent."""
    stdout = _text(getattr(exc, "output", None))
    lines = [line.strip() for line in scrub_urls(stdout).splitlines()
             if line.strip().startswith(("ERROR:", "[ERROR]"))]
    if not lines:
        return []
    kept, size = [], 0
    for line in reversed(lines):
        size += len(line) + 1
        if size > STDERR_TAIL_CHARS and kept:
            break
        kept.append(line[-STDERR_TAIL_CHARS:])
    return kept[::-1]


def scrub_urls(value):
    """`value` with the query string of every URL in it replaced by [Filtered]; strings inside dicts and lists too."""
    if isinstance(value, str):
        return _QUERY.sub(r"\1?[Filtered]", value)
    if isinstance(value, dict):
        return {k: scrub_urls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_urls(v) for v in value]
    return value


def _first_in_a_while(key):
    """Whether `key` wasn't sent in the last REPEAT_AFTER_S; if so, it is remembered as sent now.

    _last_sent holds at most MAX_REMEMBERED keys, in the order they were last sent. Once full, the keys older than
    REPEAT_AFTER_S are forgotten, and if it is still full (a burst of different failures within the hour), the
    longest-sent ones too: such a failure can then be sent again within the hour, which is better than unbounded
    memory."""
    now = time.monotonic()
    with _last_sent_lock:
        if key in _last_sent and now - _last_sent[key] < REPEAT_AFTER_S:
            return False
        _last_sent.pop(key, None)   # re-added below, at the end: the newest
        if len(_last_sent) >= MAX_REMEMBERED:
            for old in [k for k, at in _last_sent.items() if now - at >= REPEAT_AFTER_S]:
                del _last_sent[old]
            while len(_last_sent) >= MAX_REMEMBERED:
                del _last_sent[next(iter(_last_sent))]
        _last_sent[key] = now
    return True


def _unhandled_request_error(event):
    """Whether the event is an error a request raised and nothing caught (reported by Sentry's Flask integration)."""
    values = (event.get("exception") or {}).get("values") or []
    return any((value.get("mechanism") or {}).get("type") == "flask" for value in values)


def before_send(event, hint=None):
    """Strip what could identify a visitor or leak a credential before an event leaves the process, and drop an
    unhandled request error already sent in the last REPEAT_AFTER_S for the same path, type and message: a client
    repeating a request that fails would otherwise send an event per request and use up the monthly quota."""
    exc = ((hint or {}).get("exc_info") or (None, None))[1]
    if exc is not None and _unhandled_request_error(event):
        path = str((event.get("request") or {}).get("url", "")).split("?")[0]
        if not _first_in_a_while(("request", path, type(exc).__name__, failure_signature(exc))):
            return None
    request = event.get("request")
    if request:
        # Keep only the method and the path, which say which endpoint failed.
        event["request"] = {k: request[k] for k in ("method", "url") if k in request}
    user = event.get("user")
    if user:
        user.pop("ip_address", None)
        if not user:
            event.pop("user")
    return scrub_urls(event)


def before_breadcrumb(crumb, hint=None):
    """Breadcrumbs of outgoing HTTP calls carry the query string separately; drop it, and scrub URLs in the rest."""
    data = crumb.get("data")
    if isinstance(data, dict):
        data.pop("http.query", None)
    return scrub_urls(crumb)
