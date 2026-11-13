# Builds the daily digest of the sensor data: the open email alerts (scripts/check_alerts.py) and those that cleared
# in the last 24 h (including low-priority recoveries that weren't emailed on their own, and older recoveries the
# alert emails never managed to send), the sampling download's rows needing a decision (ATTENTION: lines), stale
# series, implausible values, readings and gaps per group over the last 24 h, the newest reading of every series,
# the WQData device's primary power and last contact, and yesterday's API traffic (request_metrics, utils/traffic.py). scripts/scheduler_temp.py runs it once a day (DIGEST_HOUR, default 07:00 Toronto time).
#
# The digest is Markdown text, sent with the same content as HTML (utils/email_format.py), like the alert emails.
# It emails the digest to ALERT_EMAILS when SMTP_HOST and SMTP_PORT are set (SMTP_USER, SMTP_PASSWORD and
# SMTP_FROM are optional), and otherwise prints it. It only reads the database, except to mark the recoveries it
# emailed and the alert emails hadn't (older ones, low-priority ones) as reported, and makes at most one WQData
# request, since WQData's hourly request quota is shared with the 10-minute ingestion.
#
#   python scripts/daily_digest.py               build it, then email or print it
#   python scripts/daily_digest.py --dry-run     print it, never email
#   python scripts/daily_digest.py --no-wqdata   skip the WQData request

import argparse
import os
import pathlib
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from utils.digest import anomalies, build_digest, find_gaps, parse_alert_emails, smtp_settings  # noqa: E402
from utils.email_format import markdown_to_html  # noqa: E402
from utils.monitoring import age_minutes, as_site_time, assess_freshness  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402

WINDOW = timedelta(hours=24)
MISSED_LOOKBACK = timedelta(days=14)   # how far back to look for recoveries the alert emails never sent
WQ_POWER_PARAMETER = 115219   # WQData's Primary Power (V); not stored, so it is read from the API here
WQ_FMT = "%Y-%m-%d %H:%M:%S"

SERIES_SQL = """
SELECT recorded_at, value FROM sensor_measurements
WHERE station_id = :station AND measurement_type = :measurement AND recorded_at >= :since
ORDER BY recorded_at
"""   # one range scan of the (station_id, measurement_type, recorded_at) index per series


def read_groups(db, freshness, now):
    """Rows, time slots, gaps and anomaly findings of the 24 h before `now` (aware) for every checked (not
    excluded) series. Slots and gaps are worked out in UTC: recorded_at is naive Toronto time, so on DST days
    its wall clock skips or repeats an hour, which would look like a gap or a shortfall."""
    since_utc = now.astimezone(timezone.utc) - WINDOW
    since = since_utc.astimezone(EST_TZ).replace(tzinfo=None)   # for the query: recorded_at is naive site time
    query = db.text(SERIES_SQL).columns(recorded_at=db.DateTime)
    groups, findings = {}, []
    for group, info in freshness["groups"].items():
        slots, rows, count = set(), 0, 0
        for s in info["series"]:
            if s["status"] == "excluded":
                continue
            count += 1
            readings = db.session.execute(query, {"station": s["station_id"], "measurement": s["measurement_type"],
                                                  "since": since}).all()
            rows += len(readings)
            slots.update(as_site_time(r.recorded_at).astimezone(timezone.utc) for r in readings)
            findings += anomalies(group, s["station_id"], s["measurement_type"],
                                  [r.value for r in readings if r.value is not None])
        if count:
            timestamps = sorted(slots)
            groups[group] = {"rows": rows, "series": count, "timestamps": timestamps,
                             "gaps": find_gaps(timestamps, since_utc, now.astimezone(timezone.utc))}
    return groups, findings


def read_traffic(db, now):
    """Yesterday's (site time) request totals from request_metrics, or {"error"} (e.g. migration 0005 not applied)."""
    from utils.traffic import summarize_traffic, yesterday_window
    start, end = yesterday_window(now, EST_TZ)
    try:
        return summarize_traffic(lambda sql, params: db.session.execute(db.text(sql), params), start, end)
    except Exception as e:   # the type only: a connection error's text can include the database URL
        db.session.rollback()
        return {"error": type(e).__name__}


