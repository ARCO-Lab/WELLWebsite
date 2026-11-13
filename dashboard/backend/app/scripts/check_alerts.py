# Checks the sensor data and the vendor APIs for problems someone has to act on, and emails them (rules and settings:
# utils/alerts.py; dashboard/backend/README.md, "Email alerts", lists the alerts). scripts/scheduler_temp.py runs it
# after every 10-minute ingestion run.
#
# Each problem is an incident in the alert_incidents table, so it is emailed once when it starts, again at most every
# ALERT_REMINDER_HOURS (default 24) while it lasts, and once when it clears, with how long it lasted. Everything one
# run has to say goes in a single email (Markdown text plus the same content as HTML), which ends with every incident
# still open. A recovery of a kind in ALERT_QUIET_KINDS (default SUSPECT_VALUES) sends no email of its own: it goes
# in the next email that is sent anyway, and the daily digest lists it. Emails go to ALERT_EMAILS through the
# digest's SMTP settings (SMTP_HOST, SMTP_PORT, ...); without them the incidents are still recorded (and shown by
# /health/data and the daily digest), and the email is only printed. It reads the database only: no vendor API requests.
#
# An email that fails to send is retried with a growing delay (next run, then 20 min, 40 min, at most 1 h between
# tries) as long as it has nothing new; one with something new is tried at once. Each email has a Message-ID made from
# the incidents and notifications it carries, so a retry of an email the relay had in fact delivered (a timeout after
# it accepted the message) has the same Message-ID, and mail systems that de-duplicate show it once.
#
#   python scripts/check_alerts.py            check, record, email
#   python scripts/check_alerts.py --dry-run  check and print what would be emailed; changes nothing

import argparse
import hashlib
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from utils.alerts import (  # noqa: E402
    RECOVERY_WINDOW, Plan, aware, build_email, freshness_env, is_muted, is_quiet, plan, settings_from_env,
    stale_conditions, suspect_conditions, vendor_conditions,
)
from utils.digest import parse_alert_emails, smtp_settings  # noqa: E402
from utils.monitoring import assess_freshness  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402

RECENT_SQL = """
SELECT station_id, measurement_type, recorded_at, value FROM sensor_measurements
WHERE group_type = :group AND recorded_at >= :since
ORDER BY station_id, measurement_type, recorded_at
"""   # uses the (group_type, recorded_at) index; about 6 h x 6 readings per series


def read_recent(db, groups, since_utc):
    """{(station_id, measurement_type): [(recorded_at, value)]} since `since_utc` for these groups."""
    since = since_utc.astimezone(EST_TZ).replace(tzinfo=None)   # recorded_at is naive site time
    query = db.text(RECENT_SQL).columns(recorded_at=db.DateTime)
    recent = {}
    for group in groups:
        for r in db.session.execute(query, {"group": group, "since": since}):
            recent.setdefault((str(r.station_id), r.measurement_type), []).append((r.recorded_at, r.value))
    return recent


def find_conditions(now, env, settings):
    """Every alert condition now, and the key prefixes that can't be judged this run: ({key: Condition}, held)."""
    from db.database import db
    from api.routes.latest import query_latest_per_series
    from utils.alert_state import vendor_statuses

    freshness = assess_freshness(query_latest_per_series(), now, freshness_env(env))
    vendors = vendor_statuses()
    recent = read_recent(db, freshness["groups"], now - settings.suspect_window) if settings.suspect_values else {}
    conditions, held = {}, set()
    for found, unknown in (vendor_conditions(vendors, now, settings), stale_conditions(freshness, vendors, now),
                           suspect_conditions(freshness, recent, settings)):
        conditions.update(found)
        held |= unknown
    return conditions, held


def send_email(settings, recipients, subject, body, html=None, message_id=None):
    from daily_digest import send_email as send   # the digest's SMTP code: TLS rules and all
    send(settings, recipients, subject, body, html, message_id)


# What was last written to the log in place of an email while SMTP is off, so an unchanged email isn't written out
# again every 10 minutes (it would be, since nothing is marked as emailed then).
_last_unsent = {"signature": None}

# Failed sends in a row, what the last failed email held (its signature) and when to try again. Kept in memory: the
# worker runs every check in one process, and a restart only means one early retry.
_send_failures = {"count": 0, "signature": frozenset(), "next_try": None}
RETRY_FIRST, RETRY_MAX = timedelta(minutes=10), timedelta(hours=1)
RETRY_SLACK = timedelta(minutes=1)   # checks run about every 10 minutes, not exactly


def retry_delay(failures):
    """How long after the `failures`-th failed send in a row to try again: 10 min, doubling, at most 1 h."""
    return min(RETRY_FIRST * 2 ** min(failures - 1, 10), RETRY_MAX)


