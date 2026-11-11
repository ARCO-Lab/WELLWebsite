"""Data freshness rules shared by GET /health/data and scripts/daily_digest.py. Pure: no database or network.

A series is one (station_id, measurement_type) pair. It is stale when its newest reading is older than its
group's limit. All limits come from the environment, so they can be tuned without a code change:

  HEALTH_MAX_AGE_HOURS            limit for every group without its own (default 3)
  HEALTH_MAX_AGE_HOURS_<GROUP>    limit for one group, e.g. HEALTH_MAX_AGE_HOURS_QUALITY=3
  HEALTH_QUIET_HOURS_<GROUP>      local hours "START-END" when the group's device is known to go silent
                                  (default 18-12 for Quality, none for the others; "off" disables it)
  HEALTH_EXCLUDED_SERIES          series never reported stale: "station:measurement" or "station:*",
                                  comma-separated (default 2577535:*, Logger 5, which stopped in 2025)

During a group's quiet hours a series counts as fresh if it was fresh when the quiet hours began, so a device
that stops for the night isn't reported, but one that stopped in the afternoon still is.
"""
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from utils.timezone import EST_TZ

DEFAULT_MAX_AGE_HOURS = 3.0
# LI-COR uploads about hourly, so Weather and Logger readings are up to ~1 h old when they arrive; 3 h means
# two missed uploads. WQData reports every 10 min during the day but is usually silent from the evening to
# mid-morning (Oct-Nov 2026: last reading between 18:10 and 22:30, first between 08:20 and 11:30).
DEFAULT_QUIET_HOURS = {"Quality": "18-12"}
DEFAULT_EXCLUDED_SERIES = "2577535:*"


@dataclass(frozen=True)
class GroupLimit:
    max_age: timedelta
    quiet_hours: Optional[tuple]   # (start_hour, end_hour) in site time, or None


def env_key(group):
    """The env-var suffix for a group: "Quality" -> "QUALITY"."""
    return re.sub(r"[^A-Z0-9]+", "_", str(group).upper()).strip("_")


def parse_hours(text, name):
    """A positive number of hours, e.g. "3" or "1.5". ValueError naming the variable otherwise."""
    try:
        hours = float(str(text).strip())
    except ValueError:
        raise ValueError(f"{name} must be a number of hours, got {text!r}") from None
    if not hours > 0 or hours == float("inf"):
        raise ValueError(f"{name} must be more than 0 hours, got {text!r}")
    return hours


def parse_quiet_hours(text, name="quiet hours"):
    """(start_hour, end_hour) from "START-END" (whole hours 0-23, may wrap past midnight), or None for
    "", "off" or "none"."""
    text = (text or "").strip().lower()
    if text in ("", "off", "none"):
        return None
    match = re.fullmatch(r"(\d{1,2})\s*-\s*(\d{1,2})", text)
    if not match:
        raise ValueError(f"{name} must look like 18-12 (start and end hour) or off, got {text!r}")
    start, end = int(match.group(1)), int(match.group(2))
    if not (0 <= start <= 23 and 0 <= end <= 23) or start == end:
        raise ValueError(f"{name} must be two different hours from 0 to 23, got {text!r}")
    return start, end


