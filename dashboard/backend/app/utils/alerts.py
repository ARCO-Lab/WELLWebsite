"""The rules and text of the email alerts (scripts/check_alerts.py). Pure: no database, network or SMTP, so all of
it is unit-tested. The alert check turns the freshness report (utils/monitoring.py), the vendor call outcomes
(vendor_status table) and the last hours of readings into conditions, each with a stable key:

  VENDOR_DOWN     the vendor API failed on the last ALERT_VENDOR_FAILURES ingestion runs in a row (HTTP error,
                  timeout, a reply without data). Credentials rejected (401/403) and WQData's hourly quota (429)
                  get their own wording, since the fix differs.
  STALE_SENSOR    the vendor answered on the latest run, but a station (or one of its sensors) has sent nothing
                  for longer than its group's limit: the problem is in the field (sensor, power, telemetry).
  SUSPECT_VALUES  data arrives, but looks wrong for hours: a water quality probe stuck on one value, most readings
                  outside the physical range, dissolved oxygen about 0, or a logger with about 0 m of water over it.

Settings (environment):
  ALERT_STALE_HOURS_<GROUP>   limit for one group, e.g. ALERT_STALE_HOURS_QUALITY=2 (defaults below)
  ALERT_STALE_HOURS           limit for every group without its own
  ALERT_VENDOR_FAILURES       failed runs in a row before VENDOR_DOWN (default 3, i.e. 30 min)
  ALERT_REMINDER_HOURS        how often an ongoing incident is emailed again (default 24)
  ALERT_SUSPECT_HOURS         window of the SUSPECT_VALUES rules (default 6); ALERT_SUSPECT_VALUES=off turns them off
  ALERT_DASHBOARD_URL         dashboard link in the emails (default https://welldash.mcmaster.ca/)
The quiet hours and excluded series of /health/data (HEALTH_QUIET_HOURS_<GROUP>, HEALTH_EXCLUDED_SERIES) apply
here too, so the water quality sonde's usual night-time silence isn't an alert.
"""
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

from utils.digest import (DEPTH_NEAR_ZERO, FLATLINE_MIN_READINGS, FLATLINE_TYPES, FLATLINE_ZERO_OK, LOGGER_SENSORS,
                          ODO_NEAR_ZERO, PLAUSIBLE_RANGES)
from utils.monitoring import as_site_time, env_key, parse_hours
from utils.timezone import EST_TZ

STALE_SENSOR, VENDOR_DOWN, SUSPECT_VALUES = "STALE_SENSOR", "VENDOR_DOWN", "SUSPECT_VALUES"
KIND_ORDER = {VENDOR_DOWN: 0, STALE_SENSOR: 1, SUSPECT_VALUES: 2}

# Which vendor API each group's readings come from. The water level loggers report through the LI-COR weather
# station, so a silent station silences them too.
VENDOR_OF_GROUP = {"Weather": "LI-COR", "Logger": "LI-COR", "Quality": "WQData"}
# The settings to change when a vendor rejects our credentials (in dashboard/backend/app/.env on the VM, and the
# repository secret of the same name used by the API canary).
CREDENTIALS = {"LI-COR": "HOBOLINK_API_TOKEN", "WQData": "WQ_API_KEY"}

# Hours without a new reading before STALE_SENSOR. LI-COR uploads about hourly, so Weather and Logger readings are
# already up to ~1 h old when they arrive: 3 h means two missed uploads. WQData reports every 10 min during the day
# (its night-time silence is covered by the quiet hours), so 2 h is a dozen missed readings.
DEFAULT_STALE_HOURS = {"Weather": 3.0, "Logger": 3.0, "Quality": 2.0}
DEFAULT_VENDOR_FAILURES = 3
DEFAULT_REMINDER_HOURS = 24.0
DEFAULT_SUSPECT_HOURS = 6.0
DEFAULT_DASHBOARD_URL = "https://welldash.mcmaster.ca/"
RECOVERY_WINDOW = timedelta(hours=24)   # a recovery that couldn't be emailed for this long is dropped


@dataclass
class Settings:
    vendor_failures: int = DEFAULT_VENDOR_FAILURES
    reminder: timedelta = timedelta(hours=DEFAULT_REMINDER_HOURS)
    suspect_window: timedelta = timedelta(hours=DEFAULT_SUSPECT_HOURS)
    suspect_values: bool = True
    dashboard_url: str = DEFAULT_DASHBOARD_URL


