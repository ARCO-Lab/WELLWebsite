"""Request metrics: per-minute counts of the API's traffic, for welldash² (the ops service, ops/) and the daily digest.

The backend counts every request it answers in memory, per (minute, route, method, status class): how many, their
total and longest time, a small latency histogram and the bytes sent. A background thread in each gunicorn worker
writes the finished minutes to the request_metrics table about every 15 s, adding to any row another worker wrote
for the same key (db/migrations/0005_ops_metrics.sql). Only the route pattern is kept ("/api/exports/jobs/<job_id>",
never the id, the query string, the client's address or its user agent), so the table holds no personal data.

Counting is on by default when the database is PostgreSQL; REQUEST_METRICS=0 turns it off. A failed write is
logged and the minutes dropped, so a missing table (migration not applied yet) never breaks a request. Counts
still in memory when a worker is killed outright (not stopped) are lost, at most about a minute's worth.
"""
import atexit
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# Upper bounds (ms) of the latency histogram's buckets; one more bucket holds anything slower than the last.
LATENCY_BUCKETS_MS = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000)
BUCKETS = len(LATENCY_BUCKETS_MS) + 1
# Requests that hand the visitor a CSV file: the small synchronous export and a finished export job's file.
DOWNLOAD_ENDPOINTS = ("/api/exports/sync", "/api/exports/jobs/<job_id>/download")
NO_ROUTE = "(no route)"     # a path no route matches (404/405): the path itself isn't kept
FLUSH_EVERY_S = 15
MAX_KEYS = 20000            # a flush that keeps failing must not grow memory without end


def bucket_index(ms):
    for i, bound in enumerate(LATENCY_BUCKETS_MS):
        if ms <= bound:
            return i
    return BUCKETS - 1


def percentile_ms(buckets, q=0.95, max_ms=None):
    """An estimate of the q-th latency percentile from histogram counts, interpolated linearly inside the bucket it
    falls in, and never more than the slowest request when max_ms is given. None when there are no requests."""
    total = sum(buckets or ())
    if not total:
        return None
    need, seen = q * total, 0
    for i, count in enumerate(buckets):
        if count and seen + count >= need:
            low = LATENCY_BUCKETS_MS[i - 1] if i > 0 else 0
            high = LATENCY_BUCKETS_MS[i] if i < len(LATENCY_BUCKETS_MS) else max_ms
            if high is None:   # the open-ended last bucket, without a known maximum
                return float(low)
            estimate = low + (high - low) * (need - seen) / count
            return min(estimate, max_ms) if max_ms is not None else estimate
        seen += count
    return max_ms


def minute_of(ts):
    return ts.replace(second=0, microsecond=0)


class RequestAggregator:
    """Thread-safe per-minute totals of one process's requests, until they are taken to be written."""

    def __init__(self):
        self.lock = threading.Lock()
        self.rows = {}

    def record(self, when, endpoint, method, status, ms, nbytes):
        key = (minute_of(when), endpoint, method, int(status) // 100)
        with self.lock:
            row = self.rows.get(key)
            if row is None:
                if len(self.rows) >= MAX_KEYS:
                    return
                row = self.rows[key] = {"requests": 0, "total_ms": 0.0, "max_ms": 0.0,
                                        "buckets": [0] * BUCKETS, "bytes_out": 0}
            row["requests"] += 1
            row["total_ms"] += ms
            row["max_ms"] = max(row["max_ms"], ms)
            row["buckets"][bucket_index(ms)] += 1
            row["bytes_out"] += max(int(nbytes or 0), 0)

    def take(self, before=None):
        """Remove and return the rows of minutes before `before` (all rows when None), as dicts for UPSERT_SQL."""
        with self.lock:
            keys = [k for k in self.rows if before is None or k[0] < before]
            taken = [(k, self.rows.pop(k)) for k in keys]
        return [{"minute": k[0], "endpoint": k[1], "method": k[2], "status_class": k[3], **v,
                 "buckets": list(v["buckets"])} for k, v in taken]


# Adds to the row another worker (or an earlier flush) wrote for the same minute and key. The histograms are added
# element by element.
UPSERT_SQL = """
INSERT INTO request_metrics (minute, endpoint, method, status_class, requests, total_ms, max_ms, latency_buckets,
                             bytes_out)
VALUES (:minute, :endpoint, :method, :status_class, :requests, :total_ms, :max_ms, :buckets, :bytes_out)
ON CONFLICT (minute, endpoint, method, status_class) DO UPDATE SET
    requests = request_metrics.requests + EXCLUDED.requests,
    total_ms = request_metrics.total_ms + EXCLUDED.total_ms,
    max_ms = GREATEST(request_metrics.max_ms, EXCLUDED.max_ms),
    latency_buckets = ARRAY(SELECT a + b FROM unnest(request_metrics.latency_buckets, EXCLUDED.latency_buckets)
                            WITH ORDINALITY AS t(a, b, i) ORDER BY i),
    bytes_out = request_metrics.bytes_out + EXCLUDED.bytes_out
"""


def write_rows(engine, rows):
    if not rows:
        return 0
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(UPSERT_SQL), rows)
    return len(rows)


