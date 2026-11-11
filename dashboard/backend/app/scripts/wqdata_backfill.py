"""Find and fill gaps in the water quality (WQData) data.

Why this exists: the 10-minute ingestion only re-reads WQData from an hour before its newest stored
reading. A reading the device uploads later than that, or one from a run that failed, is never read
again. This script compares WQData with the database one local day at a time and inserts whatever
WQData has that the database doesn't.

Run it from the backend app directory (/app/app inside the containers):
    python scripts/wqdata_backfill.py --check     # report missing readings per day, writes nothing
    python scripts/wqdata_backfill.py             # insert the missing readings
Options:
    --days N     how many days to look back, today included (default 14)

The last hour is left out: the ingestion still re-reads it. Rows are built with the same function as
the ingestion (utils/parsers.py quality_rows), so values, units and times are identical, and points
that only carry power or diagnostic values are skipped the same way. Stored times are local
wall-clock times, so on the night clocks go back the repeated hour's readings share their times with
the first one and can't be stored; they aren't counted as missing. --check also compares the values
of readings already stored.

WQData limits requests per hour (HTTP 429 "Request exceeds hourly limit"), and the limit is shared with
the 10-minute ingestion. So days are fetched WINDOW_DAYS at a time (a full day is about 2,700 values
and a response holds about 5,000-7,000, so a week takes 3-4 paged requests; see fetch_points), a 429
stops the run at once instead of spending more of the quota on retries, and requests are paced PAUSE
seconds apart because WQData also throttles bursts. Network errors, timeouts and 5xx responses are
retried. Each day is still compared and inserted on its own. Inserts use ON CONFLICT DO NOTHING, so
running it twice is harmless. The ids of inserted rows are saved to logs/wqdata-backfill-<timestamp>.ids;
to undo a run, delete those ids from sensor_measurements.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import pathlib
import sys
import time

import requests

APP_DIR = (pathlib.Path(__file__).resolve().parents[1]
           if pathlib.Path(globals().get("__file__", "")).is_file() else pathlib.Path.cwd())   # cwd when piped in on stdin
sys.path.insert(0, str(APP_DIR))

from utils.fetching import FMT, UTC, to_local  # noqa: E402

KEY_COLUMNS = ["station_id", "measurement_type", "recorded_at"]   # the table's unique key
PAUSE = 3.5                       # seconds between WQData requests; it throttles bursts
SETTLE = dt.timedelta(hours=1)    # the ingestion re-reads the last hour itself
WINDOW_DAYS = 7                   # days fetched per (paged) request range
RETRY_STATUSES = {500, 502, 503, 504}   # not 429: that's the hourly quota, and retries would spend more of it
ATTEMPTS = 4


class WQDataError(RuntimeError):
    """A failed WQData request. The message never contains the request URL: it carries the API key."""


class WQData:
    """Requests to WQData's data endpoint, paced PAUSE seconds apart, retried on network errors, timeouts
    and server errors. A 429 (hourly quota used up) fails at once."""

    def __init__(self, api_url, api_key, device_id, get=requests.get, sleep=time.sleep, pause=PAUSE):
        self.url = f"{str(api_url).rstrip('/')}/devices/{device_id}/parameters/data"
        self.api_key, self.get, self.sleep, self.pause = api_key, get, sleep, pause
        self.requests = 0

    def get_page(self, frm: str, to: str) -> dict:
        """One response for UTC times `frm`..`to` ("%Y-%m-%d %H:%M:%S")."""
        problem = None
        for attempt in range(ATTEMPTS):
            if self.requests:
                self.sleep(self.pause)
            self.requests += 1
            try:
                r = self.get(self.url, params={"apiKey": self.api_key, "from": frm, "to": to}, timeout=(10, 120))
            except (requests.ConnectionError, requests.Timeout) as e:
                problem = type(e).__name__   # its message holds the URL, and with it the key
            except requests.RequestException as e:   # e.g. a malformed URL: retrying won't help
                problem = type(e).__name__
                break
            else:
                if r.status_code == 200:
                    try:
                        return r.json()
                    except ValueError:
                        raise WQDataError(f"WQData sent a response that isn't JSON for {frm} to {to} UTC") from None
                problem = f"HTTP {r.status_code}" + self.message(r)
                if r.status_code == 429:
                    problem += "; WQData's hourly request limit is used up (shared with the ingestion), try again later"
                if r.status_code not in RETRY_STATUSES:
                    break
            if attempt < ATTEMPTS - 1:
                self.sleep(10 * (attempt + 1))
        raise WQDataError(f"WQData request for {frm} to {to} UTC failed: {problem}")

    def message(self, response) -> str:
        """WQData's own error message, e.g. "Request exceeds hourly limit" with a 429, with the key scrubbed."""
        try:
            text = str(response.json().get("message") or "")
        except (ValueError, AttributeError):
            return ""
        if self.api_key:
            text = text.replace(str(self.api_key), "***")   # before shortening, so no part of the key is left
        return f" ({text[:200]})" if text else ""


