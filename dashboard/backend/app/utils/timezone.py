from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EST_TZ = ZoneInfo("America/Toronto")

# The years a request's start and end may fall in. There are no readings outside them, and near datetime's limits
# (year 1 or 9999) adding a tile or a second to a time overflows, which was a 500.
FIRST_YEAR, LAST_YEAR = 1970, 2100


def check_site_years(*times: datetime) -> None:
    """ValueError unless every time falls in FIRST_YEAR to LAST_YEAR."""
    if any(not FIRST_YEAR <= t.year <= LAST_YEAR for t in times):
        raise ValueError(f"Dates must be between {FIRST_YEAR} and {LAST_YEAR}")


def est_now() -> datetime:
    # Store as naive datetime in local EST/EDT wall time to match existing DB column types.
    return datetime.now(EST_TZ).replace(tzinfo=None)


def est_after(minutes: float, now_utc: datetime = None) -> datetime:
    """The naive local wall time `minutes` of real time from now (or from `now_utc`).

    `est_now() + timedelta(...)` adds to the wall clock, so across a DST change it is off by an hour;
    this adds in UTC and converts back.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    return (now_utc + timedelta(minutes=minutes)).astimezone(EST_TZ).replace(tzinfo=None)


def est_passed(wall_time: datetime, now_utc: datetime = None) -> bool:
    """Whether a naive local wall time (as est_now()/est_after() store them) is in the past, in real time.

    Naive wall times can't be compared directly: in the hour repeated when clocks fall back, an expiry 60 minutes
    away can read the same as the current time. An ambiguous time is read as the later of its two instants, so a
    download window is never cut short. (Compared in UTC because Python ignores `fold` within one tzinfo.)
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc > wall_time.replace(tzinfo=EST_TZ, fold=1).astimezone(timezone.utc)


def site_range(start: str, end: str):
    """ISO start and end times from a request as naive local wall times, to compare with the naive recorded_at
    columns (the way /api/series reads its range).

    A time with an offset ("...Z", "...-04:00") is a real instant and is converted to America/Toronto; one without
    is taken as local wall time already. Bound as aware values instead, PostgreSQL would read recorded_at in the
    session's TimeZone, so the answer would depend on a database setting (SQLite would drop the offset). When both
    are instants, their wall times can run backwards inside the hour repeated when clocks fall back (05:30Z is
    01:30 EDT, 06:10Z is 01:10 EST), so the two are put in the instants' order: forwards for a range, backwards
    (matching nothing, as a backwards range of naive times does) when end is before start.
    Raises ValueError for text that isn't an ISO time or a year outside FIRST_YEAR to LAST_YEAR, and OverflowError
    for one with no local time (e.g. 0001-01-01T00:00+05:00).
    """
    start_in, end_in = (datetime.fromisoformat(v.replace("Z", "+00:00")) for v in (start, end))
    start_dt, end_dt = (v.astimezone(EST_TZ).replace(tzinfo=None) if v.tzinfo else v for v in (start_in, end_in))
    check_site_years(start_dt, end_dt)
    if start_in.tzinfo and end_in.tzinfo:
        low, high = min(start_dt, end_dt), max(start_dt, end_dt)
        return (low, high) if start_in <= end_in else (high, low)
    return start_dt, end_dt
