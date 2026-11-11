"""welldash²'s database reads. Every page reads in a READ ONLY transaction (PostgreSQL then refuses any write in
it, whatever the role may do), and no value from a request reaches the SQL: the period is picked from RANGES by
name, and only fixed SQL with bound times runs. Each section is read on its own, so a missing table (a migration
not applied yet) shows as an error in that section instead of breaking the page."""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from api.routes.latest import LATEST_PER_SERIES_SQL
from utils.monitoring import assess_freshness
from utils.timezone import EST_TZ
from utils.traffic import BUCKETS, DOWNLOAD_ENDPOINTS, percentile_ms, summarize_traffic

log = logging.getLogger("ops.data")

# name -> (period, chart bucket for uptime latency, chart bucket for traffic)
RANGES = {
    "24h": (timedelta(hours=24), timedelta(minutes=5), timedelta(hours=1)),
    "7d": (timedelta(days=7), timedelta(hours=1), timedelta(hours=6)),
    "30d": (timedelta(days=30), timedelta(hours=6), timedelta(days=1)),
}
DEFAULT_RANGE = "24h"
DEPLOY_LOG_TAIL_BYTES = 64 * 1024


def pick_range(name):
    return name if name in RANGES else DEFAULT_RANGE


@contextmanager
def reading(engine):
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION READ ONLY"))
        try:
            yield conn
        finally:
            conn.rollback()


def section(engine, fn, *args):
    """fn(conn, *args) in its own read-only transaction; {"error": type} if it fails."""
    try:
        with reading(engine) as conn:
            return fn(conn, *args)
    except Exception as e:   # the type only: a connection error's text can include the database URL
        log.warning("%s failed: %s", fn.__name__, type(e).__name__)
        return {"error": type(e).__name__}


def bucket_sql(column):
    """SQL for the start of the `:step`-second bucket a timestamptz column falls in (PostgreSQL 13 has no
    date_bin). Buckets are aligned to the Unix epoch, so 1-day buckets start at midnight UTC."""
    return f"to_timestamp(floor(extract(epoch FROM {column}) / :step) * :step)"


def aware(ts):
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


# --- Overview -------------------------------------------------------------------------------------------------

def latest_probes(conn):
    rows = conn.execute(text(
        "SELECT DISTINCT ON (target) target, checked_at, ok, status, latency_ms, error FROM uptime_probes "
        "ORDER BY target, checked_at DESC")).mappings().all()
    return {"probes": [dict(r) for r in rows]}


def freshness(conn, now):
    rows = [{"station_id": r.station_id, "group_type": r.group_type, "measurement_type": r.measurement_type,
             "recorded_at": r.recorded_at.isoformat()} for r in conn.execute(LATEST_PER_SERIES_SQL)]
    return assess_freshness(rows, now)


def alerts(conn, now):
    open_rows = conn.execute(text(
        "SELECT kind, title, started_at, last_notified_at, notifications FROM alert_incidents "
        "WHERE resolved_at IS NULL ORDER BY started_at")).mappings().all()
    closed = conn.execute(text(
        "SELECT kind, title, started_at, resolved_at FROM alert_incidents "
        "WHERE resolved_at >= :since ORDER BY resolved_at DESC LIMIT 10"),
        {"since": now - timedelta(days=7)}).mappings().all()
    return {"open": [dict(r) for r in open_rows], "closed": [dict(r) for r in closed]}


def vendors(conn):
    rows = conn.execute(text(
        "SELECT source, last_attempt_at, last_success_at, failing_since, consecutive_failures, last_error_kind, "
        "last_http_status, last_error FROM vendor_status ORDER BY source")).mappings().all()
    return {"vendors": [dict(r) for r in rows]}


def deploys(logs_dir, limit=10):
    """The newest deploy.sh outcomes from deploy.log in the logs folder, if deploy.sh writes it there."""
    path = os.path.join(logs_dir, "deploy.log")
    if not os.path.isfile(path):
        return {"missing": True}
    try:
        with open(path, "rb") as f:
            f.seek(max(os.path.getsize(path) - DEPLOY_LOG_TAIL_BYTES, 0))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError as e:
        return {"error": type(e).__name__}
    keep = ("deployed", "deploying", "rolling back", "rolled back", "FAILED", "HELD")
    found = [line for line in lines if line[:4].isdigit() and any(k in line for k in keep)]
    entries = []
    for line in reversed(found[-limit:]):
        when, _, message = line[:19], line[19:20], line[20:]
        kind = ("bad" if "FAILED" in message or "rolling back" in message else
                "warn" if "HELD" in message else "ok")
        entries.append({"when": when, "message": message[:240], "kind": kind})
    return {"entries": entries}


