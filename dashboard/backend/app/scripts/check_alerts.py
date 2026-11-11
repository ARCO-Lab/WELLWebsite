# Checks the sensor data and the vendor APIs for problems someone has to act on, and emails them (rules and settings:
# utils/alerts.py; the README's Monitoring section lists the alerts). scripts/scheduler_temp.py runs it after every
# 10-minute ingestion run.
#
# Each problem is an incident in the alert_incidents table, so it is emailed once when it starts, again at most every
# ALERT_REMINDER_HOURS (default 24) while it lasts, and once when it clears, with how long it lasted. Everything one
# run has to say goes in a single email. Emails go to ALERT_EMAILS through the digest's SMTP settings (SMTP_HOST,
# SMTP_PORT, ...); without them the incidents are still recorded (and shown by /health/data and the daily digest),
# and the email is only printed. It reads the database only: no vendor API requests.
#
#   python scripts/check_alerts.py            check, record, email
#   python scripts/check_alerts.py --dry-run  check and print what would be emailed; changes nothing

import argparse
import os
import pathlib
import sys
from datetime import datetime, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from utils.alerts import (  # noqa: E402
    RECOVERY_WINDOW, Plan, build_email, freshness_env, is_muted, plan, settings_from_env, stale_conditions,
    suspect_conditions, vendor_conditions,
)
from utils.digest import parse_alert_emails, smtp_settings  # noqa: E402
from utils.monitoring import assess_freshness  # noqa: E402

RECENT_SQL = """
SELECT station_id, measurement_type, recorded_at, value FROM sensor_measurements
WHERE group_type = :group AND recorded_at >= :since
ORDER BY station_id, measurement_type, recorded_at
"""   # uses the (group_type, recorded_at) index; about 6 h x 6 readings per series


def read_recent(db, groups, since_utc):
    """{(station_id, measurement_type): [(recorded_at, value)]} since `since_utc` for these groups. recorded_at is
    an instant (timestamptz): the bound and the results are aware UTC, whatever the session's TimeZone."""
    from sqlalchemy import bindparam
    from db.models import Instant
    query = db.text(RECENT_SQL).bindparams(bindparam("since", type_=Instant)).columns(recorded_at=Instant)
    recent = {}
    for group in groups:
        for r in db.session.execute(query, {"group": group, "since": since_utc}):
            recent.setdefault((str(r.station_id), r.measurement_type), []).append((r.recorded_at, r.value))
    return recent


def find_conditions(now, env, settings):
    """Every alert condition now, and the key prefixes that can't be judged this run: ({key: Condition}, held)."""
    from db.database import db
    from api.routes.latest import latest_rows
    from utils.alert_state import vendor_statuses

    freshness = assess_freshness(latest_rows(), now, freshness_env(env))   # aware instants, as /health/data
    vendors = vendor_statuses()
    recent = read_recent(db, freshness["groups"], now - settings.suspect_window) if settings.suspect_values else {}
    conditions, held = {}, set()
    for found, unknown in (vendor_conditions(vendors, now, settings), stale_conditions(freshness, vendors, now),
                           suspect_conditions(freshness, recent, settings)):
        conditions.update(found)
        held |= unknown
    return conditions, held


def send_email(settings, recipients, subject, body):
    from daily_digest import send_email as send   # the digest's SMTP code: TLS rules and all
    send(settings, recipients, subject, body)


# What was last written to the log in place of an email while SMTP is off, so an unchanged email isn't written out
# again every 10 minutes (it would be, since nothing is marked as emailed then).
_last_unsent = {"signature": None}


def deliver(subject, body, env, send, log, signature=None):
    """Email it. "sent", "off" (SMTP not set up: logged instead, in full only when `signature` changed) or "failed"."""
    recipients, invalid = parse_alert_emails(env.get("ALERT_EMAILS"))
    if invalid:
        log(f"[WARN] ALERT_EMAILS: ignoring {len(invalid)} entries that aren't email addresses")
    try:
        smtp = smtp_settings(env)
    except ValueError as e:
        log(f"[ERROR] {e}; the alert email was:\nSubject: {subject}\n\n{body}")
        return "failed"
    if not smtp:
        if signature is not None and signature == _last_unsent["signature"]:
            log(f"[INFO] Not emailing (SMTP_HOST/SMTP_PORT not set); same alerts as already logged: {subject}")
        else:
            log(f"[INFO] Not emailing (SMTP_HOST/SMTP_PORT not set); the alert email would be:\n"
                f"Subject: {subject}\n\n{body}")
            _last_unsent["signature"] = signature
        return "off"
    if not recipients:
        log(f"[ERROR] SMTP is configured but ALERT_EMAILS has no valid address; the alert email was:\n"
            f"Subject: {subject}\n\n{body}")
        return "failed"
    try:
        send(smtp, recipients, subject, body)
    except Exception as e:   # the type and message only; smtplib errors don't include the password
        log(f"[ERROR] Emailing the alerts failed: {type(e).__name__}: {e}; trying again next run. The email was:\n"
            f"Subject: {subject}\n\n{body}")
        return "failed"
    log(f"[INFO] Alert email sent to {len(recipients)} recipient(s): {subject}")
    return "sent"