@dataclass
class Condition:
    key: str
    kind: str
    title: str          # the email subject, without "[WELL] "
    detail: str
    started_at: datetime   # aware


@dataclass
class Plan:
    """What one alert check does with the incidents table and the email."""
    open_new: list = field(default_factory=list)      # Conditions to insert
    update: list = field(default_factory=list)        # (incident, Condition) still going: refresh title/detail
    resolve: list = field(default_factory=list)       # open incidents whose condition cleared
    notify_new: list = field(default_factory=list)    # incidents (or Conditions) never emailed
    remind: list = field(default_factory=list)        # emailed incidents due a reminder
    recovered: list = field(default_factory=list)     # emailed incidents that cleared, recovery not yet emailed


def settings_from_env(env=None):
    env = os.environ if env is None else env
    failures = (env.get("ALERT_VENDOR_FAILURES") or "").strip()
    if failures and (not failures.isdigit() or int(failures) < 1):
        raise ValueError(f"ALERT_VENDOR_FAILURES must be a whole number of runs, at least 1, got {failures!r}")

    def hours(name, default):
        value = (env.get(name) or "").strip()
        return timedelta(hours=parse_hours(value, name) if value else default)

    suspect = (env.get("ALERT_SUSPECT_VALUES") or "on").strip().lower()
    if suspect not in ("on", "off", "1", "0", "true", "false", "yes", "no"):
        raise ValueError(f"ALERT_SUSPECT_VALUES must be on or off, got {suspect!r}")
    return Settings(
        vendor_failures=int(failures) if failures else DEFAULT_VENDOR_FAILURES,
        reminder=hours("ALERT_REMINDER_HOURS", DEFAULT_REMINDER_HOURS),
        suspect_window=hours("ALERT_SUSPECT_HOURS", DEFAULT_SUSPECT_HOURS),
        suspect_values=suspect in ("on", "1", "true", "yes"),
        dashboard_url=(env.get("ALERT_DASHBOARD_URL") or "").strip() or DEFAULT_DASHBOARD_URL,
    )


def freshness_env(env=None):
    """The environment for utils.monitoring.assess_freshness with the alert limits in place of /health/data's:
    HEALTH_MAX_AGE_HOURS[_<GROUP>] are replaced by ALERT_STALE_HOURS[_<GROUP>] or the defaults above. The quiet
    hours and excluded series stay shared."""
    env = os.environ if env is None else env
    out = dict(env)
    overall = (env.get("ALERT_STALE_HOURS") or "").strip()
    if overall:
        parse_hours(overall, "ALERT_STALE_HOURS")
    out["HEALTH_MAX_AGE_HOURS"] = overall or str(max(DEFAULT_STALE_HOURS.values()))
    groups = {env_key(g): hours for g, hours in DEFAULT_STALE_HOURS.items()}
    groups.update({name[len("ALERT_STALE_HOURS_"):]: None for name in env if name.startswith("ALERT_STALE_HOURS_")})
    for key, default in groups.items():
        name = f"ALERT_STALE_HOURS_{key}"
        value = (env.get(name) or "").strip()
        if value:
            parse_hours(value, name)
        out[f"HEALTH_MAX_AGE_HOURS_{key}"] = value or overall or (str(default) if default else "")
    return out


def describe_vendor_error(error):
    """(kind, HTTP status or None, text) for a failed vendor call. The text is the error type and status only (or
    the message of our own BadVendorResponse): requests' messages include the URL, which holds WQData's key."""
    from utils.fetching import BadVendorResponse
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status in (401, 403):
        kind = "auth"
    elif status == 429:
        kind = "quota"
    elif status is not None and status >= 500:
        kind = "server"
    elif status is not None:
        kind = "http"
    elif isinstance(error, requests.exceptions.Timeout):
        kind = "timeout"
    elif isinstance(error, requests.exceptions.ConnectionError):
        kind = "network"
    elif isinstance(error, ValueError):
        kind = "bad_response"
    else:
        kind = "error"
    if isinstance(error, BadVendorResponse):
        text = str(error)
    else:
        text = f"{type(error).__name__} (HTTP {status})" if status else type(error).__name__
    return kind, status, text


