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

WQData throttles bursts, so requests are paced PAUSE seconds apart (a day is one request of about
2,700 values; longer responses are paged). Inserts use ON CONFLICT DO NOTHING, so running it twice is
harmless. The ids of inserted rows are saved to logs/wqdata-backfill-<timestamp>.ids; to undo a run,
delete those ids from sensor_measurements.
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
RETRY_STATUSES = {429, 500, 502, 503, 504}
ATTEMPTS = 4


class WQDataError(RuntimeError):
    """A failed WQData request. The message never contains the request URL: it carries the API key."""


class WQData:
    """Requests to WQData's data endpoint, paced PAUSE seconds apart, retried on throttling and server errors."""

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
            except requests.RequestException as e:
                problem = type(e).__name__   # its message holds the URL, and with it the key
            else:
                if r.status_code == 200:
                    try:
                        return r.json()
                    except ValueError:
                        raise WQDataError(f"WQData sent a response that isn't JSON for {frm} to {to} UTC") from None
                problem = f"HTTP {r.status_code}"
                if r.status_code not in RETRY_STATUSES:
                    break
            if attempt < ATTEMPTS - 1:
                self.sleep(10 * (attempt + 1))
        raise WQDataError(f"WQData request for {frm} to {to} UTC failed: {problem}")


def fetch_points(get_page, start: dt.datetime, end: dt.datetime) -> list:
    """Every WQData point in [start, end) (aware datetimes), following WQData's paging.

    When a response is cut off (about 5,000 values), it says info.more and gives the time of its last
    point; the next request starts at that point, not after it, so a point whose values were split
    between two pages is read whole. The repeated point is merged by quality_rows.
    """
    to = (end - dt.timedelta(seconds=1)).astimezone(UTC).strftime(FMT)
    frm = start.astimezone(UTC).strftime(FMT)
    points = []
    while True:
        body = get_page(frm, to)
        points.extend(body.get("data") or [])
        info = body.get("info") or {}
        if not info.get("more"):
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


def main(argv=None) -> int:
    args = parse_args(argv)
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert
    from zoneinfo import ZoneInfo
    from config import Config
    from db.database import db
    from db.models import SensorMeasurement
    from server import create_app
    from utils.parsers import quality_rows

    app = create_app()
    wq = WQData(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)
    station = str(Config.WQ_DEVICE_ID)
    table = SensorMeasurement.__table__
    ids_path = APP_DIR / "logs" / f"wqdata-backfill-{dt.datetime.now(UTC):%Y%m%dT%H%M%SZ}.ids"
    if not args.check:   # fail before writing anything if the ids file can't be created
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.touch()
    totals = dict(points=0, readings=0, stored=0, missing=0, inserted=0, extra=0, differ=0)
    gap_days = []

    with app.app_context():
        engine = db.engine
        with engine.connect() as c:
            tz = ZoneInfo(c.execute(text("show timezone")).scalar())
        end = (dt.datetime.now(UTC) - SETTLE).replace(second=0, microsecond=0)
        days = day_windows(end, args.days, tz)
        print(f"{'Checking' if args.check else 'Backfilling'} WQData device {station} for {days[0][0]} to "
              f"{days[-1][2]:%Y-%m-%d %H:%M} ({tz.key}, as stored), one request per day", flush=True)
        try:
            for day, lo, hi in days:
                points = fetch_points(wq.get_page, to_utc(lo, tz), to_utc(hi, tz))
                rows = {k: r for k, r in quality_rows(points, station, tz).items() if lo <= k[2] < hi}
                with engine.connect() as c:
                    stored = {(station, m, t): v for m, t, v in c.execute(text(
                        "select measurement_type, recorded_at, value from sensor_measurements "
                        "where station_id = :s and group_type = 'Quality' and recorded_at >= :lo and recorded_at < :hi"),
                        {"s": station, "lo": lo, "hi": hi})}
                missing, extra, differ = compare(rows, stored)
                inserted = []
                if missing and not args.check:
                    with engine.begin() as c:   # one transaction per day
                        for i in range(0, len(missing), 1000):
                            stmt = (insert(table).values(missing[i:i + 1000])
                                    .on_conflict_do_nothing(index_elements=KEY_COLUMNS).returning(table.c.id))
                            inserted.extend(r[0] for r in c.execute(stmt))
                        # Record the ids before the commit: if this write fails, the day is rolled back.
                        with open(ids_path, "a") as f:
                            f.writelines(f"{row_id}\n" for row_id in inserted)
                            f.flush()
                            os.fsync(f.fileno())
                n_points = len({k[2] for k in rows})
                for name, n in (("points", n_points), ("readings", len(rows)), ("stored", len(stored)),
                                ("missing", len(missing)), ("inserted", len(inserted)), ("extra", extra), ("differ", differ)):
                    totals[name] += n
                if missing:
                    gap_days.append(f"{day} ({len(missing)})")
                print(f"  {day}: {n_points:4} points, {len(rows):5} readings, {len(stored):5} stored, {len(missing):5} missing"
                      + ("" if args.check else f", {len(inserted):5} inserted")
                      + (f", {extra} stored but not at WQData" if extra else "")
                      + (f", {differ} stored with a different value" if differ else ""), flush=True)
        except WQDataError as e:
            print(f"[ERROR] {e}", flush=True)
            return 1

    if not args.check and not totals["inserted"]:
        ids_path.unlink(missing_ok=True)   # don't leave an empty ids file behind every run
    t = totals
    print(f"[INFO] WQData {'check' if args.check else 'backfill'}: {len(days)} days, {t['points']} points, "
          f"{t['readings']} readings, {t['missing']} missing" + (f" on {', '.join(gap_days)}" if gap_days else "")
          + ("" if args.check else f", {t['inserted']} inserted" + (f" (ids in {ids_path})" if t["inserted"] else ""))
          + f", {t['extra']} stored but not at WQData, values differ on {t['differ']} of {t['stored'] - t['extra']} compared"
          + f" | {wq.requests} requests", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
