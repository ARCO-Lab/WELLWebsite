"""Database reads and writes of the email alerts' state (tables vendor_status and alert_incidents, db/models.py).

record_vendor_result is called by the ingestion (scripts/inject_from_api.py) after each vendor call; it never raises,
so a missing table (migration not applied yet) or a database hiccup can't break ingestion. The readers are used by
scripts/check_alerts.py, GET /health/data and the daily digest. Call them inside a Flask app context.
"""
from datetime import datetime, timezone

from db.database import db
from db.models import AlertIncident, VendorStatus
from utils.alerts import aware, describe_vendor_error
from utils.timezone import EST_TZ


def record_vendor_result(source, error=None, now=None, log=print):
    """Record the outcome of one vendor call: success (error None) or the exception it failed with. Written in its
    own transaction, so it neither commits nor rolls back the caller's session. True if it was recorded."""
    now = now or datetime.now(timezone.utc)
    table = VendorStatus.__table__
    try:
        with db.engine.begin() as conn:
            row = conn.execute(table.select().where(table.c.source == source)).mappings().first()
            if error is None:
                values = {"last_attempt_at": now, "last_success_at": now, "consecutive_failures": 0,
                          "failing_since": None}
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


def vendor_statuses():
    """{source: row as a dict, times aware}."""
    table = VendorStatus.__table__
    rows = db.session.execute(table.select()).mappings().all()
    return {r["source"]: {k: aware(v) if isinstance(v, datetime) else v for k, v in r.items()} for r in rows}


def open_incidents():
    return (AlertIncident.query.filter(AlertIncident.resolved_at.is_(None))
            .order_by(AlertIncident.opened_at, AlertIncident.id).all())


def pending_recoveries(since):
    """Incidents that cleared (not superseded) after being emailed and whose recovery hasn't been emailed: cleared
    since `since`, or cleared quietly soon after a "back again" emailed since `since` (their recovery email is
    deferred, utils.alerts.recovery_due). The plan decides which are due now."""
    i = AlertIncident
    return (i.query.filter(i.last_notified_at.isnot(None), i.recovery_notified_at.is_(None),
                           db.or_(db.and_(i.close_reason == "cleared", i.resolved_at >= since),
                                  db.and_(i.close_reason == "cleared_quietly", i.back_again_at >= since))).all())


def recently_closed(since):
    """{incident_key: the newest incident closed since `since`}, for incidents whose condition comes back."""
    rows = (AlertIncident.query.filter(AlertIncident.resolved_at >= since)
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
