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
