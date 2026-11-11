"""Find and fill gaps in the LI-COR (HOBOlink) sensor data.

Why this exists: LI-COR's API returns at most 100,000 records per request (the response says
"max_results": true when it was cut off) and only accepts start dates within the past 365 days.
A request that was too big silently lost whole sensors, and anything older than a year can never
be fetched again. This script compares LI-COR with the database, reading at most a week per
request, and inserts whatever is missing. It also catches what the 10-minute ingestion can't see,
such as a sensor that was absent from one response while the others came through.

Run it from the backend app directory (/app/app inside the containers):
    python scripts/licor_backfill.py --check     # report only, writes nothing
    python scripts/licor_backfill.py             # insert the missing rows
Options:
    --days N     how far back to look (default and maximum: 364)
    --groups G   Logger, Weather, or Logger,Weather (default: Logger,Weather)

Rows are parsed with the same functions as the regular ingestion (utils/parsers.py), so backfilled
rows are identical to rows the scheduler would have stored; --check also re-compares the values of
rows already stored. Inserts use ON CONFLICT DO NOTHING, so running it twice is harmless. The ids of
inserted rows are saved to logs/backfill-<timestamp>.ids; to undo a run, delete those ids from
sensor_measurements.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import os
import pathlib
import sys
import time

APP_DIR = (pathlib.Path(__file__).resolve().parents[1]
           if pathlib.Path(globals().get("__file__", "")).is_file() else pathlib.Path.cwd())   # cwd when piped in on stdin
sys.path.insert(0, str(APP_DIR))

from utils.fetching import MAX_DAYS, UTC, fetch_window, to_local, windows  # noqa: E402

KEY_COLUMNS = ["station_id", "measurement_type", "recorded_at"]   # the table's unique key


def spans(days: list[dt.date], min_len: int = 2) -> list[str]:
    """Collapse sorted dates into 'first..last' runs of at least `min_len` days."""
    out, run = [], []
    for d in days:
        if run and (d - run[-1]).days != 1:
            if len(run) >= min_len:
                out.append(f"{run[0]}..{run[-1]}")
            run = []
        run.append(d)
    if len(run) >= min_len:
        out.append(f"{run[0]}..{run[-1]}")
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Find and fill gaps in LI-COR sensor data.")
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    ap.add_argument("--days", type=int, default=MAX_DAYS, help=f"days to look back (max {MAX_DAYS})")
    ap.add_argument("--groups", default="Logger,Weather", help="Logger, Weather, or Logger,Weather")
    args = ap.parse_args(argv)
    args.days = max(1, min(args.days, MAX_DAYS))
    args.groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    if not args.groups or args.groups - {"Logger", "Weather"}:
        ap.error("--groups must be Logger, Weather, or Logger,Weather")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert
    from zoneinfo import ZoneInfo
    from api.services.weather import WeatherService
    from config import Config
    from db.database import db
    from db.models import SensorMeasurement
    from server import create_app
    from utils.parsers import licor_rows

    app = create_app()
    licor = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
    station = licor.get_logger_id()
    table = SensorMeasurement.__table__
    ids_path = APP_DIR / "logs" / f"backfill-{dt.datetime.now(UTC):%Y%m%dT%H%M%SZ}.ids"
    if not args.check:   # fail before writing anything if the ids file can't be created
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.touch()
    stats = collections.Counter()
    series = collections.defaultdict(collections.Counter)
    source_days = collections.defaultdict(set)
    biggest_diff, compared = 0.0, 0

    with app.app_context():
        engine = db.engine
        tz = ZoneInfo("America/Toronto")   # recorded_at is site wall-clock time, whatever the database's TimeZone
        end = dt.datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        start = end - dt.timedelta(days=args.days)
        print(f"{'Checking' if args.check else 'Backfilling'} {','.join(sorted(args.groups))} from {start:%Y-%m-%d %H:%M} UTC "
              f"to now, a week per request (stored times are {tz.key})", flush=True)

        for w0, w1 in windows(start, end):
            records = fetch_window(licor.get_page, w0, w1, stats)
            stats["windows"] += 1
            rows = licor_rows(records, args.groups, station, tz)
            with engine.connect() as c:
                stored = {(s, m, t): v for s, m, t, v in c.execute(text(
                    "select station_id, measurement_type, recorded_at, value from sensor_measurements "
                    "where group_type = any(:g) and recorded_at >= :lo and recorded_at < :hi"),
                    {"g": sorted(args.groups), "lo": to_local(w0, tz), "hi": to_local(w1, tz)})}
            missing = []
            for key, row in rows.items():
                s = series[key[:2]]
                s["at LI-COR"] += 1
                source_days[key[:2]].add(key[2].date())
                if key in stored:
                    compared += 1
                    biggest_diff = max(biggest_diff, abs((stored[key] or 0.0) - (row["value"] or 0.0)))
                else:
                    missing.append(row)
                    s["missing"] += 1
            for key in stored:
                series[key[:2]]["stored"] += 1
                if key not in rows:
                    series[key[:2]]["stored, not at LI-COR"] += 1

            inserted = []
            if missing and not args.check:
                with engine.begin() as c:   # one transaction per window
                    for i in range(0, len(missing), 1000):
                        stmt = (insert(table).values(missing[i:i + 1000])
                                .on_conflict_do_nothing(index_elements=KEY_COLUMNS)
                                .returning(table.c.id, table.c.station_id, table.c.measurement_type))
                        inserted.extend(c.execute(stmt).fetchall())
                    # Record the ids before the commit: if this write fails, the window is rolled back.
                    with open(ids_path, "a") as f:
                        f.writelines(f"{r[0]}\n" for r in inserted)
                        f.flush()
                        os.fsync(f.fileno())
                for _, s_id, m in inserted:
                    series[(s_id, m)]["inserted"] += 1
            print(f"  {w0:%Y-%m-%d} .. {w1:%Y-%m-%d}: {len(records):6} records, {len(rows):6} rows, {len(stored):6} stored, "
                  f"{len(missing):6} missing" + ("" if args.check else f", {len(inserted):6} inserted"), flush=True)
            time.sleep(1)

    first_day, last_day = to_local(start, tz).date() + dt.timedelta(days=1), to_local(end, tz).date() - dt.timedelta(days=1)
    all_days = [first_day + dt.timedelta(days=i) for i in range((last_day - first_day).days + 1)]
    cols = ["at LI-COR", "stored", "missing"] + ([] if args.check else ["inserted"]) + ["stored, not at LI-COR"]
    print("\nstation    measurement                " + "".join(f"{c:>23}" for c in cols) + "   days with nothing at LI-COR")
    for key in sorted(series):
        gaps = [d for d in all_days if d not in source_days[key]]
        print(f"{key[0]:10} {key[1]:26} " + "".join(f"{series[key][c]:>23}" for c in cols)
              + f"   {len(gaps)} {spans(gaps)[:3]}")
    total_missing = sum(s["missing"] for s in series.values())
    print(f"\nmissing rows: {total_missing}" + ("" if args.check else f", inserted: {sum(s['inserted'] for s in series.values())}")
          + f" | windows: {stats['windows']}, capped responses split: {stats['split']}"
          + f" | values re-checked on {compared} already-stored rows, largest difference: {biggest_diff:.3g}")
    if not args.check:
        print(f"inserted row ids: {ids_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
