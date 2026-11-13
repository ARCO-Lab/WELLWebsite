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
  ALERT_CLEAR_MINUTES         how long a condition must be gone before its incident clears (default 30)
  ALERT_REOPEN_HOURS          a condition back within this long of clearing reopens its incident (default 6)
  ALERT_FLAP_CLEAR_MINUTES    how long it must be gone once it has come back after a recovery (default 180,
                              doubling with each further return, up to 12 h)
  ALERT_EXCLUDED_SERIES       series to mute, like HEALTH_EXCLUDED_SERIES ("station:measurement" or "station:*")
  ALERT_DASHBOARD_URL         dashboard link in the emails (default https://welldash.mcmaster.ca/)
  ALERT_QUIET_KINDS           kinds whose recovery gets no email of its own (default SUSPECT_VALUES; "none" emails
                              every recovery). Such a recovery goes in the next email sent anyway, and in the digest.
The quiet hours and excluded series of /health/data (HEALTH_QUIET_HOURS_<GROUP>, HEALTH_EXCLUDED_SERIES) apply
here too, so the water quality sonde's usual night-time silence isn't an alert.
"""
import os
import re
import statistics
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests

from utils.email_format import (
    aware, duration, footer, markdown_to_html, section, since, span, what, when,
)
from utils.digest import (DEPTH_NEAR_ZERO, FLATLINE_MIN_READINGS, FLATLINE_TYPES, FLATLINE_ZERO_OK, LOGGER_SENSORS,
                          ODO_NEAR_ZERO, PLAUSIBLE_RANGES)
from utils.fetching import WRONG_UNITS
from utils.monitoring import DEFAULT_EXCLUDED_SERIES, as_site_time, env_key, parse_excluded_series, parse_hours

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
DEFAULT_CLEAR_MINUTES = 30.0
DEFAULT_REOPEN_HOURS = 6.0
DEFAULT_DASHBOARD_URL = "https://welldash.mcmaster.ca/"
DEFAULT_FLAP_CLEAR_MINUTES = 180.0
FLAP_CLEAR_CAP = timedelta(hours=12)
RECOVERY_WINDOW = timedelta(hours=24)   # a recovery that couldn't be emailed for this long is dropped
# Low-severity kinds: their recovery waits for the next email that goes out anyway (or the daily digest, which lists
# every recovery of the last 24 h), rather than sending one of its own. New alerts of these kinds are still emailed.
DEFAULT_QUIET_KINDS = frozenset({SUSPECT_VALUES})


@dataclass
class Settings:
    """The alert settings (see the list at the top of this file); settings_from_env() reads them."""
    vendor_failures: int = DEFAULT_VENDOR_FAILURES
    reminder: timedelta = timedelta(hours=DEFAULT_REMINDER_HOURS)
    suspect_window: timedelta = timedelta(hours=DEFAULT_SUSPECT_HOURS)
    suspect_values: bool = True
    dashboard_url: str = DEFAULT_DASHBOARD_URL
    clear_after: timedelta = timedelta(minutes=DEFAULT_CLEAR_MINUTES)
    reopen_within: timedelta = timedelta(hours=DEFAULT_REOPEN_HOURS)
    flap_clear_after: timedelta = timedelta(minutes=DEFAULT_FLAP_CLEAR_MINUTES)
    muted: frozenset = frozenset()   # (station_id, measurement_type or "*") from ALERT_EXCLUDED_SERIES
    quiet_kinds: frozenset = DEFAULT_QUIET_KINDS   # ALERT_QUIET_KINDS


@dataclass
class Condition:
    """One problem found by this check. `key` identifies it across runs (e.g. "vendor:LI-COR",
    "stale:LI-COR:2577531"), so an open incident is matched to the same condition next time."""
    key: str
    kind: str
    title: str          # the email subject, without "[WELL] "
    detail: str
    started_at: datetime   # aware


@dataclass
class Plan:
    """What one alert check does with the incidents table and the email."""
    open_new: list = field(default_factory=list)      # (Condition, coarser open incident it replaces or None)
    reopen: list = field(default_factory=list)        # recently closed incidents whose condition is back
    update: list = field(default_factory=list)        # (incident, Condition) still going: refresh title/detail
    resolve: list = field(default_factory=list)       # open incidents whose condition cleared
    supersede: list = field(default_factory=list)     # open incidents replaced by a coarser/finer one, or muted
    notify_new: list = field(default_factory=list)    # open incidents never emailed (new rows: see open_new)
    remind: list = field(default_factory=list)        # emailed incidents due a reminder
    back_again: list = field(default_factory=list)    # back after an emailed recovery, and stayed back
    absent: list = field(default_factory=list)        # open incidents whose condition is gone, not cleared yet
    steady: list = field(default_factory=list)        # flapped before, now present ALERT_REOPEN_HOURS: undamp
    recovered: list = field(default_factory=list)     # emailed incidents that cleared, recovery not yet emailed


def parse_positive(text, name, unit):
    """A positive number from a setting, e.g. "30"; ValueError naming the variable and its unit otherwise."""
    try:
        number = float(str(text).strip())
    except ValueError:
        raise ValueError(f"{name} must be a number of {unit}, got {text!r}") from None
    if not number > 0 or number == float("inf"):
        raise ValueError(f"{name} must be more than 0 {unit}, got {text!r}")
    return number


def settings_from_env(env=None):
    """Settings from the ALERT_* environment variables; unset ones take the defaults. A bad value raises
    ValueError naming the variable."""
    env = os.environ if env is None else env
    failures = (env.get("ALERT_VENDOR_FAILURES") or "").strip()
    if failures and (not failures.isdigit() or int(failures) < 1):
        raise ValueError(f"ALERT_VENDOR_FAILURES must be a whole number of runs, at least 1, got {failures!r}")

    def hours(name, default):
        value = (env.get(name) or "").strip()
        return timedelta(hours=parse_hours(value, name) if value else default)

    muted_text = (env.get("ALERT_EXCLUDED_SERIES") or "").strip()
    try:
        muted = frozenset(parse_excluded_series(muted_text))
    except ValueError:
        raise ValueError(f"ALERT_EXCLUDED_SERIES entries must look like 4501:ODO or 2577533:*, got {muted_text!r}") from None
    clear = (env.get("ALERT_CLEAR_MINUTES") or "").strip()
    flap_clear = (env.get("ALERT_FLAP_CLEAR_MINUTES") or "").strip()
    quiet_kinds = parse_quiet_kinds(env.get("ALERT_QUIET_KINDS"))
    suspect = (env.get("ALERT_SUSPECT_VALUES") or "on").strip().lower()
    if suspect not in ("on", "off", "1", "0", "true", "false", "yes", "no"):
        raise ValueError(f"ALERT_SUSPECT_VALUES must be on or off, got {suspect!r}")
    return Settings(
        vendor_failures=int(failures) if failures else DEFAULT_VENDOR_FAILURES,
        reminder=hours("ALERT_REMINDER_HOURS", DEFAULT_REMINDER_HOURS),
        suspect_window=hours("ALERT_SUSPECT_HOURS", DEFAULT_SUSPECT_HOURS),
        suspect_values=suspect in ("on", "1", "true", "yes"),
        dashboard_url=(env.get("ALERT_DASHBOARD_URL") or "").strip() or DEFAULT_DASHBOARD_URL,
        clear_after=timedelta(minutes=parse_positive(clear, "ALERT_CLEAR_MINUTES", "minutes") if clear
                              else DEFAULT_CLEAR_MINUTES),
        reopen_within=hours("ALERT_REOPEN_HOURS", DEFAULT_REOPEN_HOURS),
        flap_clear_after=timedelta(minutes=parse_positive(flap_clear, "ALERT_FLAP_CLEAR_MINUTES", "minutes")
                                   if flap_clear else DEFAULT_FLAP_CLEAR_MINUTES),
        muted=muted,
        quiet_kinds=quiet_kinds,
    )


def parse_quiet_kinds(text):
    """ALERT_QUIET_KINDS: alert kinds, comma-separated, any case; unset or blank is the default, "none" is no kind.
    ValueError naming the variable for an unknown kind."""
    text = (text or "").strip()
    if not text:
        return DEFAULT_QUIET_KINDS
    if text.lower() == "none":
        return frozenset()
    kinds = {part.strip().upper() for part in re.split(r"[,;\s]+", text) if part.strip()}
    unknown = sorted(kinds - set(KIND_ORDER))
    if unknown:
        raise ValueError(f"ALERT_QUIET_KINDS must list alert kinds ({', '.join(KIND_ORDER)}) or be none, "
                         f"got {text!r}")
    return frozenset(kinds)


def freshness_env(env=None):
    """The environment for utils.monitoring.assess_freshness with the alert limits in place of /health/data's:
    HEALTH_MAX_AGE_HOURS[_<GROUP>] are replaced by ALERT_STALE_HOURS[_<GROUP>] or the defaults above. The quiet
    hours and excluded series stay shared, plus the series muted by ALERT_EXCLUDED_SERIES."""
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
    muted = (env.get("ALERT_EXCLUDED_SERIES") or "").strip()
    if muted:
        shared = env.get("HEALTH_EXCLUDED_SERIES", DEFAULT_EXCLUDED_SERIES)
        out["HEALTH_EXCLUDED_SERIES"] = ",".join(part for part in (shared, muted) if part.strip())
    return out


def describe_vendor_error(error):
    """(kind, HTTP status or None, text) for a failed vendor call. The text is the error type and status only (or
    the message of our own BadVendorResponse): requests' messages include the URL, which holds WQData's key."""
    from utils.fetching import BadVendorResponse, UnreadableRecords
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
    elif isinstance(error, UnreadableRecords):
        kind = "unreadable"
    elif isinstance(error, ValueError):
        kind = "bad_response"
    else:
        kind = "error"
    if isinstance(error, BadVendorResponse):
        text = str(error)
    else:
        text = f"{type(error).__name__} (HTTP {status})" if status else type(error).__name__
    return kind, status, text


def site_time(ts):
    # A database time in Toronto time, written like everywhere else in the emails: "Wed Nov 11, 12:00".
    return when(ts)


def station_label(group, station_id):
    station_id = str(station_id)
    if group == "Logger" and station_id in LOGGER_SENSORS:
        return f"Water level logger {LOGGER_SENSORS[station_id][0]}"
    names = {"Weather": "Weather station", "Quality": "Water quality station", "Logger": "Water level logger"}
    return f"{names.get(group, f'{group} station')} {station_id}"


def vendor_conditions(vendors, now, settings):
    """(conditions, held) for VENDOR_DOWN from the vendor_status rows ({source: row dict}). A vendor that failed, but
    fewer times in a row than ALERT_VENDOR_FAILURES, is held: an open incident for it neither clears nor changes."""
    found, held = {}, set()
    for source, row in sorted(vendors.items()):
        failures = row.get("consecutive_failures") or 0
        if failures < settings.vendor_failures:
            if failures:
                held.add(f"vendor:{source}")
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
        elif kind == "unreadable" and WRONG_UNITS in (row.get("last_error") or ""):
            # It answers, but every record is in a unit we don't expect: a sensor was swapped or the account's unit
            # system changed. The fix is a setting in utils/parsers.py (and maybe a conversion), not in the field.
            title = f"{source} sends readings in an unexpected unit (×{failures}) — check the ingestion log"
            detail = (f"{source} has answered on the last {failures} ingestion runs, since {site_time(since)}, but "
                      f"its records are in units we don't expect (last error: {row.get('last_error')}). {last_ok} "
                      f"Check whether a sensor was swapped or the account's unit setting changed, then update "
                      f"WEATHER_UNITS/LOGGER_UNITS in utils/parsers.py (converting if needed) and refill the period "
                      f"with scripts/licor_backfill.py. No {source} data is being stored until then.")
        elif kind == "unreadable":
            # It answers, but none of its records could be read: most likely its format changed, so the fix is in
            # our parser, not at the vendor or in the field.
            title = f"{source} sends records we can't read (×{failures}) — check the ingestion log"
            detail = (f"{source} has answered on the last {failures} ingestion runs, since {site_time(since)}, but "
                      f"none of its records could be read (last error: {row.get('last_error') or 'unknown'}). "
                      f"{last_ok} The vendor may have changed its format: see the worker's ingestion log and "
                      f"utils/parsers.py. No {source} data is being stored until then; the sensors may be fine.")
        else:
            title = f"{source} API not responding since {site_time(since)} ({count}) — check vendor status"
            detail = (f"The {source} API call has failed on the last {failures} ingestion runs, since "
                      f"{site_time(since)} (last error: {row.get('last_error') or 'unknown'}). {last_ok} Check the "
                      f"vendor's status page or support; our sensors may be fine. Ingestion catches up on missed "
                      f"readings by itself once the API answers (up to 14 days back).")
        found[f"vendor:{source}"] = Condition(f"vendor:{source}", VENDOR_DOWN, title, detail, since)
    return found, held


def vendor_of(group):
    return VENDOR_OF_GROUP.get(group, group)


def is_under(key, prefix):
    """Whether `key` is `prefix` itself or nested under it ("stale:LI-COR:2577531" is under "stale:LI-COR")."""
    return key == prefix or key.startswith(prefix + ":")


def stale_conditions(freshness, vendors, now):
    """(conditions, held) for STALE_SENSOR, from assess_freshness()'s report. Keys nest: "stale:<vendor>" (every
    station of the vendor silent), "stale:<vendor>:<station>", "stale:<vendor>:<station>:<measurement>". `held` are
    key prefixes that can't be judged now (the vendor's latest call failed): their open incidents stay as they are."""
    found, held = {}, set()
    by_vendor = {}   # vendor -> {(group, station): [series]}
    for group, info in freshness["groups"].items():
        for s in info["series"]:
            if s["status"] != "excluded":
                by_vendor.setdefault(vendor_of(group), {}).setdefault((group, s["station_id"]), []).append(s)
    for vendor, stations in sorted(by_vendor.items()):
        row = vendors.get(vendor)
        if row and (row.get("consecutive_failures") or 0) > 0:
            held.add(f"stale:{vendor}")   # no new data is expected: say nothing either way until it answers
            continue
        if row and row.get("last_success_at"):
            vendor_ok = f"{vendor} is responding (latest call {site_time(row['last_success_at'])})"
        else:
            vendor_ok = f"{vendor}'s latest call isn't recorded yet, so this may also be a vendor problem"
        fix = "Check the sensor, its power and its telemetry in the field."
        # Records of the vendor's latest answer that couldn't be read (vendor_status.last_skipped) may be the missing
        # readings: then the title points at the ingestion log, not the field.
        unread = row.get("last_skipped") if row else None
        unreadable = (f"{vendor} sends readings in an unexpected unit, check the ingestion log"
                      if unread and WRONG_UNITS in unread
                      else f"{vendor} sent unreadable records, check the ingestion log")
        check_site, check_sensor = (unreadable, unreadable) if unread else ("vendor OK, check the site",
                                                                         "vendor OK, check the sensor")
        note = (f" {vendor}'s latest answer also had records we couldn't read ({unread}); check the worker's "
                f"ingestion log before going to the field." if unread else "")
        everything = [s for series in stations.values() for s in series]
        if len(stations) > 1 and all(s["status"] == "stale" for s in everything):
            newest = max(as_site_time(s["newest"]) for s in everything)
            names = ", ".join(station_label(g, st) for g, st in sorted(stations))
            title = f"Every {vendor} station silent for {duration(now - newest)} — {check_site}"
            detail = (f"{vendor_ok}, but none of its stations ({names}) has sent anything since "
                      f"{site_time(newest)} ({duration(now - newest)}). The water level loggers report through the "
                      f"weather station, so check the weather station's power, cellular modem and data plan "
                      f"first.{note}")
            key = f"stale:{vendor}"
            found[key] = Condition(key, STALE_SENSOR, title, detail, newest)
            continue
        for (group, station), series in sorted(stations.items()):
            label = station_label(group, station)
            for s in series:
                if s["status"] != "future":
                    continue
                # Its newest reading is dated ahead of now (a device clock that jumped ahead), so it can't be judged
                # stale: say so, under the series' own key, until the row is gone.
                key = f"stale:{vendor}:{station}:{s['measurement_type']}"
                newest = as_site_time(s["newest"])
                title = (f"{label} {s['measurement_type']} newest reading dated {site_time(newest)}, in the future — "
                         f"check the device clock")
                detail = (f"The newest stored {label} {s['measurement_type']} reading is dated {site_time(newest)}, "
                          f"ahead of now, so whether it is still reporting can't be told. Ingestion now skips such "
                          f"records; this one was stored before. Check the device's clock, then delete the row(s) "
                          f"dated in the future from sensor_measurements.{note}")
                found[key] = Condition(key, STALE_SENSOR, title, detail, now)
            stale = [s for s in series if s["status"] == "stale"]
            if not stale:
                continue
            if len(stale) == len(series):
                newest = max(as_site_time(s["newest"]) for s in series)
                key = f"stale:{vendor}:{station}"
                title = f"{label} silent for {duration(now - newest)} — {check_sensor}"
                detail = (f"{vendor_ok}; {label} has sent nothing since {site_time(newest)} "
                          f"({duration(now - newest)}). {fix}{note}")
                found[key] = Condition(key, STALE_SENSOR, title, detail, newest)
                continue
            for s in stale:
                newest = as_site_time(s["newest"])
                key = f"stale:{vendor}:{station}:{s['measurement_type']}"
                title = (f"{label} {s['measurement_type']} silent for {duration(now - newest)} — "
                         + check_sensor)
                detail = (f"{vendor_ok} and {label}'s other sensors are reporting, but {s['measurement_type']} has "
                          f"sent nothing since {site_time(newest)} ({duration(now - newest)}). Check that sensor and "
                          f"its cable in the field.{note}")
                found[key] = Condition(key, STALE_SENSOR, title, detail, newest)
    return found, held


def enough_readings(readings):
    return sum(v is not None for _, v in readings) >= FLATLINE_MIN_READINGS


def suspect_finding(group, station_id, measurement_type, readings, window):
    """A short description of what looks wrong with one series' readings [(recorded_at, value)] of the window, or
    None, including when there are too few readings to judge. Conservative on purpose: one odd reading is not an
    alert, only a pattern over the whole window."""
    if not enough_readings(readings):
        return None
    values = [v for _, v in readings if v is not None]
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
    """(conditions, held) for SUSPECT_VALUES. recent: {(station_id, measurement_type): [(recorded_at, value)]} over
    the window. A series that is stale, or has too few readings to judge (e.g. the water quality sonde at night),
    is held: an open incident for it stays open rather than "recovering" for lack of data."""
    found, held = {}, set()
    if not settings.suspect_values:
        return found, held
    for group, info in freshness["groups"].items():
        for s in info["series"]:
            if s["status"] == "excluded":
                continue
            key = f"suspect:{vendor_of(group)}:{s['station_id']}:{s['measurement_type']}"
            readings = recent.get((s["station_id"], s["measurement_type"])) or []
            if s["status"] != "ok" or not enough_readings(readings):
                held.add(key)
                continue
            finding = suspect_finding(group, s["station_id"], s["measurement_type"], readings, settings.suspect_window)
            if not finding:
                continue
            label = station_label(group, s["station_id"])
            title = f"{label} {s['measurement_type']} looks wrong — check the probe"
            detail = (f"Readings are arriving, but {label} {s['measurement_type']}: {finding}. Look at the chart on "
                      f"the dashboard, then check and clean the sensor in the field if it isn't a real event.")
            found[key] = Condition(key, SUSPECT_VALUES, title, detail, as_site_time(readings[0][0]))
    return found, held


def plan(conditions, held, open_incidents, recently_closed, pending_recoveries, now, settings,
         muted=lambda key: False):
    """Compare the conditions found now with the incidents and decide what to store and email.

    conditions: {key: Condition}. held: key prefixes that can't be judged this run; their open incidents are left
    exactly as they are. open_incidents: incidents with resolved_at NULL. recently_closed: {key: incident} closed
    within ALERT_REOPEN_HOURS, newest per key. pending_recoveries: cleared, emailed incidents whose recovery email
    hasn't gone out. muted(key): whether the key's series is muted (ALERT_EXCLUDED_SERIES).

    - An incident clears (and its recovery is emailed) once its condition has been gone for ALERT_CLEAR_MINUTES.
      A condition that comes back within ALERT_REOPEN_HOURS of clearing reopens the same incident; if its recovery
      had been emailed, "back again" is emailed once it has stayed back ALERT_CLEAR_MINUTES.
    - Flap damping: once an incident has had a "back again", it has to be gone for longer before it clears again:
      ALERT_FLAP_CLEAR_MINUTES, doubled for each further "back again", up to FLAP_CLEAR_CAP (clear_window). So a
      flapping condition sends at most one "recovered" and one "back again" per window, and the last email about
      a key is never wrong for longer than ALERT_CLEAR_MINUTES or the incident's current window. An incident that
      then stays present without a break for ALERT_REOPEN_HOURS is steady again: its flap count resets.
    - Keys nest (site > station > sensor). When a coarser condition replaces finer open incidents, or finer
      conditions replace a coarser one, the replaced incidents close as superseded, without a recovery email, and a
      new finer incident takes over its coarser incident's notification state, so nothing already reported is
      emailed as new. A muted series' incidents close the same way.
    """
    result = Plan()
    open_by_key = {i.incident_key: i for i in open_incidents}
    present = set(conditions)
    reopened = set()

    def is_held(key):
        return any(is_under(key, prefix) for prefix in held)

    for key, condition in conditions.items():
        incident = open_by_key.get(key)
        if incident is None and key in recently_closed:
            incident = recently_closed[key]
            result.reopen.append(incident)
            reopened.add(id(incident))
        if incident is None:
            parent = next((i for k, i in open_by_key.items() if k not in present and key.startswith(k + ":")), None)
            result.open_new.append((condition, parent))
            continue
        result.update.append((incident, condition))
        if (incident.flaps and id(incident) not in reopened and incident.present_since is not None
                and now - aware(incident.present_since) >= settings.reopen_within):
            result.steady.append(incident)   # steady for hours: its real recovery is reported after the usual delay
        if incident.last_notified_at is None:
            result.notify_new.append(incident)
        elif (incident.reopened_at is not None or id(incident) in reopened) and incident.recovery_notified_at is not None:
            # Back after an emailed recovery: the next email about it is "back again", never a reminder.
            if incident.reopened_at is not None and now - aware(incident.reopened_at) >= settings.clear_after:
                result.back_again.append(incident)
        elif now - aware(incident.last_notified_at) >= settings.reminder:
            result.remind.append(incident)
    for key, incident in open_by_key.items():
        if key in present or is_held(key):
            continue
        if muted(key) or any(key.startswith(k + ":") or k.startswith(key + ":") for k in present):
            result.supersede.append(incident)
        elif now - aware(incident.last_seen_at) >= clear_window(incident, settings):
            result.resolve.append(incident)
            if incident.last_notified_at is not None and incident.recovery_notified_at is None:
                result.recovered.append(incident)
        else:
            result.absent.append(incident)
    result.recovered += [i for i in pending_recoveries
                         if id(i) not in reopened and now - aware(i.resolved_at) <= RECOVERY_WINDOW]
    return result


def clear_window(incident, settings):
    """How long an incident's condition must be gone before it clears: ALERT_CLEAR_MINUTES, or once it has come back
    after a recovery ("back again" emailed `flaps` times), ALERT_FLAP_CLEAR_MINUTES doubled per further return,
    at most FLAP_CLEAR_CAP."""
    flaps = incident.flaps or 0
    if not flaps:
        return settings.clear_after
    return min(settings.flap_clear_after * 2 ** min(flaps - 1, 10), max(FLAP_CLEAR_CAP, settings.flap_clear_after))


def is_muted(key, muted):
    """Whether a stale/suspect key is about a series muted by ALERT_EXCLUDED_SERIES (vendor and site keys never are)."""
    parts = key.split(":", 3)
    if parts[0] not in ("stale", "suspect") or len(parts) < 3:
        return False
    station, measurement = parts[2], parts[3] if len(parts) > 3 else "*"
    return (station, "*") in muted or (station, measurement) in muted


def sort_key(item):
    return KIND_ORDER.get(item.kind, 9), item.title


# One email: its subject and two bodies with the same content, Markdown text and the HTML rendered from it.
Email = namedtuple("Email", "subject text html")

# What an alert's problem is, shortest form, for the subject and the cards; and what "recovered" means for it.
RECOVERED_AS = {VENDOR_DOWN: "API answering again", STALE_SENSOR: "reporting again",
                SUSPECT_VALUES: "readings back to normal"}
SILENT_RE = re.compile(r"silent for (.+?)(?: —|$)")


def status(item, now):
    """The problem in a few words: "silent 4 h", "readings look wrong", "API not responding". From the kind, and
    for silences and vendor errors from the title, which every check refreshes (utils/alerts.py writes both)."""
    title = item.title or ""
    if item.kind == STALE_SENSOR:
        if "in the future" in title:
            return "dated in the future"
        found = SILENT_RE.search(title)
        return f"silent {found.group(1) if found else duration(now - aware(item.started_at))}"
    if item.kind == SUSPECT_VALUES:
        return "readings look wrong"
    if item.kind == VENDOR_DOWN:
        for words, text in (("credentials", "rejects our credentials"), ("quota", "request quota exceeded"),
                            ("can't read", "sends records we can't read"),
                            ("unexpected unit", "sends readings in an unexpected unit")):
            if words in title:
                return text
        return "not responding"
    return title.split(" — ")[0]


def action(item):
    """What to do, one line: the part of the title after " — " ("vendor OK, check the sensor"), capitalized."""
    text = (item.title or "").split(" — ", 1)[1] if " — " in (item.title or "") else "see the dashboard"
    return text[:1].upper() + text[1:]


def short_action(item):
    # The subject's version: the vendor is fine whenever "vendor OK" is said, so the subject leaves it out. The first
    # letter is lowercased only when it starts an ordinary word ("Check ..."), never a name ("LI-COR", "WQData").
    text = action(item)
    if text.startswith("Vendor OK, "):
        return text[len("Vendor OK, "):]
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


def is_quiet(item, settings):
    """Whether this recovery waits for an email that goes out anyway (ALERT_QUIET_KINDS)."""
    return item.kind in settings.quiet_kinds


def needs_email(new, reminders, recovered, back_again, settings):
    """Whether this check has anything worth an email of its own: any problem (new, still open, back again), or a
    recovery of a kind not in ALERT_QUIET_KINDS. Quiet recoveries alone wait (their recovery stays unsent, so the
    next check offers them again, for up to RECOVERY_WINDOW; the daily digest lists them either way)."""
    return bool(new or reminders or back_again or any(not is_quiet(r, settings) for r in recovered))


def problem_card(item, now, base):
    back = getattr(item, "reopened_at", None)   # back after an emailed recovery: say since when it is back
    return [f"**{what(key_of(item))}**: {status(item, now)}",
            f"Back {since(back, now)[0].lower()}{since(back, now)[1:]}; first seen {when(item.started_at)}"
            if back is not None else since(item.started_at, now),
            f"To do: {action(item)}.",
            f"Details: {item.detail}",
            f"Dashboard: {base}/"]


def key_of(item):
    # Incidents (db/models.py) have incident_key; Conditions (new this run, not stored yet) have key.
    return getattr(item, "incident_key", None) or item.key


def build_email(new, reminders, recovered, open_items, now, settings, back_again=()):
    """The Email for one alert check, or None when there is nothing worth sending (see needs_email). new,
    reminders, back_again, recovered: incidents (kind, incident_key, title, detail, started_at; recovered ones also
    resolved_at). open_items: every incident open after this check, for the "Open right now" list."""
    new, reminders, recovered = sorted(new, key=sort_key), sorted(reminders, key=sort_key), sorted(recovered, key=sort_key)
    back_again, open_items = sorted(back_again, key=sort_key), sorted(open_items, key=sort_key)
    if not needs_email(new, reminders, recovered, back_again, settings):
        return None
    base = settings.dashboard_url.rstrip("/")
    counts = [(len(new), "new"), (len(reminders), "still open"), (len(back_again), "back again"),
              (len(recovered), "recovered")]
    if sum(n for n, _ in counts) == 1:
        if new or back_again:
            item = (new or back_again)[0]
            subject = (f"{'New' if new else 'Back again'}: {what(key_of(item))} {status(item, now)} — "
                       f"{short_action(item)}")
        elif reminders:
            item = reminders[0]
            subject = f"Still open: {what(key_of(item))} {status(item, now)}"
            if item.kind != STALE_SENSOR:   # a silence already says how long
                subject += f" ({duration(now - aware(item.started_at))})"
        else:
            item = recovered[0]
            subject = f"Recovered: {what(key_of(item))} ({duration(aware(item.resolved_at) - aware(item.started_at))})"
    else:
        subject = ", ".join(f"{n} {word}" for n, word in counts if n)

    words = {"new": lambda n: f"{n} new problem{'s' if n > 1 else ''}"}
    summary = ", ".join(words.get(word, lambda n, w=word: f"{n} {w}")(n) for n, word in counts if n)
    lines = [f"{summary[:1].upper()}{summary[1:]}. Open right now: {len(open_items)}.", ""]
    for heading, items in (("New problems", new), ("Still open (reminder)", reminders), ("Back again", back_again)):
        if items:
            lines += section(heading, [problem_card(i, now, base) for i in items])
    if recovered:
        lines += section("Recovered", [
            [f"**{what(key_of(i))}**: {RECOVERED_AS.get(i.kind, 'recovered')}",
             span(i.started_at, i.resolved_at),
             f"Dashboard: {base}/"] for i in recovered])
    lines += section("Open right now", [
        [f"**{what(key_of(i))}**: {status(i, now)}. {since(i.started_at, now)}"] for i in open_items] or [["None"]])
    lines += footer(settings.dashboard_url, now)
    text = "\n".join(lines) + "\n"
    subject = "[WELL] " + subject
    return Email(subject, text, markdown_to_html(text, subject))