def read_wqdata(config, now):
    """Primary power min/max and the newest data point of the last 24 h, from one WQData request."""
    if not (config.WQ_API_URL and config.WQ_API_KEY and config.WQ_DEVICE_ID):
        return {"error": "WQ_API_URL, WQ_API_KEY or WQ_DEVICE_ID is not set"}
    from api.services.quality import describe_request_error   # never logs the key (it is in the URL)
    url = f"{config.WQ_API_URL}/devices/{config.WQ_DEVICE_ID}/parameters/data"
    params = {"apiKey": config.WQ_API_KEY, "from": (now - WINDOW).strftime(WQ_FMT), "to": now.strftime(WQ_FMT)}
    try:
        response = requests.get(url, params=params, timeout=(10, 60))
        response.raise_for_status()
        body = response.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        return {"error": describe_request_error(e)}
    power, newest = [], None
    for point in body.get("data") or []:
        newest = max(newest or point["timestamp"], point["timestamp"])   # fixed format, so string order is time order
        for v in point.get("values") or []:
            if v.get("parameterId") == WQ_POWER_PARAMETER:
                try:
                    power.append(float(v["value"]))
                except (TypeError, ValueError, KeyError):
                    pass   # a reading without a numeric value is left out of the power range
    result = {"power_min": min(power, default=None), "power_max": max(power, default=None),
              "power_readings": len(power), "last_point": None, "last_point_age_minutes": None}
    if newest:   # WQData timestamps are UTC without an offset
        last = datetime.strptime(newest, WQ_FMT).replace(tzinfo=timezone.utc).astimezone(EST_TZ)
        result["last_point"] = last.replace(tzinfo=None).isoformat(sep=" ")
        result["last_point_age_minutes"] = age_minutes(last, now)
    if (body.get("info") or {}).get("more"):
        result["note"] = "only the first page of the day was read"
    return result


