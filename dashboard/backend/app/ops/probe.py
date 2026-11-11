"""welldash²'s uptime checks and housekeeping, run by a background thread of the ops service.

Once a minute (OPS_PROBE_INTERVAL_S) it requests the dashboard's home page, the backend's /api/latest (which reads
the database), and the WordPress home page (on the wp_probe network, with the public host name, as deploy.sh
does), and records each answer's status and time in uptime_probes. The API check carries a header that
keeps it out of the traffic counts (utils/traffic.py, PROBE_HEADER). Once a day it deletes rows
older than OPS_RETENTION_DAYS (90) from uptime_probes and request_metrics. These are welldash²'s only writes.
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import text

from utils.traffic import PROBE_HEADER

log = logging.getLogger("ops.probe")

PROBE_TIMEOUT = (5, 20)
PRUNE_EVERY = timedelta(days=1)
TARGET_LABELS = {"dashboard": "Dashboard page", "api": "Data API and database", "wordpress": "WordPress site"}

INSERT_SQL = text("INSERT INTO uptime_probes (checked_at, target, ok, status, latency_ms, error) "
                  "VALUES (:checked_at, :target, :ok, :status, :latency_ms, :error)")


def probe_targets(settings):
    """[(name, url, extra headers)] of the enabled checks."""
    targets = []
    if settings.probe_dashboard_url:
        targets.append(("dashboard", settings.probe_dashboard_url, {}))
    if settings.probe_api_url:
        targets.append(("api", settings.probe_api_url, {PROBE_HEADER: "1"}))
    if settings.probe_wordpress_url:
        # WordPress redirects any other host name to its own, so ask for the public one, over "https" as the
        # front proxy does.
        targets.append(("wordpress", settings.probe_wordpress_url,
                        {"Host": settings.probe_wordpress_host, "X-Forwarded-Proto": "https"}))
    return targets


def check(name, url, headers, get=None, clock=time.perf_counter, now=None):
    """One check: a row for uptime_probes. OK means a 2xx answer (redirects are not followed)."""
    checked_at = now or datetime.now(timezone.utc)
    started = clock()
    try:
        response = (get or requests.get)(url, headers={"User-Agent": "welldash2-probe", **headers},
                                         timeout=PROBE_TIMEOUT, allow_redirects=False)
        status, error = response.status_code, None
    except requests.exceptions.RequestException as e:
        status, error = None, type(e).__name__[:64]
    latency = (clock() - started) * 1000
    return {"checked_at": checked_at, "target": name, "ok": status is not None and 200 <= status < 300,
            "status": status, "latency_ms": round(latency, 1), "error": error}


def record(engine, rows):
    with engine.begin() as conn:
        conn.execute(INSERT_SQL, rows)


def prune(engine, retention_days, now=None):
    """Delete rows older than the retention from uptime_probes and request_metrics. {table: rows deleted}."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    deleted = {}
    with engine.begin() as conn:
        for table, column in (("uptime_probes", "checked_at"), ("request_metrics", "minute")):
            # Fixed table and column names; only the cutoff is a parameter.
            deleted[table] = conn.execute(text(f"DELETE FROM {table} WHERE {column} < :cutoff"),
                                          {"cutoff": cutoff}).rowcount
    return deleted


def run_once(engine, settings, get=None, now=None):
    rows = [check(name, url, headers, get=get, now=now) for name, url, headers in probe_targets(settings)]
    if rows:
        record(engine, rows)
    return rows


class Prober:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.last_prune = None
        self.last_run = None
        self.failures = 0

    def tick(self):
        try:
            run_once(self.engine, self.settings)
            self.last_run = datetime.now(timezone.utc)
            self.failures = 0
        except Exception as e:   # the type only: a connection error's text can include the database URL
            self.failures += 1
            if self.failures in (1, 10) or self.failures % 60 == 0:
                log.warning("uptime check not recorded (%s; failure %d)", type(e).__name__, self.failures)
        now = datetime.now(timezone.utc)
        if self.last_prune is None or now - self.last_prune >= PRUNE_EVERY:
            try:
                deleted = prune(self.engine, self.settings.retention_days, now)
                log.info("pruned rows older than %d days: %s", self.settings.retention_days, deleted)
                self.last_prune = now
            except Exception as e:
                log.warning("pruning failed (%s); retrying in an hour", type(e).__name__)
                self.last_prune = now - PRUNE_EVERY + timedelta(hours=1)

    def run(self):
        interval = self.settings.probe_interval_s
        while True:
            started = time.monotonic()
            self.tick()
            time.sleep(max(1.0, interval - (time.monotonic() - started)))

    def start(self):
        if self.settings.probe_interval_s <= 0:
            log.info("uptime checks are off (OPS_PROBE_INTERVAL_S=0)")
            return None
        thread = threading.Thread(target=self.run, name="uptime-probe", daemon=True)
        thread.start()
        return thread