def fetch_points(get_page, start: dt.datetime, end: dt.datetime) -> list:
    """Every WQData point in [start, end) (aware datetimes), following WQData's paging.

    A response cut off at about 5,000-7,000 values gives the time of its last point
    (info.lastDataPointTimestamp), and the next request starts at that point, not after it, so a point
    whose values were split between two pages is read whole (quality_rows merges the repeat). WQData's
    info.more isn't reliable on its own: a 14-day request ended with more=false three days early. So
    paging only stops when a response holds every value it says the range has (info.count >= info.total).
    """
    to = (end - dt.timedelta(seconds=1)).astimezone(UTC).strftime(FMT)
    frm = start.astimezone(UTC).strftime(FMT)
    points = []
    while True:
        body = get_page(frm, to)
        points.extend(body.get("data") or [])
        info = body.get("info") or {}
        count, total = info.get("count"), info.get("total")
        if not info.get("more") and (count is None or total is None or count >= total):
            return points
        last = info.get("lastDataPointTimestamp")
        if not last or last <= frm:   # same fixed format, so string order is time order
            raise WQDataError(f"WQData paging didn't advance past {frm} UTC")
        frm = last


def day_windows(end: dt.datetime, days: int, tz) -> list[tuple[dt.date, dt.datetime, dt.datetime]]:
    """The last `days` local days up to `end` (aware), oldest first, as (day, start, end) in naive local
    time, the way recorded_at is stored. The last day stops at `end`."""
    end_local = to_local(end, tz)
    last_day = (end_local - dt.timedelta(microseconds=1)).date()   # `end` at midnight closes the day before
    out = []
    for i in range(days - 1, -1, -1):
        lo = dt.datetime.combine(last_day - dt.timedelta(days=i), dt.time())
        out.append((lo.date(), lo, min(lo + dt.timedelta(days=1), end_local)))
    return out


def to_utc(local: dt.datetime, tz) -> dt.datetime:
    return local.replace(tzinfo=tz).astimezone(UTC)


