"""The pure parts of the daily digest (scripts/daily_digest.py): settings, gap finding, implausible-value rules
and the text itself, written as Markdown like the alert emails (utils/email_format.py). No database, network or SMTP
here, so all of it is unit-tested."""
import math
import os
import re
import statistics
from datetime import datetime, timedelta
from types import SimpleNamespace

from utils.email_format import footer, since, span, what, when, when_local
from utils.parsers import LOGGER_CONFIG
from utils.timezone import EST_TZ
from utils.traffic import traffic_lines

INTERVAL = timedelta(minutes=10)   # every sensor reports every 10 minutes
GAP = timedelta(minutes=30)        # a stretch longer than this without readings is listed as a gap

# Logger station_id -> (logger number, height of the sensor in m asl). Loggers store the water surface
# elevation (sensor height + depth, utils/parsers.py), so depth is that minus the sensor height.
LOGGER_SENSORS = {
    str(c["station_id"]): (c["logger_num"], c["z"] - c["L"] * math.cos(math.radians(c["theta"])))
    for c in LOGGER_CONFIG.values()
}

# Readings outside these ranges can't be real. (low, high); None is open.
PLAUSIBLE_RANGES = {
    "Water Temperature": (-1.0, 40.0),
    "Air Temperature": (-45.0, 45.0),
    "Relative Humidity": (0.0, 100.0),
    "Conductivity": (0.0, None),
    "Salinity": (0.0, None),
    "TDS": (0.0, None),
    # Optical sensors read slightly below 0 in clear water (calibration offset), so a little is allowed.
    "TSS": (-1.0, None),
    "Turbidity": (-1.0, None),
}
ODO_NEAR_ZERO = 0.1          # mg/L; stream water is never this low on oxygen for a whole day
ODOSAT_NEAR_ZERO = 1.0       # %
DEPTH_NEAR_ZERO = 0.02       # m of water above a logger's sensor
FLATLINE_MIN_READINGS = 12   # Quality series that report the very same value this many times in a row
# ... among these, which vary from reading to reading when the probe works. (Salinity and TDS are reported to
# two decimals and can sit on one value all day, so they are left out.)
FLATLINE_TYPES = {"Water Temperature", "Conductivity", "ODO", "ODOSat", "Turbidity", "TSS"}
# Clear water reads exactly 0 on these all day, so a flat run at 0 isn't a stuck sensor.
FLATLINE_ZERO_OK = {"TSS", "Turbidity"}

EMAIL_RE = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+")


def parse_alert_emails(text):
    """Recipients from ALERT_EMAILS: addresses separated by commas (semicolons and spaces work too), duplicates
    and blanks dropped, order kept. Returns (valid addresses, entries that aren't addresses)."""
    valid, invalid = [], []
    for entry in re.split(r"[,;\s]+", text or ""):
        if not entry:
            continue
        if not EMAIL_RE.fullmatch(entry):
            invalid.append(entry)
        elif entry.lower() not in (v.lower() for v in valid):
            valid.append(entry)
    return valid, invalid


def smtp_settings(env=None):
    """SMTP settings from the environment, or None unless both SMTP_HOST and SMTP_PORT are set.
    SMTP_USER and SMTP_PASSWORD are optional (login only if both are set); SMTP_FROM defaults to SMTP_USER."""
    env = os.environ if env is None else env
    host, port = (env.get("SMTP_HOST") or "").strip(), (env.get("SMTP_PORT") or "").strip()
    if not host or not port:
        return None
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError(f"SMTP_PORT must be a port number, got {port!r}")
    user = (env.get("SMTP_USER") or "").strip()
    sender = (env.get("SMTP_FROM") or "").strip() or user
    if not sender:
        raise ValueError("set SMTP_FROM (or SMTP_USER) to the address the digest is sent from")
    return {"host": host, "port": int(port), "user": user, "password": env.get("SMTP_PASSWORD") or "",
            "from": sender}


def find_gaps(timestamps, start, end, min_gap=GAP):
    """[(from, to)] stretches longer than min_gap with no reading, from `start` to the newest of `timestamps`
    (sorted), or [(start, end)] if there are none. Pass aware UTC times (scripts/daily_digest.py does), so a DST
    change doesn't make or hide a gap. The time after the newest reading isn't listed: LI-COR readings arrive
    about an hour late, and the newest-reading ages already show it."""
    if not timestamps:
        return [(start, end)]
    gaps, previous = [], start
    for ts in timestamps:
        if ts - previous > min_gap:
            gaps.append((previous, ts))
        previous = max(previous, ts)
    return gaps


