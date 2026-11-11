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

# How much of a failed subprocess's stderr (usually its traceback) goes with the event.
STDERR_TAIL_CHARS = 2000

# Numbers and hex ids (timestamps, ports, row and job ids), collapsed in failure_signature.
_NUMBERS = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]*\d[0-9a-f]*\b|\d+", re.IGNORECASE)


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
    was sent in the last REPEAT_AFTER_S. A failed subprocess's exit code and the end of its stderr go with it.
    No-op when reporting is off."""
    if getattr(exc, "already_reported", False) or not sentry_sdk.is_initialized():
        return
    key = (threading.current_thread().name, source, type(exc).__name__, failure_signature(exc))
    now = time.monotonic()
    with _last_sent_lock:
        if key in _last_sent and now - _last_sent[key] < REPEAT_AFTER_S:
            return
        _last_sent[key] = now
    with sentry_sdk.new_scope() as scope:
        if source:
            scope.set_tag("source", source)
        if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
            scope.set_context("subprocess", {
                "command": " ".join(map(str, exc.cmd)) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd),
                "exit_code": getattr(exc, "returncode", None),
                "stderr_tail": stderr_tail(exc),
            })
        sentry_sdk.capture_exception(exc)


def _stderr(exc):
    stderr = getattr(exc, "stderr", None) or ""
    return stderr.decode(errors="replace") if isinstance(stderr, bytes) else str(stderr)


def failure_signature(exc):
    """What makes one failure the same as another, for the throttle: the first line of the message, or for a failed
    subprocess its exit code and last stderr line (its message names the command, which differs per month), with
    numbers and hex ids collapsed so timestamps, ports and ids don't make every repeat look new."""
    if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        lines = [line for line in _stderr(exc).splitlines() if line.strip()]
        code = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else exc.returncode
        return f"exit {code}: " + _NUMBERS.sub("#", lines[-1].strip() if lines else "")[:300]
    lines = str(exc).strip().splitlines()
    return _NUMBERS.sub("#", lines[0] if lines else "")[:300]


def stderr_tail(exc):
    """The last STDERR_TAIL_CHARS of a failed subprocess's stderr, scrubbed first (so a cut can't fall inside a URL
    and hide its query string from the filter), starting at a whole line."""
    text = scrub_urls(_stderr(exc))
    if len(text) <= STDERR_TAIL_CHARS:
        return text
    tail = text[-STDERR_TAIL_CHARS:]
    return tail.split("\n", 1)[1] if "\n" in tail else tail


def scrub_urls(value):
    """`value` with the query string of every URL in it replaced by [Filtered]; strings inside dicts and lists too."""
    if isinstance(value, str):
        return _QUERY.sub(r"\1?[Filtered]", value)
    if isinstance(value, dict):
        return {k: scrub_urls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_urls(v) for v in value]
    return value


def before_send(event, hint=None):
    """Strip what could identify a visitor or leak a credential before an event leaves the process."""
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
