from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EST_TZ = ZoneInfo("America/Toronto")


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
