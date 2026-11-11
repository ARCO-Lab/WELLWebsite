# Site time (America/Toronto) helpers. est_now/est_after/est_passed are for export job times, which are still
# stored as naive site wall-clock time (export_jobs); sensor readings are stored as instants (see below).
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


# Sensor readings (sensor_measurements.recorded_at) are stored as real instants (timestamptz) since migration 0002;
# the helpers below convert between those instants and the site's wall clock, which the API and the CSV files show.
UTC = timezone.utc


def site_to_utc(local: datetime, fold: int = 0) -> datetime:
    """The instant of a naive site (Toronto) wall time. In the hour repeated when clocks fall back, fold=0 is the
    first occurrence (EDT) and fold=1 the second (EST); a time skipped when clocks spring forward is read with the
    offset before the change (02:30 -> 03:30 EDT), as PostgreSQL does."""
    return local.replace(tzinfo=EST_TZ, fold=fold).astimezone(UTC)


def as_utc(ts: datetime) -> datetime:
    """An aware datetime in UTC. A naive one is taken as site wall time, the meaning naive times had before
    recorded_at held instants, so a caller that still passes one gets what it meant."""
    return ts.astimezone(UTC) if ts.tzinfo else site_to_utc(ts)


def site_wall_time(ts: datetime) -> datetime:
    """An instant as naive site wall-clock time: the format the API and the CSV downloads have always used.
    Both copies of the repeated fall-back hour read the same here; keep the instant where they must stay apart."""
    return as_utc(ts).astimezone(EST_TZ).replace(tzinfo=None)


def parse_instant(value: str) -> datetime:
    """An ISO time from a request as an aware UTC datetime: with an offset (the dashboard sends ...Z) it is that
    instant; without one it is site wall time, as before."""
    return as_utc(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))