class MetricsRecorder:
    """Hooks a Flask app's requests into an aggregator and writes it out from a daemon thread."""

    def __init__(self, app, aggregator=None, engine=None, clock=None):
        self.app = app
        self.aggregator = aggregator or RequestAggregator()
        self.engine = engine
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.thread_pid = None
        self.thread_lock = threading.Lock()
        self.failures = 0

    def install(self):
        from flask import g, request

        @self.app.before_request
        def start_timer():
            g._metrics_started = time.perf_counter()

        @self.app.after_request
        def count_request(response):
            try:
                started = g.pop("_metrics_started", None)
                if started is not None:
                    ms = (time.perf_counter() - started) * 1000
                    rule = request.url_rule.rule if request.url_rule is not None else NO_ROUTE
                    self.aggregator.record(self.clock(), rule, request.method[:8], response.status_code, ms,
                                           response.content_length)
                    self.ensure_thread()
            except Exception:   # counting must never break a response
                log.exception("request metrics: couldn't count a request")
            return response

        atexit.register(self.flush_all)
        return self

    def get_engine(self):
        if self.engine is not None:
            return self.engine
        from db.database import db
        with self.app.app_context():
            return db.engine

    def flush(self, everything=False):
        before = None if everything else minute_of(self.clock())
        rows = self.aggregator.take(before)
        if not rows:
            return 0
        try:
            return write_rows(self.get_engine(), rows)
        except Exception as e:   # the type only: a connection error's text can include the database URL
            self.failures += 1
            if self.failures in (1, 10) or self.failures % 100 == 0:
                log.warning("request metrics: couldn't write %d rows (%s; failure %d); dropped them",
                            len(rows), type(e).__name__, self.failures)
            return 0

    def flush_all(self):
        self.flush(everything=True)

    def ensure_thread(self):
        """One writer thread per process, started on its first request (gunicorn forks the workers after import)."""
        if self.thread_pid == os.getpid():
            return
        with self.thread_lock:
            if self.thread_pid == os.getpid():
                return
            self.thread_pid = os.getpid()
            threading.Thread(target=self.run, name="request-metrics", daemon=True).start()

    def run(self):
        while True:
            time.sleep(FLUSH_EVERY_S)
            self.flush()


def metrics_enabled(uri, env=None):
    env = os.environ if env is None else env
    off = (env.get("REQUEST_METRICS") or "").strip().lower() in ("0", "false", "no", "off")
    return not off and (uri or "").startswith("postgresql")


def init_request_metrics(app, env=None):
    """Count the app's requests when enabled (see the module docstring). Returns the recorder, or None."""
    if not metrics_enabled(app.config.get("SQLALCHEMY_DATABASE_URI"), env):
        return None
    recorder = app.extensions["request_metrics"] = MetricsRecorder(app).install()
    return recorder


# --- Reading the table back: shared by the ops service and the daily digest -------------------------------------

