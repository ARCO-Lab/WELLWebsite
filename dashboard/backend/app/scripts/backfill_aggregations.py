# Backfill aggregation tables from raw sensor measurements.

import argparse
import pathlib
import sys
from datetime import datetime

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from utils.aggregation import backfill_aggregations


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid datetime format: {value}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill sensor aggregation tables")
    parser.add_argument("--start", type=_parse_dt, default=None, help="ISO datetime, e.g. 2024-01-01T00:00:00")
    parser.add_argument("--end", type=_parse_dt, default=None, help="ISO datetime, e.g. 2026-03-29T23:59:59")
    parser.add_argument(
        "--bucket-types",
        type=str,
        default="30min,1hour,3hour,6hour,12hour,24hour,1week",
        help="Comma-separated bucket types",
    )

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        start_time = args.start
        end_time = args.end

        if start_time is None:
            earliest = db.session.query(db.func.min(SensorMeasurement.recorded_at)).scalar()
            start_time = earliest or datetime.utcnow()

        if end_time is None:
            end_time = datetime.utcnow()

        bucket_types = [item.strip() for item in args.bucket_types.split(",") if item.strip()]

        print(f"[Backfill] start={start_time} end={end_time} buckets={bucket_types}")
        backfill_aggregations(start_time, end_time, bucket_types=bucket_types)
        print("[Backfill] complete")


if __name__ == "__main__":
    main()