def series_label(station_id, measurement_type):
    logger = LOGGER_SENSORS.get(str(station_id))
    return f"Logger {logger[0]} {measurement_type}" if logger else f"{station_id} {measurement_type}"


def anomalies(group, station_id, measurement_type, values):
    """Implausible-value findings (strings) for one series' readings of the last 24 h, in time order."""
    if not values:
        return []
    found, label = [], series_label(station_id, measurement_type)
    median = statistics.median(values)
    if measurement_type == "ODO" and median <= ODO_NEAR_ZERO:
        found.append(f"{label}: dissolved oxygen is about 0 mg/L (median {median:g}); "
                     "the probe may be fouled, out of the water or failing")
    if measurement_type == "ODOSat" and median <= ODOSAT_NEAR_ZERO:
        found.append(f"{label}: oxygen saturation is about 0 % (median {median:g})")
    if group == "Logger" and measurement_type == "Water Surface Elevation" and str(station_id) in LOGGER_SENSORS:
        depth = median - LOGGER_SENSORS[str(station_id)][1]
        if depth <= DEPTH_NEAR_ZERO:
            found.append(f"{label}: about {depth:.2f} m of water above the sensor (median); "
                         "the logger may be out of the water or the creek dry there")
    low, high = PLAUSIBLE_RANGES.get(measurement_type, (None, None))
    outside = [v for v in values if (low is not None and v < low) or (high is not None and v > high)]
    if outside:
        bounds = f"{low:g} to {high:g}" if high is not None else f"at least {low:g}"
        found.append(f"{label}: {len(outside)} of {len(values)} readings outside the plausible range "
                     f"({bounds}), e.g. {outside[0]:g}")
    if (group == "Quality" and measurement_type in FLATLINE_TYPES and len(values) >= FLATLINE_MIN_READINGS
            and len(set(values)) == 1
            and not (measurement_type in FLATLINE_ZERO_OK and values[0] == 0)):
        found.append(f"{label}: all {len(values)} readings are exactly {values[0]:g}; the sensor may be stuck")
    return found


def fmt_age(minutes):
    if minutes is None:
        return "never"
    if minutes < 120:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h"
    return f"{minutes / 1440:.1f} days"


def to_markdown(lines):
    """The digest's lines as Markdown: a line ending in ":" at the left margin is a `## ` heading, an indented line
    (with or without its "- ") a bullet, a line indented twice a nested bullet, and any other line a paragraph."""
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
        elif not line.startswith(" ") and stripped.endswith(":") and not stripped.startswith(("- ", "**")):
            out += [f"## {stripped[:-1]}", ""]
        elif line.startswith("    "):
            out.append(f"  - {stripped[2:] if stripped.startswith('- ') else stripped}")
        elif line.startswith("  "):
            out.append(f"- {stripped[2:] if stripped.startswith('- ') else stripped}")
        else:
            out.append(stripped)
    return out