def summarize_traffic(execute, start, end):
    """Totals of request_metrics for minutes in [start, end) (aware datetimes). `execute(sql, params)` returns rows
    with attribute access (a SQLAlchemy connection's execute, or a session's). The SQL is fixed; only the two
    times are parameters.

    {"requests", "errors_4xx", "errors_5xx", "bytes_out", "p95_ms", "max_ms", "downloads",
     "peak_per_minute", "peak_minute", "endpoints": [{"endpoint", "requests", "errors_5xx", "avg_ms", "max_ms",
     "bytes_out"}]}"""
    params = {"start": start, "end": end}
    rows = execute("""
        SELECT endpoint, method, status_class, sum(requests) AS requests, sum(total_ms) AS total_ms,
               max(max_ms) AS max_ms, sum(bytes_out) AS bytes_out
        FROM request_metrics WHERE minute >= :start AND minute < :end
        GROUP BY endpoint, method, status_class""", params)
    totals = {"requests": 0, "errors_4xx": 0, "errors_5xx": 0, "bytes_out": 0, "max_ms": None, "downloads": 0}
    endpoints = {}
    for r in rows:
        n = int(r.requests or 0)
        totals["requests"] += n
        totals["bytes_out"] += int(r.bytes_out or 0)
        if r.status_class == 4:
            totals["errors_4xx"] += n
        if r.status_class == 5:
            totals["errors_5xx"] += n
        if r.endpoint in DOWNLOAD_ENDPOINTS and r.status_class == 2:
            totals["downloads"] += n
        if r.max_ms is not None:
            totals["max_ms"] = max(totals["max_ms"] or 0, float(r.max_ms))
        e = endpoints.setdefault((r.endpoint, r.method), {"endpoint": r.endpoint, "method": r.method, "requests": 0,
                                                          "errors_5xx": 0, "total_ms": 0.0, "max_ms": 0.0,
                                                          "bytes_out": 0})
        e["requests"] += n
        e["errors_5xx"] += n if r.status_class == 5 else 0
        e["total_ms"] += float(r.total_ms or 0)
        e["max_ms"] = max(e["max_ms"], float(r.max_ms or 0))
        e["bytes_out"] += int(r.bytes_out or 0)
    for e in endpoints.values():
        e["avg_ms"] = e.pop("total_ms") / e["requests"] if e["requests"] else None
    buckets = [0] * BUCKETS
    for r in execute("""
            SELECT u.i AS i, sum(u.b) AS n
            FROM request_metrics m, unnest(m.latency_buckets) WITH ORDINALITY AS u(b, i)
            WHERE m.minute >= :start AND m.minute < :end GROUP BY u.i""", params):
        if 1 <= r.i <= BUCKETS:
            buckets[r.i - 1] = int(r.n or 0)
    totals["p95_ms"] = percentile_ms(buckets, 0.95, totals["max_ms"])
    peak = list(execute("""
        SELECT minute, sum(requests) AS n FROM request_metrics WHERE minute >= :start AND minute < :end
        GROUP BY minute ORDER BY n DESC, minute LIMIT 1""", params))
    totals["peak_per_minute"] = int(peak[0].n) if peak else 0
    totals["peak_minute"] = peak[0].minute if peak else None
    totals["endpoints"] = sorted(endpoints.values(), key=lambda e: (-e["requests"], e["endpoint"], e["method"]))
    return totals


def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def traffic_lines(summary, site_tz):
    """The daily digest's "Traffic yesterday" lines for summarize_traffic()'s result, or {"error": ...}."""
    lines = ["Traffic yesterday (data API, all visitors; welldash² has charts):"]
    if summary.get("error"):
        return lines + [f"  could not be read: {summary['error']}"]
    if not summary["requests"]:
        return lines + ["  no requests recorded (is the request_metrics migration applied?)"]
    p95 = summary["p95_ms"]
    lines += [
        f"  requests: {summary['requests']}, errors: {summary['errors_5xx']} server (5xx), "
        f"{summary['errors_4xx']} client (4xx)",
        f"  p95 response time: {'about ' + str(round(p95)) + ' ms' if p95 is not None else 'n/a'}; "
        f"slowest {summary['max_ms']:.0f} ms",
        f"  data sent: {fmt_bytes(summary['bytes_out'])}; CSV downloads: {summary['downloads']}",
    ]
    if summary["peak_minute"] is not None:
        lines.append(f"  busiest minute: {summary['peak_per_minute']} requests at "
                     f"{summary['peak_minute'].astimezone(site_tz):%H:%M}")
    return lines


def yesterday_window(now, site_tz):
    """[start, end) of the previous calendar day in site time, as aware datetimes."""
    today = now.astimezone(site_tz).date()
    yesterday = today - timedelta(days=1)
    # Built from dates, so both ends are midnight even when the day had 23 or 25 hours (a DST change).
    return (datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=site_tz),
            datetime(today.year, today.month, today.day, tzinfo=site_tz))
