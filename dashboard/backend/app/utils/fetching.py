# Time windows and paging for the vendor API fetches. Pure functions: no network or database.
#
# LI-COR (HOBOlink) returns at most 100,000 records per response and sets "max_results": true when
# it cut the response off. It also rejects start dates more than a year back. So we ask for at most
# a week at a time (about 35,000 records for this station) and split any window that still comes
# back capped. Without this, long requests silently lost whole sensors.
import datetime as dt
from typing import Callable, Iterator

MAX_DAYS = 364                       # LI-COR rejects start dates more than a year back
WINDOW = dt.timedelta(days=7)
MIN_WINDOW = dt.timedelta(hours=1)   # a capped 1-hour window means something else is wrong
OVERLAP = dt.timedelta(hours=1)      # re-read the last hour each run to catch readings that arrive late
RUN_LOOKBACK = dt.timedelta(days=14) # the 10-minute ingestion never looks further back than this;
                                     # older gaps are found and filled by scripts/licor_backfill.py
FMT = "%Y-%m-%d %H:%M:%S"
UTC = dt.timezone.utc

Page = tuple[list, bool]             # (records, response was capped)


def windows(start: dt.datetime, end: dt.datetime, size: dt.timedelta = WINDOW) -> Iterator[tuple[dt.datetime, dt.datetime]]:
    """Consecutive [start, end) windows of at most `size`."""
    cur = start
    while cur < end:
        nxt = min(cur + size, end)
        yield cur, nxt
        cur = nxt


def fetch_window(get_page: Callable[[dt.datetime, dt.datetime], Page], start: dt.datetime, end: dt.datetime,
                 stats=None) -> list:
    """All records for [start, end), halving the window for as long as the response comes back capped."""
    records, capped = get_page(start, end)
    if not capped:
        return records
    if stats is not None:
        stats["split"] += 1
    if end - start <= MIN_WINDOW:
        raise RuntimeError(f"LI-COR still caps a {end - start} window starting {start:%Y-%m-%d %H:%M} UTC")
    mid = start + (end - start) / 2
    return fetch_window(get_page, start, mid, stats) + fetch_window(get_page, mid, end, stats)


def fetch_range(get_page: Callable[[dt.datetime, dt.datetime], Page], start: dt.datetime, end: dt.datetime,
                stats=None) -> list:
    """All records for [start, end), one window at a time."""
    records = []
    for w0, w1 in windows(start, end):
        records.extend(fetch_window(get_page, w0, w1, stats))
    return records


def to_local(ts: dt.datetime, tz) -> dt.datetime:
    """recorded_at is stored as naive wall-clock time in the database session's time zone."""
    return ts.astimezone(tz).replace(tzinfo=None) if ts.tzinfo else ts


def start_from_newest(newest_local: dt.datetime | None, tz, first_start: dt.datetime,
                      overlap: dt.timedelta = OVERLAP) -> dt.datetime:
    """UTC time to fetch from: the newest stored reading (naive local time) minus `overlap`,
    or `first_start` when nothing is stored yet."""
    if newest_local is None:
        return first_start
    return newest_local.replace(tzinfo=tz).astimezone(UTC) - overlap