def send_email(settings, recipients, subject, body, html=None, message_id=None):
    """Send one email: `body` as the text part and, if given, `html` as its HTML alternative (multipart), and
    `message_id` as its Message-ID (otherwise the relay sets one)."""
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings["from"], ", ".join(recipients), subject
    if message_id:
        message["Message-ID"] = message_id
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    context = ssl.create_default_context()
    if settings["port"] == 465:
        server = smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=30, context=context)
    else:
        server = smtplib.SMTP(settings["host"], settings["port"], timeout=30)
    with server:
        if settings["port"] != 465:
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls(context=context)
                server.ehlo()
            elif settings["user"] and settings["password"]:
                # Never send the password unencrypted: a relay that offers no STARTTLS gets no login.
                raise RuntimeError(f"{settings['host']}:{settings['port']} doesn't offer STARTTLS; not logging in "
                                   "without encryption (use port 465, or a relay that supports STARTTLS)")
        if settings["user"] and settings["password"]:
            server.login(settings["user"], settings["password"])
        server.send_message(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the WELL daily data digest and email or print it.")
    parser.add_argument("--dry-run", action="store_true", help="print the digest; never email it")
    parser.add_argument("--no-wqdata", action="store_true", help="skip the WQData request")
    args = parser.parse_args(argv)

    from config import Config
    from db.database import db
    from server import create_app
    from api.routes.latest import query_latest_per_series

    from utils.alerts import RECOVERY_WINDOW, Settings, settings_from_env
    from utils.alert_state import alerts_report, mark_recoveries_reported, missed_recoveries, recent_recoveries

    try:
        alert_settings = settings_from_env()
    except ValueError as e:   # a bad ALERT_* setting fails the alert check; the digest still goes out
        print(f"[WARN] {e}; the digest uses the default alert settings")
        alert_settings = Settings()
    now = datetime.now(timezone.utc)
    app = create_app()
    with app.app_context():
        freshness = assess_freshness(query_latest_per_series(), now)
        groups, findings = read_groups(db, freshness, now)
        try:
            incidents = alerts_report()["open"]
            recoveries = recent_recoveries(now - WINDOW)
            # Recoveries the alert check stopped retrying (an SMTP outage of a day or more): listed here instead.
            missed = missed_recoveries(now - MISSED_LOOKBACK, now - RECOVERY_WINDOW, alert_settings.quiet_kinds)
        except Exception as e:   # e.g. the alert tables' migration hasn't run yet
            db.session.rollback()
            incidents = recoveries = {"error": type(e).__name__}
            missed = []
        traffic = read_traffic(db, now)
    attention = read_attention(now)
    wqdata = None if args.no_wqdata else read_wqdata(Config, now)
    subject, body = build_digest(now.astimezone(EST_TZ).date().isoformat(), freshness, groups, findings, wqdata,
                                 incidents, traffic, recoveries, alert_settings.dashboard_url,
                                 alert_settings.quiet_kinds, missed, attention)

    def reported():   # what it listed has now been told: neither the alert emails nor the next digest repeat it
        with app.app_context():
            mark_recoveries_reported(reported_ids(recoveries, missed, alert_settings.quiet_kinds), now)

    return deliver(subject, body, args.dry_run, html=markdown_to_html(body, subject), on_sent=reported)


def reported_ids(recoveries, missed, quiet_kinds):
    """The incidents whose recovery an emailed digest reports: the older recoveries it listed (`missed`), and the
    low-priority (quiet kind) recoveries of its last 24 h not emailed yet. Not the other unsent recoveries of the
    last 24 h: the alert check is still retrying their email."""
    ids = [r["id"] for r in missed]
    if isinstance(recoveries, list):
        ids += [r["id"] for r in recoveries if not r["recovery_emailed"] and r["kind"] in quiet_kinds]
    return ids


def read_attention(now):
    """The sampling download's ATTENTION: entries of the last 24 h (utils/jobs.recent_attention), or {"error"}."""
    from utils.jobs import recent_attention
    try:
        return recent_attention(now - WINDOW)
    except (OSError, ValueError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


def deliver(subject, body, dry_run, env=None, send=send_email, html=None, on_sent=None):
    """Email the digest, or print it when --dry-run or SMTP isn't set up; `on_sent()` is called once it has been
    emailed. The exit code: 1 when it should have been emailed and wasn't (bad settings, no recipients, sending
    failed), so the digest heartbeat reports /fail."""
    env = os.environ if env is None else env
    recipients, invalid = parse_alert_emails(env.get("ALERT_EMAILS"))
    if invalid:
        print(f"[WARN] ALERT_EMAILS: ignoring {len(invalid)} entries that aren't email addresses")
    try:
        settings = smtp_settings(env)
    except ValueError as e:
        print(f"[ERROR] {e}; printing the digest instead")
        print(f"Subject: {subject}\n\n{body}")
        return 1
    if dry_run or not settings:
        reason = "--dry-run" if dry_run else "SMTP_HOST/SMTP_PORT not set"
        print(f"[INFO] Not emailing ({reason}); the digest is:\n")
        print(f"Subject: {subject}\n\n{body}")
        return 0
    if not recipients:
        # SMTP is set up, so the digest is meant to be emailed: fail, so the digest heartbeat reports it.
        print("[ERROR] SMTP is configured but ALERT_EMAILS has no valid address; the digest was:\n")
        print(f"Subject: {subject}\n\n{body}")
        return 1
    try:
        send(settings, recipients, subject, body, html)
    except Exception as e:   # the type and message only; smtplib errors don't include the password
        print(f"[ERROR] Emailing the digest failed: {type(e).__name__}: {e}; the digest was:\n")
        print(f"Subject: {subject}\n\n{body}")
        return 1
    print(f"[INFO] Digest emailed to {len(recipients)} recipient(s): {subject}")
    if on_sent:
        try:
            on_sent()
        except Exception as e:   # the digest went out; at worst the next one lists the same recoveries again
            print(f"[WARN] Couldn't record what the digest reported: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
