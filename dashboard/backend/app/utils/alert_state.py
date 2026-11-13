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


def superseded_incidents(since):
    """{incident_key: the newest incident closed as superseded}, so one whose problem carried on can reopen when its
    condition is back (utils/alerts.carried_on and handed_to_silence). Only those closed since `since` (now minus
    ALERT_REOPEN_HOURS) or since the oldest incident still open or cleared since then was opened: an older one
    can't have been carried on by any of those."""
    i = AlertIncident
    oldest = (db.session.query(db.func.min(i.opened_at))
              .filter(db.or_(i.resolved_at.is_(None), db.and_(i.resolved_at >= since, i.close_reason == "cleared")))
              .scalar())
    start = since if oldest is None else min(aware(oldest), since)
    rows = (i.query.filter(i.resolved_at >= start, i.close_reason == "superseded")
            .order_by(i.resolved_at, i.id).all())
    return {r.incident_key: r for r in rows}   # later rows win


def missed_recoveries(since, before, quiet_kinds=()):
    """Incidents that cleared between `since` and `before` after being emailed, whose recovery email never went out:
    the alert check stops retrying RECOVERY_WINDOW after a recovery (utils/alerts.py). The daily digest lists them
    and, once it has been emailed, marks them as reported (mark_recoveries_reported), so an SMTP outage longer than
    that doesn't lose them. Not the kinds in `quiet_kinds` (ALERT_QUIET_KINDS): their recovery was never meant to
    have an email of its own, and the digest of the day it happened listed it."""
    i = AlertIncident
    rows = (i.query.filter(i.resolved_at >= since, i.resolved_at < before, i.close_reason == "cleared",
                           i.last_notified_at.isnot(None), i.recovery_notified_at.is_(None),
                           i.kind.notin_(list(quiet_kinds)))
            .order_by(i.resolved_at, i.id).all())
    return [{"id": r.id, "kind": r.kind, "key": r.incident_key, "title": r.title, "started_at": iso(r.started_at),
             "resolved_at": iso(r.resolved_at)} for r in rows]


def mark_recoveries_reported(ids, now):
    """Mark these incidents' recoveries as reported (ids from missed_recoveries or recent_recoveries), once the digest
    listing them has been emailed, like an emailed recovery."""
    if ids:
        AlertIncident.query.filter(AlertIncident.id.in_(ids)).update({"recovery_notified_at": now},
                                                                     synchronize_session=False)
        db.session.commit()


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
    id, kind, key, title, started_at, resolved_at, and whether the recovery was emailed (a quiet kind's may not be,
    ALERT_QUIET_KINDS). Superseded incidents aren't listed: their problem carried on in another incident."""
    i = AlertIncident
    rows = (i.query.filter(i.resolved_at >= since, i.close_reason == "cleared", i.last_notified_at.isnot(None))
            .order_by(i.resolved_at, i.id).all())
    return [{"id": r.id, "kind": r.kind, "key": r.incident_key, "title": r.title, "started_at": iso(r.started_at),
             "resolved_at": iso(r.resolved_at), "recovery_emailed": r.recovery_notified_at is not None}
            for r in rows]
