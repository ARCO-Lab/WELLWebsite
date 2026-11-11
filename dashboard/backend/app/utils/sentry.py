"""Error reporting to Sentry for the backend processes (API, worker scheduler, export worker).

Errors only, and nothing that identifies a visitor: no performance tracing, no request bodies, cookies,
headers, query strings or IP addresses, and no local variables in stack traces. It is off unless SENTRY_DSN
is set (tests and local development leave it unset), so every function here is then a no-op.

Settings (from the environment, e.g. dashboard/backend/app/.env on the VM):
  SENTRY_DSN          where to send errors; unset or empty turns reporting off
  SENTRY_ENVIRONMENT  e.g. production (default: production)
  GIT_SHA             optional release name, so an error can be matched to a commit
"""
import os
import re

import sentry_sdk

# A URL's query string, which can hold a vendor API key (WQData takes apiKey as a query parameter, so a
# failed request's error message includes it).
_QUERY = re.compile(r"(https?://[^\s?#'\"<>]+)\?[^\s#'\"<>]*")


def init_sentry(component):
    """Start reporting errors for this process, tagged with `component` (backend, worker or export_worker).
    Returns True if reporting is on, False (and does nothing) when SENTRY_DSN isn't set.

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
    sentry_sdk.get_global_scope().set_tag("component", component)
    return True


def capture_job_error(exc):
    """Report an error that was caught and logged (so it would otherwise never reach Sentry), unless it was
    already reported. No-op when reporting is off."""
    if not getattr(exc, "already_reported", False):
        sentry_sdk.capture_exception(exc)


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