# --- Uptime ---------------------------------------------------------------------------------------------------

def availability(conn, now):
    rows = conn.execute(text("""
        SELECT target,
               count(*) FILTER (WHERE checked_at >= :d1) AS n1, count(*) FILTER (WHERE ok AND checked_at >= :d1) AS ok1,
               count(*) FILTER (WHERE checked_at >= :d7) AS n7, count(*) FILTER (WHERE ok AND checked_at >= :d7) AS ok7,
               count(*) AS n30, count(*) FILTER (WHERE ok) AS ok30,
               max(checked_at) AS last
        FROM uptime_probes WHERE checked_at >= :d30 GROUP BY target ORDER BY target"""),
        {"d1": now - timedelta(days=1), "d7": now - timedelta(days=7), "d30": now - timedelta(days=30)}).mappings()
    result = []
    for r in rows:
        pct = lambda ok, n: 100.0 * ok / n if n else None   # noqa: E731
        result.append({"target": r["target"], "last": r["last"], "day": pct(r["ok1"], r["n1"]),
                       "week": pct(r["ok7"], r["n7"]), "month": pct(r["ok30"], r["n30"]),
                       "checks_day": r["n1"]})
    return {"targets": result}


def latency_series(conn, now, range_name):
    period, step, _ = RANGES[range_name]
    rows = conn.execute(text(f"""
        SELECT target, {bucket_sql('checked_at')} AS t, avg(latency_ms) FILTER (WHERE ok) AS avg_ms,
               count(*) AS n, count(*) FILTER (WHERE ok) AS ok
        FROM uptime_probes WHERE checked_at >= :since GROUP BY 1, 2 ORDER BY 2"""),
        {"since": now - period, "step": int(step.total_seconds())}).mappings()
    series = {}
    for r in rows:
        series.setdefault(r["target"], []).append((aware(r["t"]), r["avg_ms"], r["n"], r["ok"]))
    return {"series": series, "start": now - period, "end": now, "step": step}