def message_id(events, sender):
    """A Message-ID made from what the email reports (`events`: (section, incident id, notification number or
    recovery time) tuples), so a retry of the same email has the same one, at the sender's domain."""
    digest = hashlib.sha256(repr(sorted(events)).encode()).hexdigest()[:32]
    domain = parseaddr(sender or "")[1].rpartition("@")[2] or "localhost"
    return f"<well-alert.{digest}@{domain}>"


def deliver(subject, body, env, send, log, signature=None, html=None, events=None, now=None):
    """Email it (`body` the text part, `html` the HTML part; the log gets the text). "sent", "off" (SMTP not set
    up: logged instead, in full only when `signature` changed), "failed", or "waiting" (an earlier send failed and
    this email has nothing new: it is retried once its delay is up, retry_delay). `events`, if given, make the
    Message-ID (message_id)."""
    now = now or datetime.now(timezone.utc)
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
    failures, contents = _send_failures, frozenset(signature or ())
    if failures["count"] and contents <= failures["signature"] and now < failures["next_try"]:
        log(f"[INFO] Not retrying the alert email yet: sending failed {failures['count']} times in a row, next try "
            f"after {failures['next_try'].astimezone(EST_TZ):%H:%M} (sooner if something new comes up): {subject}")
        return "waiting"
    mid = message_id(events, smtp["from"]) if events is not None else None
    try:
        send(smtp, recipients, subject, body, html, mid)
    except Exception as e:   # the type and message only; smtplib errors don't include the password
        failures["count"] += 1
        failures["signature"] = contents
        failures["next_try"] = now + retry_delay(failures["count"]) - RETRY_SLACK
        log(f"[ERROR] Emailing the alerts failed ({failures['count']} in a row): {type(e).__name__}: {e}; trying "
            f"again in {int(retry_delay(failures['count']).total_seconds() // 60)} min. The email was:\n"
            f"Subject: {subject}\n\n{body}")
        return "failed"
    failures.update(count=0, signature=frozenset(), next_try=None)
    log(f"[INFO] Alert email sent to {len(recipients)} recipient(s): {subject}")
    return "sent"


def run(now=None, env=None, send=send_email, log=print, dry_run=False):
    """One alert check, inside an app context. Returns a summary dict; "email" is None (nothing to say), "sent",
    "off", "failed", "waiting" (see deliver) or "dry-run". Raises on a bad setting or a database error (the
    scheduler reports those)."""
    from db.database import db
    from db.models import AlertIncident
    from utils.alert_state import open_incidents, pending_recoveries, recently_closed, superseded_incidents

    now = now or datetime.now(timezone.utc)
    env = os.environ if env is None else env
    settings = settings_from_env(env)
    conditions, held = find_conditions(now, env, settings)
    current = open_incidents()
    actions: Plan = plan(conditions, held, current, recently_closed(now - settings.reopen_within),
                         pending_recoveries(now - RECOVERY_WINDOW), now, settings,
                         muted=lambda key: is_muted(key, settings.muted), superseded=superseded_incidents())

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
    for incident in actions.reopen:   # back soon after closing, or carried on since: the same incident, not a new one
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
    closed = {id(i) for i in actions.resolve + actions.supersede}
    still_open = [i for i in current if id(i) not in closed] + list(actions.reopen) + new_rows
    open_count = len(still_open)
    email = build_email(new, actions.remind, actions.recovered, still_open, now, settings, actions.back_again)
    # Quiet recoveries that wait for the next email, since nothing else this run is worth one.
    waiting = 0 if email else sum(is_quiet(i, settings) for i in actions.recovered)
    summary = {"open": open_count, "new": len(new), "back_again": len(actions.back_again),
               "reminders": len(actions.remind),
               "recovered": len(actions.recovered), "quiet_waiting": waiting, "email": None}
    if dry_run:
        db.session.rollback()
        if email:
            log(f"[INFO] --dry-run; the alert email would be:\nSubject: {email.subject}\n\n{email.text}")
        summary["email"] = "dry-run" if email else None
        return summary

    db.session.add_all(new_rows)
    db.session.commit()   # record the incidents first: they show in /health/data even if the email fails
    if email:
        sections = (("new", new), ("back", actions.back_again), ("remind", actions.remind),
                    ("recovered", actions.recovered))
        signature = tuple(sorted((section, i.incident_key) for section, items in sections for i in items))
        # Which notification of which incident: the same until this email is sent (the counters move only then).
        events = [(section, i.id, str(aware(i.resolved_at)) if section == "recovered" else i.notifications or 0)
                  for section, items in sections for i in items]
        summary["email"] = deliver(email.subject, email.text, env, send, log, signature, email.html, events, now)
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
        f"{summary['recovered']} recovered"
        + (f" ({waiting} low-priority, kept for the next email or the digest)" if waiting else "")
        + f"; email: {summary['email'] or 'nothing to send'}")
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