def aware(ts):
    """A database time as an aware datetime: PostgreSQL's timestamptz already is; SQLite (tests) returns naive UTC."""
    if ts is None or ts.tzinfo:
        return ts
    return ts.replace(tzinfo=timezone.utc)


def site_time(ts):
    return aware(ts).astimezone(EST_TZ).strftime("%Y-%m-%d %H:%M")


def duration(delta):
    """A rounded, readable length of time: "45 min", "3 h", "2.5 days"."""
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 120:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{round(minutes / 60)} h"
    return f"{minutes / 1440:.1f} days"


def station_label(group, station_id):
    station_id = str(station_id)
    if group == "Logger" and station_id in LOGGER_SENSORS:
        return f"Water level logger {LOGGER_SENSORS[station_id][0]}"
    names = {"Weather": "Weather station", "Quality": "Water quality station", "Logger": "Water level logger"}
    return f"{names.get(group, f'{group} station')} {station_id}"


def vendor_conditions(vendors, now, settings):
    """VENDOR_DOWN conditions from the vendor_status rows ({source: row dict})."""
    found = {}
    for source, row in sorted(vendors.items()):
        failures = row.get("consecutive_failures") or 0
        if failures < settings.vendor_failures:
            continue
        since = aware(row.get("failing_since") or row.get("last_failure_at") or now)
        status = row.get("last_http_status")
        count = f"HTTP {status} ×{failures}" if status else f"{row.get('last_error') or 'failed'} ×{failures}"
        last_ok = (f"The last successful call was at {site_time(row['last_success_at'])}."
                   if row.get("last_success_at") else "No successful call is recorded.")
        kind = row.get("last_error_kind")
        if kind == "auth":
            title = f"{source} rejects our credentials ({count}) — rotate the API key"
            detail = (f"{source} has refused the API credentials on the last {failures} ingestion runs, since "
                      f"{site_time(since)}. {last_ok} Get a new key from {source}, set {CREDENTIALS.get(source, 'it')} "
                      f"in dashboard/backend/app/.env on the VM and in the repository secret of the same name, then "
                      f"recreate the worker. No {source} data is being stored until then; the sensors may be fine.")
        elif kind == "quota":
            title = f"{source} request quota exceeded ({count}) — data is delayed until it resets"
            detail = (f"{source} has answered 'too many requests' on the last {failures} ingestion runs, since "
                      f"{site_time(since)}. {last_ok} WQData's hourly quota is shared by the 10-minute ingestion, the "
                      f"daily digest, the API canary and scripts/wqdata_backfill.py: stop any backfill that is "
                      f"running. Ingestion catches up by itself once the quota resets; the sensors may be fine.")
        else:
            title = f"{source} API not responding since {site_time(since)} ({count}) — check vendor status"
            detail = (f"The {source} API call has failed on the last {failures} ingestion runs, since "
                      f"{site_time(since)} (last error: {row.get('last_error') or 'unknown'}). {last_ok} Check the "
                      f"vendor's status page or support; our sensors may be fine. Ingestion catches up on missed "
                      f"readings by itself once the API answers (up to 14 days back).")
        found[f"vendor:{source}"] = Condition(f"vendor:{source}", VENDOR_DOWN, title, detail, since)
    return found