def incidents(conn, now, limit=50):
    """Downtime: runs of failed checks of a target, merged when no successful check came between them."""
    rows = conn.execute(text(
        "SELECT target, checked_at, ok, status, error FROM uptime_probes WHERE checked_at >= :since "
        "AND target IN (SELECT DISTINCT target FROM uptime_probes WHERE NOT ok AND checked_at >= :since) "
        "ORDER BY target, checked_at"), {"since": now - timedelta(days=30)}).mappings()
    found, current = [], {}
    for r in rows:
        open_one = current.get(r["target"])
        if not r["ok"]:
            if open_one is None:
                open_one = current[r["target"]] = {"target": r["target"], "start": r["checked_at"],
                                                   "end": None, "checks": 0, "reasons": set()}
            open_one["checks"] += 1
            open_one["last_failed"] = r["checked_at"]
            open_one["reasons"].add(f"HTTP {r['status']}" if r["status"] is not None else (r["error"] or "no answer"))
        elif open_one is not None:
            open_one["end"] = r["checked_at"]
            found.append(current.pop(r["target"]))
    found += current.values()   # still failing
    for i in found:
        until = i["end"] or now
        i["minutes"] = max(int((until - i["start"]).total_seconds() // 60), 1)
        i["reasons"] = ", ".join(sorted(i["reasons"]))
    found.sort(key=lambda i: i["start"], reverse=True)
    return {"incidents": found[:limit]}


# --- Traffic --------------------------------------------------------------------------------------------------

def traffic_summary(conn, now, range_name):
    period = RANGES[range_name][0]
    return summarize_traffic(lambda sql, params: conn.execute(text(sql), params), now - period, now)


def traffic_series(conn, now, range_name):
    period, _, step = RANGES[range_name]
    params = {"since": now - period, "step": int(step.total_seconds()), "downloads": list(DOWNLOAD_ENDPOINTS)}
    rows = conn.execute(text(f"""
        SELECT {bucket_sql('minute')} AS t, sum(requests) AS requests,
               coalesce(sum(requests) FILTER (WHERE status_class = 5), 0) AS errors,
               coalesce(sum(requests) FILTER (WHERE status_class = 2 AND endpoint = ANY(:downloads)), 0) AS downloads,
               sum(bytes_out) AS bytes_out, max(max_ms) AS max_ms
        FROM request_metrics WHERE minute >= :since GROUP BY 1 ORDER BY 1"""), params).mappings().all()
    peaks = {aware(r["t"]): int(r["peak"]) for r in conn.execute(text(f"""
        SELECT {bucket_sql('minute')} AS t, max(n) AS peak FROM (
            SELECT minute, sum(requests) AS n FROM request_metrics WHERE minute >= :since GROUP BY minute) m
        GROUP BY 1"""), params).mappings()}
    hist = {}
    for r in conn.execute(text(f"""
            SELECT {bucket_sql('m.minute')} AS t, u.i AS i, sum(u.b) AS n
            FROM request_metrics m, unnest(m.latency_buckets) WITH ORDINALITY AS u(b, i)
            WHERE m.minute >= :since GROUP BY 1, 2"""), params).mappings():
        buckets = hist.setdefault(aware(r["t"]), [0] * BUCKETS)
        if 1 <= r["i"] <= BUCKETS:
            buckets[r["i"] - 1] = int(r["n"] or 0)
    points = []
    for r in rows:
        t = aware(r["t"])
        points.append({"t": t, "requests": int(r["requests"] or 0), "errors": int(r["errors"]),
                       "downloads": int(r["downloads"]), "bytes_out": int(r["bytes_out"] or 0),
                       "p95_ms": percentile_ms(hist.get(t, []), 0.95, r["max_ms"]), "peak": peaks.get(t, 0)})
    return {"points": points, "start": now - period, "end": now, "step": step}


def export_jobs(conn, now, range_name):
    """Export jobs created in the period (export_jobs times are naive site time), and the queue now."""
    since = (now - RANGES[range_name][0]).astimezone(EST_TZ).replace(tzinfo=None)
    by_status = conn.execute(text("""
        SELECT status, count(*) AS jobs, coalesce(sum(produced_rows), 0) AS rows,
               avg(extract(epoch FROM completed_at - started_at)) AS avg_s,
               max(extract(epoch FROM completed_at - started_at)) AS max_s
        FROM export_jobs WHERE created_at >= :since GROUP BY status ORDER BY status"""), {"since": since}).mappings().all()
    queue = conn.execute(text(
        "SELECT count(*) FILTER (WHERE status = 'queued') AS queued, count(*) FILTER (WHERE status = 'running') AS running "
        "FROM export_jobs")).mappings().one()
    failures = conn.execute(text("""
        SELECT created_at, domain, estimated_rows, left(coalesce(error_message, ''), 200) AS error
        FROM export_jobs WHERE status = 'failed' AND created_at >= :since ORDER BY created_at DESC LIMIT 10"""),
        {"since": since}).mappings().all()
    return {"by_status": [dict(r) for r in by_status], "queued": queue["queued"], "running": queue["running"],
            "failures": [dict(r) for r in failures]}


# --- System ---------------------------------------------------------------------------------------------------

def database(conn):
    info = conn.execute(text(
        "SELECT current_setting('server_version') AS version, pg_database_size(current_database()) AS size, "
        "current_user AS role")).mappings().one()
    tables = conn.execute(text("""
        SELECT c.relname AS name, pg_total_relation_size(c.oid) AS size, c.reltuples::bigint AS rows
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY (current_schemas(false)) AND c.relkind = 'r' ORDER BY size DESC LIMIT 15""")).mappings().all()
    return {**dict(info), "tables": [dict(t) for t in tables]}


def migrations(conn):
    rows = conn.execute(text("SELECT version, applied_at FROM schema_migrations ORDER BY version")).mappings().all()
    return {"applied": [dict(r) for r in rows]}


def log_files(logs_dir):
    """Name, size and last change of each file directly in the logs folder (read-only mount)."""
    if not os.path.isdir(logs_dir):
        return {"missing": True}
    files = []
    try:
        with os.scandir(logs_dir) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):
                    st = entry.stat(follow_symlinks=False)
                    files.append({"name": entry.name, "size": st.st_size,
                                  "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc)})
    except OSError as e:
        return {"error": type(e).__name__}
    files.sort(key=lambda f: f["name"])
    return {"files": files, "total": sum(f["size"] for f in files)}