def run(now=None, env=None, send=send_email, log=print, dry_run=False):
    """One alert check, inside an app context. Returns a summary dict; "email" is None (nothing to say), "sent",
    "off", "failed" or "dry-run". Raises on a bad setting or a database error (the scheduler reports those)."""
    from db.database import db
    from db.models import AlertIncident
    from utils.alert_state import open_incidents, pending_recoveries, recently_closed

    now = now or datetime.now(timezone.utc)
    env = os.environ if env is None else env
    settings = settings_from_env(env)
    conditions, held = find_conditions(now, env, settings)
    current = open_incidents()
    actions: Plan = plan(conditions, held, current, recently_closed(now - settings.reopen_within),
                         pending_recoveries(now - RECOVERY_WINDOW), now, settings,
                         muted=lambda key: is_muted(key, settings.muted))

    new_rows, new = [], list(actions.notify_new)
    for condition, parent in actions.open_new:
        row = AlertIncident(incident_key=condition.key, kind=condition.kind, title=condition.title,
                            detail=condition.detail,
                            started_at=condition.started_at.astimezone(timezone.utc),   # SQLite (tests) drops the offset
                            opened_at=now, last_seen_at=now, present_since=now, notifications=0)
        if parent is not None and parent.last_notified_at is not None:
            # A finer incident split off one already emailed: it has been reported, so it isn't new.
            # Its notification state too, so a pending "back again" still goes out and flap damping carries on.
            for name in ("last_notified_at", "notifications", "recovery_notified_at", "reopened_at", "back_again_at",
                         "flaps"):
                setattr(row, name, getattr(parent, name))
        else:
            new.append(row)
        new_rows.append(row)
    for incident in actions.reopen:   # back soon after closing: the same incident again, not a new one
        incident.resolved_at, incident.close_reason = None, None
        incident.present_since = now   # a fresh stretch of presence; its flap count stays
        if incident.recovery_notified_at is not None:   # the team was told it recovered: say so once it stays back
            incident.reopened_at = now
    for incident, condition in actions.update:   # keep the wording current (durations, failure counts)
        incident.title, incident.detail, incident.last_seen_at = condition.title, condition.detail, now
        if incident.present_since is None:   # present again after a gap (or reopened)
            incident.present_since = now
    for incident in actions.absent:
        incident.present_since = None
    for incident in actions.steady:
        incident.flaps = 0
    for incident in actions.resolve:
        incident.resolved_at, incident.close_reason, incident.present_since = now, "cleared", None
    for incident in actions.supersede:
        incident.resolved_at, incident.close_reason, incident.present_since = now, "superseded", None
    open_count = len(current) + len(actions.reopen) + len(new_rows) - len(actions.resolve) - len(actions.supersede)
    email = build_email(new, actions.remind, actions.recovered, open_count, now, settings, actions.back_again)
    summary = {"open": open_count, "new": len(new), "back_again": len(actions.back_again),
               "reminders": len(actions.remind),
               "recovered": len(actions.recovered), "email": None}
    if dry_run:
        db.session.rollback()
        if email:
            log(f"[INFO] --dry-run; the alert email would be:\nSubject: {email[0]}\n\n{email[1]}")
        summary["email"] = "dry-run" if email else None
        return summary

    db.session.add_all(new_rows)
    db.session.commit()   # record the incidents first: they show in /health/data even if the email fails
    if email:
        signature = tuple(sorted((section, i.incident_key) for section, items in
                                 (("new", new), ("back", actions.back_again), ("remind", actions.remind),
                                  ("recovered", actions.recovered))
                                 for i in items))
        summary["email"] = deliver(email[0], email[1], env, send, log, signature)
        if summary["email"] == "sent":
            for incident in new + actions.remind:
                incident.last_notified_at = now
                incident.notifications = (incident.notifications or 0) + 1
                incident.recovery_notified_at = None   # told it's on again, so its recovery is worth an email
            for incident in actions.back_again:
                incident.last_notified_at = incident.back_again_at = now
                incident.notifications = (incident.notifications or 0) + 1
                incident.recovery_notified_at = incident.reopened_at = None
                incident.flaps = (incident.flaps or 0) + 1   # it now has to stay clear longer (clear_window)
            for incident in actions.recovered:
                incident.recovery_notified_at = now
            db.session.commit()
    log(f"[INFO] Alert check: {open_count} open, {summary['new']} new, {summary['back_again']} back again, "
        f"{summary['reminders']} reminders, "
        f"{summary['recovered']} recovered; email: {summary['email'] or 'nothing to send'}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check for sensor and vendor problems and email new ones.")
    parser.add_argument("--dry-run", action="store_true", help="print what would be emailed; change nothing")
    args = parser.parse_args(argv)
    from server import create_app
    with create_app().app_context():
        summary = run(dry_run=args.dry_run)
    return 1 if summary["email"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