def stale_conditions(freshness, vendors, now):
    """STALE_SENSOR conditions from assess_freshness()'s report, for groups whose vendor answered on the latest
    run. All series of a vendor stale -> one condition for the vendor's whole site; all series of a station stale
    -> one for the station; otherwise one per silent sensor."""
    found = {}
    by_vendor = {}   # vendor -> {(group, station): [series]}
    for group, info in freshness["groups"].items():
        vendor = VENDOR_OF_GROUP.get(group)
        for s in info["series"]:
            if s["status"] != "excluded":
                by_vendor.setdefault(vendor, {}).setdefault((group, s["station_id"]), []).append(s)
    for vendor, stations in sorted(by_vendor.items(), key=lambda item: str(item[0])):
        row = vendors.get(vendor) if vendor else None
        if row and (row.get("consecutive_failures") or 0) > 0:
            continue   # the vendor failed on the latest run: VENDOR_DOWN covers it once it persists
        if row and row.get("last_success_at"):
            vendor_ok = f"{vendor} is responding (latest call {site_time(row['last_success_at'])})"
        elif vendor:
            vendor_ok = f"{vendor}'s latest call isn't recorded yet, so this may also be a vendor problem"
        else:
            vendor_ok = "The vendor of this group isn't known"
        fix = "Check the sensor, its power and its telemetry in the field."
        everything = [s for series in stations.values() for s in series]
        if len(stations) > 1 and all(s["status"] == "stale" for s in everything):
            newest = max(as_site_time(s["newest"]) for s in everything)
            names = ", ".join(station_label(g, st) for g, st in sorted(stations))
            title = f"Every {vendor} station silent for {duration(now - newest)} — vendor OK, check the site"
            detail = (f"{vendor_ok}, but none of its stations ({names}) has sent anything since "
                      f"{site_time(newest)} ({duration(now - newest)}). The water level loggers report through the "
                      f"weather station, so check the weather station's power, cellular modem and data plan first.")
            found[f"stale:{vendor}"] = Condition(f"stale:{vendor}", STALE_SENSOR, title, detail, newest)
            continue
        for (group, station), series in sorted(stations.items()):
            stale = [s for s in series if s["status"] == "stale"]
            if not stale:
                continue
            label = station_label(group, station)
            if len(stale) == len(series):
                newest = max(as_site_time(s["newest"]) for s in series)
                key = f"stale:{station}"
                title = f"{label} silent for {duration(now - newest)} — vendor OK, check the sensor"
                detail = f"{vendor_ok}; {label} has sent nothing since {site_time(newest)} ({duration(now - newest)}). {fix}"
                found[key] = Condition(key, STALE_SENSOR, title, detail, newest)
                continue
            for s in stale:
                newest = as_site_time(s["newest"])
                key = f"stale:{station}:{s['measurement_type']}"
                title = (f"{label} {s['measurement_type']} silent for {duration(now - newest)} — "
                         f"vendor OK, check the sensor")
                detail = (f"{vendor_ok} and {label}'s other sensors are reporting, but {s['measurement_type']} has "
                          f"sent nothing since {site_time(newest)} ({duration(now - newest)}). Check that sensor and "
                          f"its cable in the field.")
                found[key] = Condition(key, STALE_SENSOR, title, detail, newest)
    return found


def suspect_finding(group, station_id, measurement_type, readings, window):
    """A short description of what looks wrong with one series' readings [(recorded_at, value)] of the window, or
    None. Conservative on purpose: one odd reading is not an alert, only a pattern over the whole window."""
    values = [v for _, v in readings if v is not None]
    if len(values) < FLATLINE_MIN_READINGS:
        return None
    hours = f"{window.total_seconds() / 3600:g} h"
    median = statistics.median(values)
    if (group == "Quality" and measurement_type in FLATLINE_TYPES and len(set(values)) == 1
            and not (measurement_type in FLATLINE_ZERO_OK and values[0] == 0)):
        return f"stuck at exactly {values[0]:g} for {len(values)} readings ({hours}); the probe may have failed"
    if measurement_type == "ODO" and median <= ODO_NEAR_ZERO:
        return f"dissolved oxygen about 0 mg/L for {hours} (median {median:g}); the probe may be fouled or out of the water"
    if group == "Logger" and measurement_type == "Water Surface Elevation" and str(station_id) in LOGGER_SENSORS:
        depth = median - LOGGER_SENSORS[str(station_id)][1]
        if depth <= DEPTH_NEAR_ZERO:
            return (f"about {depth:.2f} m of water over the sensor for {hours} (median); the logger may be out of "
                    f"the water, buried or the creek dry there")
    low, high = PLAUSIBLE_RANGES.get(measurement_type, (None, None))
    outside = [v for v in values if (low is not None and v < low) or (high is not None and v > high)]
    if len(outside) * 2 >= len(values):
        bounds = f"{low:g} to {high:g}" if high is not None else f"at least {low:g}"
        return (f"{len(outside)} of {len(values)} readings in {hours} outside the physical range ({bounds}), "
                f"e.g. {outside[-1]:g}")
    return None


