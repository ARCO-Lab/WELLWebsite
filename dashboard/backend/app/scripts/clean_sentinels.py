"""Find, and optionally delete, stored "no reading" sentinel values in sensor_measurements.

Why this exists: vendors can report a missing reading as a huge negative number (WQData sent -100000 for every
Quality measurement on 2026-06-12 11:10). Ingestion stored those as real readings until utils/parsers.reading_value
learned to skip them, and a single one pulls a chart's average thousands of units down. /api/series already leaves
them out; this script removes the rows themselves, so exports and anything else reading the table don't see them.

Run it from the backend app directory (/app/app inside the containers):
    python scripts/clean_sentinels.py            # same as --check: count them, change nothing
    python scripts/clean_sentinels.py --check    # counts per group, measurement and local date
    python scripts/clean_sentinels.py --apply    # back the rows up to a CSV, then delete them

--apply first writes every row it will delete (all columns, id included) to logs/sentinels-<timestamp>.csv,
readable by the file's owner only, then deletes exactly those ids in one transaction. If the backup can't be
written, or the delete doesn't remove exactly the rows backed up, nothing is deleted. To undo, insert the CSV's
rows back (e.g. psql \\copy sensor_measurements(id,station_id,group_type,measurement_type,value,unit,recorded_at)
FROM 'file.csv' CSV HEADER).

The backup is owned by the user the script runs as: root in the backend image, which sets no USER. In the worker
container logs/ is the host's dashboard/backend/app/logs, so on the host the file is root's and mode 600: read or
copy it with sudo, or through the container (docker compose exec -w /app/app worker
cat logs/sentinels-<timestamp>.csv).

A sentinel is any value at or below utils/parsers.SENTINEL_MAX (-99999); no sensor here reads anywhere near that.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import pathlib
import sys

APP_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from sqlalchemy import bindparam, text  # noqa: E402

from utils.parsers import SENTINEL_MAX  # noqa: E402

COLUMNS = ("id", "station_id", "group_type", "measurement_type", "value", "unit", "recorded_at")

COUNT_SQL = text("""
SELECT group_type, measurement_type, CAST(recorded_at AS DATE) AS day, count(*) AS n
FROM sensor_measurements WHERE value <= :s
GROUP BY group_type, measurement_type, CAST(recorded_at AS DATE)
ORDER BY day, group_type, measurement_type
""")
ROWS_SQL = text(f"SELECT {', '.join(COLUMNS)} FROM sensor_measurements WHERE value <= :s ORDER BY id")
DELETE_SQL = text("DELETE FROM sensor_measurements WHERE id IN :ids AND value <= :s").bindparams(
    bindparam("ids", expanding=True))


def counts(conn):
    """[(group_type, measurement_type, local date, rows)] of the sentinel values stored."""
    return [tuple(r) for r in conn.execute(COUNT_SQL, {"s": SENTINEL_MAX}).fetchall()]


def write_backup(rows, path):
    """Write the rows to a new CSV only its owner can read (umask 077), and flush it to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    old = os.umask(0o077)
    try:
        with open(path, "x", newline="", encoding="utf-8") as f:   # "x": never overwrite an earlier backup
            w = csv.writer(f)
            w.writerow(COLUMNS)
            for r in rows:
                w.writerow([v.isoformat(sep=" ") if isinstance(v, dt.datetime) else v for v in r])
            f.flush()
            os.fsync(f.fileno())
    finally:
        os.umask(old)


def apply(engine, logs_dir, now=None):
    """Back up and delete every sentinel row in one transaction. Returns (rows deleted, backup path or None)."""
    stamp = (now or dt.datetime.now()).strftime("%Y%m%dT%H%M%S")
    with engine.begin() as conn:   # commits at the end, rolls back on any exception
        rows = [tuple(r) for r in conn.execute(ROWS_SQL, {"s": SENTINEL_MAX}).fetchall()]
        if not rows:
            return 0, None
        path = pathlib.Path(logs_dir) / f"sentinels-{stamp}.csv"
        write_backup(rows, path)
        deleted = conn.execute(DELETE_SQL, {"ids": [r[0] for r in rows], "s": SENTINEL_MAX}).rowcount
        if deleted != len(rows):
            raise RuntimeError(f"deleted {deleted} rows but backed up {len(rows)}; rolled back, nothing deleted")
    return deleted, path


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=f"Find (and with --apply delete) values <= {SENTINEL_MAX}.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="count them and change nothing (the default)")
    mode.add_argument("--apply", action="store_true", help="back them up to logs/ as CSV, then delete them")
    return ap.parse_args(argv)


def main(argv=None, engine=None, logs_dir=None) -> int:
    args = parse_args(argv)
    if engine is None:
        from db.database import db
        from server import create_app
        app = create_app()
        with app.app_context():
            return main(argv, db.engine, logs_dir)

    with engine.connect() as conn:
        found = counts(conn)
    total = sum(n for *_, n in found)
    print(f"{total} stored value(s) at or below {SENTINEL_MAX}")
    for group, measurement, day, n in found:
        print(f"  {day}  {group:<8} {measurement:<20} {n}")
    if not args.apply or not total:
        if total:
            print("Nothing changed. Run with --apply to back these rows up to logs/ and delete them.")
        return 0

    deleted, path = apply(engine, logs_dir or APP_DIR / "logs")
    print(f"Deleted {deleted} row(s); backup: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