def same_value(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return (math.isnan(a) and math.isnan(b)) or math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def compare(rows: dict, stored: dict) -> tuple[list, int, int]:
    """(rows WQData has that aren't stored, stored readings WQData doesn't have, stored readings whose value differs).
    Both dicts are keyed by the table's unique key; `stored` maps it to the stored value."""
    missing = [row for key, row in rows.items() if key not in stored]
    extra = sum(1 for key in stored if key not in rows)
    differ = sum(1 for key, row in rows.items() if key in stored and not same_value(stored[key], row["value"]))
    return missing, extra, differ


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Find and fill gaps in the water quality (WQData) data.")
    ap.add_argument("--check", action="store_true", help="report missing readings per day, write nothing")
    ap.add_argument("--days", type=int, default=14, help="days to look back, today included (default 14)")
    args = ap.parse_args(argv)
    if args.days < 1:
        ap.error("--days must be at least 1")
    return args


def backfill(days, tz, station, get_page, read_stored, insert_rows, ids_path, check, log=print, requests_made=None,
             window=WINDOW_DAYS) -> int:
    """Compare WQData with the database for each (day, start, end) in `days` and, unless `check`, insert
    what's missing. WQData is read `window` consecutive days at a time, to spend fewer requests of its
    hourly quota; the comparison, the inserts and their transactions stay per day.
    The database is reached through two functions, so this runs without one in tests:
      read_stored(lo, hi) -> {unique key: stored value} for the station's Quality rows in [lo, hi)
      insert_rows(rows, record_ids) -> ids of the rows inserted; it must call record_ids(ids) before it commits
    Returns the exit code: 1 if a WQData request failed, after reporting what was inserted until then."""
    from utils.parsers import quality_rows

    totals = dict(points=0, readings=0, stored=0, missing=0, inserted=0, extra=0, differ=0)
    gap_days, failed = [], None

    def record_ids(ids):
        with open(ids_path, "a") as f:
            f.writelines(f"{row_id}\n" for row_id in ids)
            f.flush()
            os.fsync(f.fileno())

    def by_day():
        """(day, lo, hi, that day's rows), fetching WQData `window` days at a time."""
        for i in range(0, len(days), window):
            chunk = days[i:i + window]
            points = fetch_points(get_page, to_utc(chunk[0][1], tz), to_utc(chunk[-1][2], tz))
            window_rows = quality_rows(points, station, tz)
            for day, lo, hi in chunk:
                yield day, lo, hi, {k: r for k, r in window_rows.items() if lo <= k[2] < hi}

    try:
        for day, lo, hi, rows in by_day():
            stored = read_stored(lo, hi)
            missing, extra, differ = compare(rows, stored)
            inserted = insert_rows(missing, record_ids) if missing and not check else []
            n_points = len({k[2] for k in rows})
            for name, n in (("points", n_points), ("readings", len(rows)), ("stored", len(stored)),
                            ("missing", len(missing)), ("inserted", len(inserted)), ("extra", extra), ("differ", differ)):
                totals[name] += n
            if missing:
                gap_days.append(f"{day} ({len(missing)})")
            log(f"  {day}: {n_points:4} points, {len(rows):5} readings, {len(stored):5} stored, {len(missing):5} missing"
                + ("" if check else f", {len(inserted):5} inserted")
                + (f", {extra} stored but not at WQData" if extra else "")
                + (f", {differ} stored with a different value" if differ else ""))
    except WQDataError as e:
        failed = e
        log(f"[ERROR] {e}")
    finally:
        if not check and not totals["inserted"]:
            ids_path.unlink(missing_ok=True)   # don't leave an empty ids file behind
    t = totals
    log(f"[{'ERROR' if failed else 'INFO'}] WQData {'check' if check else 'backfill'}"
        + (" stopped early" if failed else "") + f": {len(days)} days, {t['points']} points, "
        f"{t['readings']} readings, {t['missing']} missing" + (f" on {', '.join(gap_days)}" if gap_days else "")
        + ("" if check else f", {t['inserted']} inserted" + (f" (ids in {ids_path})" if t["inserted"] else ""))
        + f", {t['extra']} stored but not at WQData, values differ on {t['differ']} of {t['stored'] - t['extra']} compared"
        + (f" | {requests_made()} requests" if requests_made else ""))
    return 1 if failed else 0


def main(argv=None) -> int:
    args = parse_args(argv)
    from config import Config
    unset = [name for name in ("WQ_API_URL", "WQ_API_KEY", "WQ_DEVICE_ID") if not getattr(Config, name)]
    if unset:
        print(f"[ERROR] {', '.join(unset)} not set; WQData can't be read", flush=True)
        return 2
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert
    from zoneinfo import ZoneInfo
    from db.database import db
    from db.models import SensorMeasurement
    from server import create_app

    app = create_app()
    wq = WQData(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)
    station = str(Config.WQ_DEVICE_ID)
    table = SensorMeasurement.__table__
    ids_path = APP_DIR / "logs" / f"wqdata-backfill-{dt.datetime.now(UTC):%Y%m%dT%H%M%SZ}.ids"
    if not args.check:   # fail before writing anything if the ids file can't be created
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.touch()

    with app.app_context():
        engine = db.engine

        def read_stored(lo, hi):
            with engine.connect() as c:
                return {(station, m, t): v for m, t, v in c.execute(text(
                    "select measurement_type, recorded_at, value from sensor_measurements "
                    "where station_id = :s and group_type = 'Quality' and recorded_at >= :lo and recorded_at < :hi"),
                    {"s": station, "lo": lo, "hi": hi})}

        def insert_rows(rows, record_ids):
            ids = []
            with engine.begin() as c:   # one transaction per day
                for i in range(0, len(rows), 1000):
                    stmt = (insert(table).values(rows[i:i + 1000])
                            .on_conflict_do_nothing(index_elements=KEY_COLUMNS).returning(table.c.id))
                    ids.extend(r[0] for r in c.execute(stmt))
                record_ids(ids)   # before the commit: if this write fails, the day is rolled back
            return ids

        with engine.connect() as c:
            tz = ZoneInfo(c.execute(text("show timezone")).scalar())
        end = (dt.datetime.now(UTC) - SETTLE).replace(second=0, microsecond=0)
        days = day_windows(end, args.days, tz)
        print(f"{'Checking' if args.check else 'Backfilling'} WQData device {station} for {days[0][0]} to "
              f"{days[-1][2]:%Y-%m-%d %H:%M} ({tz.key}, as stored), reading WQData {WINDOW_DAYS} days at a time", flush=True)
        code = backfill(days, tz, station, wq.get_page, read_stored, insert_rows, ids_path, args.check,
                        log=lambda line: print(line, flush=True), requests_made=lambda: wq.requests)
    return code


if __name__ == "__main__":
    sys.exit(main())