def build_digest(day, freshness, groups, findings, wqdata, incidents=None, traffic=None, recoveries=None,
                 dashboard_url="https://welldash.mcmaster.ca/", quiet_kinds=None):
    """(subject, body) of the digest; the body is Markdown (scripts/daily_digest.py also sends it as HTML).

    freshness: assess_freshness()'s report. groups: {group: {"rows", "series", "timestamps", "gaps"}} for the
    last 24 h of the live series. findings: anomaly strings. wqdata: {"error"} or {"power_min", "power_max", "power_readings",
    "last_point", "last_point_age_minutes", optional "note"} or None when skipped. incidents: the open email alerts
    (utils/alert_state.alerts_report()["open"]), {"error": ...} if they couldn't be read, or None to leave them out.
    traffic: utils/traffic.summarize_traffic() of yesterday, {"error": ...}, or None to leave it out.
    recoveries: alerts cleared in the last 24 h (utils/alert_state.recent_recoveries()), {"error": ...}, or None.
    quiet_kinds: ALERT_QUIET_KINDS (Settings.quiet_kinds); None is the default.
    """
    # Here, not at the top: utils.alerts imports this module.
    from utils.alerts import DEFAULT_QUIET_KINDS, RECOVERED_AS, Settings, is_quiet, status
    quiet = Settings(quiet_kinds=DEFAULT_QUIET_KINDS if quiet_kinds is None else quiet_kinds)

    def unsent(r):
        # A recovery not emailed yet: a quiet kind's waits for the next email; any other's is being retried.
        return ". Not emailed yet (low priority)" if is_quiet(SimpleNamespace(**r), quiet) else ". Email pending"

    now = datetime.fromisoformat(freshness["checked_at"])
    stale = freshness["stale"]
    expected_per_series = int(timedelta(hours=24) / INTERVAL)
    problems = len(stale) + len(findings) + (1 if wqdata and wqdata.get("error") else 0)
    subject = f"[WELL] Daily digest {day}: " + ("all OK" if not problems else f"{problems} to check")
    lines = [f"WELL dashboard daily digest for the 24 h before {when(now)} (Toronto time).", ""]

    if incidents is not None:
        lines.append("Open alerts (each was emailed when it began):")
        if isinstance(incidents, dict):
            lines.append(f"  could not be read: {incidents.get('error')}")
        else:
            lines += [f"  **{what(i['key'])}**: {status(SimpleNamespace(**i), now)}. {since(i['started_at'], now)}"
                      for i in incidents] or ["  none"]
        lines.append("")

    if recoveries is not None:
        lines.append("Alerts recovered in the last 24 h:")
        if isinstance(recoveries, dict):
            lines.append(f"  could not be read: {recoveries.get('error')}")
        else:
            lines += [f"  **{what(r['key'])}**: {RECOVERED_AS.get(r['kind'], 'recovered')}. "
                      f"{span(r['started_at'], r['resolved_at'])}"
                      + ("" if r["recovery_emailed"] else unsent(r))
                      for r in recoveries] or ["  none"]
        lines.append("")

    lines.append("Stale series (newest reading older than its limit):")
    lines += [f"  - {series_label(s['station_id'], s['measurement_type'])}: newest {when_local(s['newest'])} "
              f"({fmt_age(s['age_minutes'])} ago; limit {s['max_age_hours']:g} h)" for s in stale] or ["  none"]
    lines.append("")

    lines.append("Implausible values:")
    lines += [f"  - {f}" for f in findings] or ["  none"]
    lines.append("")

    lines.append("Readings in the last 24 h (10-minute cadence):")
    for group, info in sorted(groups.items()):
        expected = info["series"] * expected_per_series
        note = ""
        quiet = freshness["groups"].get(group, {}).get("quiet_hours")
        if quiet:
            note = f"; the device is usually silent {quiet.replace('-', ':00 to ')}:00, so fewer is normal"
        lines.append(f"  {group}: {info['rows']} rows of {expected} expected ({info['series']} series), "
                     f"{len(info['timestamps'])} of {expected_per_series} time slots{note}")
        for start, end in info["gaps"]:
            minutes = int((end - start).total_seconds() // 60)
            lines.append(f"    gap {when_local(start)} → {when_local(end)} ({fmt_age(minutes)})")
    lines.append("")

    lines.append("WQData device:")
    if wqdata is None:
        lines.append("  not checked")
    elif wqdata.get("error"):
        lines.append(f"  request failed: {wqdata['error']}")
    else:
        if wqdata.get("power_min") is None:
            lines.append("  primary power: no readings in the last 24 h")
        else:
            lines.append(f"  primary power: {wqdata['power_min']:g} to {wqdata['power_max']:g} V "
                         f"over {wqdata['power_readings']} readings")
        if wqdata.get("last_point"):
            lines.append(f"  last contact (newest data point): {when_local(wqdata['last_point'])} "
                         f"({fmt_age(wqdata['last_point_age_minutes'])} ago)")
        else:
            lines.append("  last contact: no data points in the last 24 h")
        if wqdata.get("note"):
            lines.append(f"  note: {wqdata['note']}")
    lines.append("")

    if traffic is not None:
        lines += traffic_lines(traffic, EST_TZ) + [""]

    lines.append("Newest reading per series:")
    for group, info in sorted(freshness["groups"].items()):
        lines.append(f"  {group} (limit {info['max_age_hours']:g} h"
                     + (f", quiet {info['quiet_hours']}" if info["quiet_hours"] else "") + "):")
        for s in info["series"]:
            lines.append(f"    {series_label(s['station_id'], s['measurement_type'])}: {when_local(s['newest'])} "
                         f"({fmt_age(s['age_minutes'])} ago){'' if s['status'] == 'ok' else ', ' + s['status']}")
    lines = to_markdown(lines) + [""] + footer(dashboard_url)
    return subject, "\n".join(lines) + "\n"
