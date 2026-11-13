"""Database reads and writes of the email alerts' state (tables vendor_status and alert_incidents, db/models.py).

record_vendor_result is called by the ingestion (scripts/inject_from_api.py) after each vendor call, and
record_fetched_until once that call's readings are stored; neither raises, so a missing table (migration not applied
yet) or a database hiccup can't break ingestion. The readers are used by scripts/check_alerts.py, GET /health/data,
the daily digest and (fetched_until) the ingestion. Call them inside a Flask app context.
"""
from datetime import datetime, timezone

from db.database import db
from db.models import AlertIncident, VendorStatus
from utils.alerts import aware, describe_vendor_error
from utils.timezone import EST_TZ


def record_vendor_result(source, error=None, now=None, log=print, skipped=None):
    """Record the outcome of one vendor call: success (error None) or the exception it failed with. Written in its
    own transaction, so it neither commits nor rolls back the caller's session. True if it was recorded.
    `skipped` (on success) describes the records of the answer that couldn't be read, None when all were."""
    now = now or datetime.now(timezone.utc)
    table = VendorStatus.__table__
    try:
        with db.engine.begin() as conn:
            row = conn.execute(table.select().where(table.c.source == source)).mappings().first()
            if error is None:
                values = {"last_attempt_at": now, "last_success_at": now, "consecutive_failures": 0,
                          "failing_since": None, "last_skipped": skipped}
            else:
                kind, status, text = describe_vendor_error(error)
                failures = (row["consecutive_failures"] if row else 0) + 1
                values = {"last_attempt_at": now, "last_failure_at": now, "consecutive_failures": failures,
                          "failing_since": row["failing_since"] if row and row["failing_since"] else now,
                          "last_error_kind": kind, "last_http_status": status, "last_error": text}
            if row:
                conn.execute(table.update().where(table.c.source == source).values(**values))
            else:
                conn.execute(table.insert().values(source=source, **values))
        return True
    except Exception as e:   # the type only: a connection error's text can include the database URL
        log(f"[WARN] Couldn't record the {source} call outcome for the alerts: {type(e).__name__}")
        return False


def fetched_until(source, log=print):
    """The end (aware UTC) of the newest `source` request whose readings were all stored, or None when none is
    recorded or it can't be read. Read on a connection of its own, so a failure leaves the caller's session usable;
    the ingestion then falls back to starting from the stored readings."""
    table = VendorStatus.__table__
    try:
        with db.engine.connect() as conn:
            return aware(conn.execute(table.select().with_only_columns(table.c.fetched_until)
                                      .where(table.c.source == source)).scalar())
    except Exception as e:   # the type only, as above
        log(f"[WARN] Couldn't read where the last {source} fetch ended: {type(e).__name__}")
        return None


def record_fetched_until(source, until, log=print):
    """Record that every reading `source` returned up to `until` is stored. Updates the row record_vendor_result
    wrote for this call; never raises (the next run then starts from the previous mark, which is safe)."""
    table = VendorStatus.__table__
    try:
        with db.engine.begin() as conn:
            conn.execute(table.update().where(table.c.source == source).values(fetched_until=until))
        return True
    except Exception as e:
        log(f"[WARN] Couldn't record where the {source} fetch ended: {type(e).__name__}")
        return False


def vendor_statuses():
    """{source: row as a dict, times aware}."""
    table = VendorStatus.__table__
    rows = db.session.execute(table.select()).mappings().all()
    return {r["source"]: {k: aware(v) if isinstance(v, datetime) else v for k, v in r.items()} for r in rows}


def open_incidents():
    # The incidents not resolved yet, oldest first.
    return (AlertIncident.query.filter(AlertIncident.resolved_at.is_(None))
            .order_by(AlertIncident.opened_at, AlertIncident.id).all())


def pending_recoveries(since):
    """Incidents that cleared (not superseded) since `since` after being emailed, whose recovery email hasn't gone
    out (the send failed), so it is retried."""
    i = AlertIncident
    return i.query.filter(i.resolved_at >= since, i.close_reason == "cleared", i.last_notified_at.isnot(None),
                          i.recovery_notified_at.is_(None)).all()


def recently_closed(since):
    """{incident_key: the newest incident cleared since `since`}, for incidents whose condition comes back. Only
    "cleared" ones: a superseded incident's problem was carried on by a coarser one, whose state is what counts."""
    rows = (AlertIncident.query.filter(AlertIncident.resolved_at >= since, AlertIncident.close_reason == "cleared")
            .order_by(AlertIncident.resolved_at, AlertIncident.id).all())
    return {i.incident_key: i for i in rows}   # later rows win


def iso(ts):
    """Site (Toronto) time with its offset, like /health/data's checked_at."""
    return aware(ts).astimezone(EST_TZ).isoformat(timespec="seconds") if ts else None


def alerts_report():
    """The open incidents and the vendor call outcomes, as JSON-ready dicts, for /health/data and the digest. Public
    (/health/data is), so only the kind, key, title and times: the detail, with setting names and advice, is for
    the emails."""
    incidents = [{"kind": i.kind, "key": i.incident_key, "title": i.title,
                  "started_at": iso(i.started_at), "opened_at": iso(i.opened_at),
                  "last_emailed_at": iso(i.last_notified_at)} for i in open_incidents()]
    vendors = {source: {"last_attempt_at": iso(r["last_attempt_at"]), "last_success_at": iso(r["last_success_at"]),
                        "consecutive_failures": r["consecutive_failures"], "last_error": r["last_error"]
                        if r["consecutive_failures"] else None}
               for source, r in vendor_statuses().items()}
    return {"open": incidents, "vendors": vendors}


def recent_recoveries(since):
    """Incidents that cleared since `since` after being emailed, oldest first, as dicts for the daily digest:
    kind, key, title, started_at, resolved_at, and whether the recovery was emailed (a quiet kind's may not be,
    ALERT_QUIET_KINDS). Superseded incidents aren't listed: their problem carried on in another incident."""
    i = AlertIncident
    rows = (i.query.filter(i.resolved_at >= since, i.close_reason == "cleared", i.last_notified_at.isnot(None))
            .order_by(i.resolved_at, i.id).all())
    return [{"kind": r.kind, "key": r.incident_key, "title": r.title, "started_at": iso(r.started_at),
             "resolved_at": iso(r.resolved_at), "recovery_emailed": r.recovery_notified_at is not None}
            for r in rows]