def suspect_conditions(freshness, recent, settings):
    """SUSPECT_VALUES conditions. recent: {(station_id, measurement_type): [(recorded_at, value)]} over the window,
    for the series that aren't excluded or stale (a silent series is STALE_SENSOR's)."""
    found = {}
    if not settings.suspect_values:
        return found
    for group, info in freshness["groups"].items():
        for s in info["series"]:
            if s["status"] != "ok":
                continue
            readings = recent.get((s["station_id"], s["measurement_type"])) or []
            finding = suspect_finding(group, s["station_id"], s["measurement_type"], readings, settings.suspect_window)
            if not finding:
                continue
            label = station_label(group, s["station_id"])
            key = f"suspect:{s['station_id']}:{s['measurement_type']}"
            started = as_site_time(readings[0][0])
            title = f"{label} {s['measurement_type']} looks wrong — check the probe"
            detail = (f"Readings are arriving, but {label} {s['measurement_type']}: {finding}. Look at the chart on "
                      f"the dashboard, then check and clean the sensor in the field if it isn't a real event.")
            found[key] = Condition(key, SUSPECT_VALUES, title, detail, started)
    return found


def plan(conditions, open_incidents, pending_recoveries, now, settings):
    """Compare the conditions found now with the open incidents (objects with incident_key, last_notified_at,
    resolved_at, ...) and decide what to store and email. pending_recoveries: incidents resolved earlier whose
    recovery email hasn't gone out yet."""
    result = Plan()
    by_key = {i.incident_key: i for i in open_incidents}
    for key, condition in conditions.items():
        incident = by_key.get(key)
        if incident is None:
            result.open_new.append(condition)
            continue
        result.update.append((incident, condition))
        if incident.last_notified_at is None:
            result.notify_new.append(incident)
        elif now - aware(incident.last_notified_at) >= settings.reminder:
            result.remind.append(incident)
    for key, incident in by_key.items():
        if key not in conditions:
            result.resolve.append(incident)
            if incident.last_notified_at is not None:
                result.recovered.append(incident)
    result.recovered += [i for i in pending_recoveries if now - aware(i.resolved_at) <= RECOVERY_WINDOW]
    return result


def sort_key(item):
    return KIND_ORDER.get(item.kind, 9), item.title


def build_email(new, reminders, recovered, open_count, now, settings):
    """(subject, body) of one batched email; items have kind, title, detail, started_at (recovered ones also
    resolved_at). None when there is nothing to send."""
    new, reminders, recovered = sorted(new, key=sort_key), sorted(reminders, key=sort_key), sorted(recovered, key=sort_key)
    if not (new or reminders or recovered):
        return None
    if new:
        subject = new[0].title if len(new) == 1 else f"{len(new)} new alerts: {new[0].title} (+{len(new) - 1} more)"
        extra = [f"{len(x)} {word}" for x, word in ((recovered, "recovered"), (reminders, "still ongoing")) if x]
        subject += f"; {', '.join(extra)}" if extra else ""
    elif recovered and not reminders:
        subject = (f"Recovered: {recovered[0].title}" if len(recovered) == 1
                   else f"{len(recovered)} alerts recovered")
    elif reminders and not recovered:
        subject = (f"Still ongoing: {reminders[0].title}" if len(reminders) == 1
                   else f"{len(reminders)} alerts still ongoing")
    else:
        subject = f"{len(recovered)} alerts recovered, {len(reminders)} still ongoing"

    lines = [f"WELL dashboard alerts, checked {site_time(now)} (Toronto time).", ""]
    for heading, items in (("NEW", new), (f"STILL ONGOING (reminder, at most every "
                                          f"{duration(settings.reminder)})", reminders)):
        if not items:
            continue
        lines += [heading, ""]
        for n, item in enumerate(items, 1):
            lines += [f"{n}. {item.title}", f"   {item.detail}",
                      f"   Since {site_time(item.started_at)} ({duration(now - aware(item.started_at))} ago).", ""]
    if recovered:
        lines += ["RECOVERED", ""]
        for item in recovered:
            lines.append(f"- {item.title}: recovered at {site_time(item.resolved_at)}, after "
                         f"{duration(aware(item.resolved_at) - aware(item.started_at))} "
                         f"(from {site_time(item.started_at)}).")
        lines.append("")
    base = settings.dashboard_url.rstrip("/")
    lines += [f"Open alerts now: {open_count}. You get one email per new problem, a reminder at most every "
              f"{duration(settings.reminder)} while it lasts, and one when it clears.",
              f"Dashboard: {base}/",
              f"Data freshness and open alerts (JSON): {base}/api/health/data",
              "What each alert means and how to tune it: the README's Monitoring section."]
    return "[WELL] " + subject, "\n".join(lines) + "\n"
