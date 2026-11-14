"""Keeps a short Redis outage out of Sentry, and reports one that lasts.

While Redis (the export queue's broker and result store) can't be reached, Celery logs each retry at ERROR level,
every 2 to 30 seconds until it connects again, and Sentry's logging integration sends every ERROR record as an
event. A deploy that recreates the redis container makes a few seconds of such retries, and they used to arrive as
dozens of errors although Celery recovers by itself. So in the processes that load the Celery app (tasks/celery_app.py:
the export worker, and the API, which queues exports), those retry records are logged as warnings instead: still in
docker compose logs, and kept in Sentry only as breadcrumbs. An outage still going after REPORT_AFTER_S is sent once,
as an error. Every other record of these loggers is left as it is.
"""
import logging
import threading
import time

import sentry_sdk

from utils.sentry import scrub_urls

REPORT_AFTER_S = 5 * 60
# Celery retries at most 30 s apart, so retries further apart than this belong to a new outage.
NEW_OUTAGE_AFTER_S = 2 * 60

# The loggers that log Celery's connection retries, and how each retry message starts (Celery 5.x): the worker's
# consumer, the beat scheduler embedded in the export worker, and the Redis result backend.
RETRY_MESSAGES = {
    "celery.worker.consumer.consumer": "consumer: Cannot connect to ",
    "celery.beat": "beat: Connection error: ",
    "celery.backends.redis": "Connection to Redis lost: Retry ",
}
# Logs "Connected to <broker>" each time the worker's consumer has (re)connected, which ends an outage.
CONNECTED_LOGGER = "celery.worker.consumer.connection"
CONNECTED_MESSAGE = "Connected to "

OUTAGE_MESSAGE = (f"Redis (the export queue) has been unreachable for over {REPORT_AFTER_S // 60} min; Celery is "
                  f"still retrying, and exports can't run until it is back")


def is_retry(record):
    """Whether `record` is one of Celery's connection-retry messages."""
    prefix = RETRY_MESSAGES.get(record.name)
    return prefix is not None and isinstance(record.msg, str) and record.msg.startswith(prefix)


def report_outage(record, seconds):
    """Send the one Sentry error for an outage, with the latest retry message (without its "Trying again" line)."""
    last_error = scrub_urls(record.getMessage().strip().splitlines()[0])
    with sentry_sdk.new_scope() as scope:
        scope.set_context("broker", {"last_error": last_error, "unreachable_for_s": round(seconds)})
        sentry_sdk.capture_message(OUTAGE_MESSAGE, level="error")


class BrokerOutageFilter(logging.Filter):
    """A filter for the loggers in RETRY_MESSAGES and CONNECTED_LOGGER: logs retries as warnings, and calls
    `report(record, seconds)` once when an outage reaches REPORT_AFTER_S. A filter on the logger runs before its
    handlers and before Sentry's logging integration sees the record, so both see the lowered level."""

    def __init__(self, report=report_outage, clock=time.monotonic):
        super().__init__()
        self.report, self.clock = report, clock
        self.lock = threading.Lock()
        self.started = self.last = None
        self.reported = False

    def filter(self, record):
        if record.name == CONNECTED_LOGGER:
            if isinstance(record.msg, str) and record.msg.startswith(CONNECTED_MESSAGE):
                with self.lock:
                    self.started = self.last = None
            return True
        if not is_retry(record):
            return True
        record.levelno, record.levelname = logging.WARNING, logging.getLevelName(logging.WARNING)
        now = self.clock()
        with self.lock:
            if self.started is None or now - self.last > NEW_OUTAGE_AFTER_S:
                self.started, self.reported = now, False
            self.last = now
            due = not self.reported and now - self.started >= REPORT_AFTER_S
            if due:
                self.reported = True
            seconds = now - self.started
        if due:
            try:
                self.report(record, seconds)
            except Exception:   # reporting must never stop Celery from logging, or retrying
                logging.getLogger(__name__).exception("reporting the Redis outage failed")
        return True


_installed = []


def install(report=report_outage, clock=time.monotonic):
    """Add one BrokerOutageFilter to the retry loggers and CONNECTED_LOGGER of this process (again: no-op).
    Returns it."""
    if not _installed:
        outage = BrokerOutageFilter(report, clock)
        for name in (*RETRY_MESSAGES, CONNECTED_LOGGER):
            logging.getLogger(name).addFilter(outage)
        _installed.append(outage)
    return _installed[0]