def group_limit(group, env=None):
    """The freshness limit for a group, read from the environment (see the module docstring)."""
    env = os.environ if env is None else env
    key = env_key(group)
    default = parse_hours(env.get("HEALTH_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS), "HEALTH_MAX_AGE_HOURS")
    hours_name = f"HEALTH_MAX_AGE_HOURS_{key}"
    hours = parse_hours(env[hours_name], hours_name) if env.get(hours_name, "").strip() else default
    quiet_name = f"HEALTH_QUIET_HOURS_{key}"
    quiet = parse_quiet_hours(env.get(quiet_name, DEFAULT_QUIET_HOURS.get(group, "")), quiet_name)
    return GroupLimit(timedelta(hours=hours), quiet)


def parse_excluded_series(text):
    """{(station_id, measurement_type or "*")} from "station:measurement,station:*". Blank entries are ignored."""
    excluded = set()
    for entry in (text or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        station, sep, measurement = entry.partition(":")
        if not sep or not station.strip() or not measurement.strip():
            raise ValueError(f"HEALTH_EXCLUDED_SERIES entries must look like 2577535:* or "
                             f"2577535:Water Temperature, got {entry!r}")
        excluded.add((station.strip(), measurement.strip()))
    return excluded


def excluded_series(env=None):
    env = os.environ if env is None else env
    return parse_excluded_series(env.get("HEALTH_EXCLUDED_SERIES", DEFAULT_EXCLUDED_SERIES))


def is_excluded(station_id, measurement_type, excluded):
    return (str(station_id), "*") in excluded or (str(station_id), measurement_type) in excluded


def in_quiet_hours(hour, quiet):
    if not quiet:
        return False
    start, end = quiet
    return start <= hour < end if start < end else hour >= start or hour < end


def oldest_fresh(now_local, limit):
    """The oldest newest-reading time (aware, UTC) that still counts as fresh at `now_local` (aware, site time).
    The limit is subtracted in UTC, so it is real elapsed time even across a DST change."""
    since = now_local
    if in_quiet_hours(now_local.hour, limit.quiet_hours):
        # Start of the current quiet hours: today, or yesterday if they began before midnight.
        since = now_local.replace(hour=limit.quiet_hours[0], minute=0, second=0, microsecond=0)
        if since > now_local:
            since -= timedelta(days=1)
    return since.astimezone(timezone.utc) - limit.max_age


def as_site_time(recorded_at):
    """recorded_at is stored as naive site (Toronto) wall-clock time; make it aware for real-time arithmetic."""
    if isinstance(recorded_at, str):
        recorded_at = datetime.fromisoformat(recorded_at)
    return recorded_at if recorded_at.tzinfo else recorded_at.replace(tzinfo=EST_TZ)


def age_minutes(recorded_at, now):
    # In UTC: Python subtracts two datetimes with the same tzinfo as wall-clock times, ignoring DST.
    return int((now.astimezone(timezone.utc) - as_site_time(recorded_at).astimezone(timezone.utc)).total_seconds() // 60)


def assess_freshness(latest, now, env=None):
    """The /health/data report for `latest` (the rows of /api/latest: station_id, group_type, measurement_type,
    recorded_at) at `now` (an aware datetime).

    {"status": "ok" | "stale", "checked_at", "stale": [...], "groups": {group: {...}}}. A group with no series
    that is checked (all excluded) is reported but can't make the result stale. Raises ValueError for a bad
    setting, naming it.
    """
    env = os.environ if env is None else env
    now_local = now.astimezone(EST_TZ)
    excluded = excluded_series(env)
    groups, stale = {}, []
    for row in latest:
        group = row.get("group_type") or "Unknown"
        if group not in groups:
            limit = group_limit(group, env)
            groups[group] = {
                "newest": None, "age_minutes": None,
                "max_age_hours": limit.max_age.total_seconds() / 3600,
                "quiet_hours": "{}-{}".format(*limit.quiet_hours) if limit.quiet_hours else None,
                "in_quiet_hours": in_quiet_hours(now_local.hour, limit.quiet_hours),
                "oldest_fresh": oldest_fresh(now_local, limit),
                "series": [],
            }
        info = groups[group]
        newest = as_site_time(row["recorded_at"])
        if is_excluded(row["station_id"], row["measurement_type"], excluded):
            status = "excluded"
        elif newest.astimezone(timezone.utc) < info["oldest_fresh"]:
            status = "stale"
        else:
            status = "ok"
        series = {
            "station_id": str(row["station_id"]),
            "measurement_type": row["measurement_type"],
            "newest": newest.replace(tzinfo=None).isoformat(),
            "age_minutes": age_minutes(newest, now),
            "status": status,
        }
        info["series"].append(series)
        if status == "stale":
            stale.append({"group": group, **series, "max_age_hours": info["max_age_hours"]})
        if info["newest"] is None or series["newest"] > info["newest"]:
            info["newest"], info["age_minutes"] = series["newest"], series["age_minutes"]
    for info in groups.values():
        info["oldest_fresh"] = info["oldest_fresh"].astimezone(EST_TZ).replace(tzinfo=None).isoformat(timespec="seconds")
    checked = [s for info in groups.values() for s in info["series"] if s["status"] != "excluded"]
    return {
        "status": "stale" if stale or not checked else "ok",
        "checked_at": now_local.isoformat(timespec="seconds"),
        "stale": stale,
        "groups": groups,
        **({} if checked else {"error": "no series to check: the table is empty or every series is excluded"}),
    }
