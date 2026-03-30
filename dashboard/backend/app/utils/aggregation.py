# Aggregation utilities for sensor time-series data.
# Computes and maintains multi-interval aggregate tables from raw sensor_measurements.

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from db.database import db
from db.models import (
    SensorMeasurement,
    SensorMeasurementAgg30Min,
    SensorMeasurementAgg1Hour,
    SensorMeasurementAgg3Hour,
    SensorMeasurementAgg6Hour,
    SensorMeasurementAgg12Hour,
    SensorMeasurementAgg24Hour,
    SensorMeasurementAgg1Week,
)


BUCKET_CONFIG: Dict[str, Tuple[int, type]] = {
    "30min": (30, SensorMeasurementAgg30Min),
    "1hour": (60, SensorMeasurementAgg1Hour),
    "3hour": (180, SensorMeasurementAgg3Hour),
    "6hour": (360, SensorMeasurementAgg6Hour),
    "12hour": (720, SensorMeasurementAgg12Hour),
    "24hour": (1440, SensorMeasurementAgg24Hour),
    "1week": (10080, SensorMeasurementAgg1Week),
}


def _normalize_to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def round_to_bucket(dt: datetime, bucket_minutes: int) -> datetime:
    normalized = _normalize_to_utc_naive(dt)
    timestamp = int(normalized.timestamp())
    bucket_seconds = bucket_minutes * 60
    bucket_start_ts = (timestamp // bucket_seconds) * bucket_seconds
    return datetime.utcfromtimestamp(bucket_start_ts)


def compute_aggregates_for_bucket(rows: Iterable[SensorMeasurement]) -> Dict[str, Optional[float]]:
    rows_list = list(rows)
    values = [row.value for row in rows_list if row.value is not None]
    null_count = len(rows_list) - len(values)

    if not rows_list:
        return {
            "value_min": None,
            "value_max": None,
            "value_avg": None,
            "value_sum": None,
            "value_count": 0,
            "has_nulls": False,
        }

    if not values:
        return {
            "value_min": None,
            "value_max": None,
            "value_avg": None,
            "value_sum": None,
            "value_count": 0,
            "has_nulls": True,
        }

    return {
        "value_min": min(values),
        "value_max": max(values),
        "value_avg": sum(values) / len(values),
        "value_sum": sum(values),
        "value_count": len(values),
        "has_nulls": null_count > 0,
    }


def aggregate_raw_to_level(
    start_time: datetime,
    end_time: datetime,
    bucket_type: str,
    group_types: Optional[List[str]] = None,
) -> int:
    if bucket_type not in BUCKET_CONFIG:
        raise ValueError(f"Invalid bucket_type: {bucket_type}")

    bucket_minutes, agg_model = BUCKET_CONFIG[bucket_type]
    start_norm = _normalize_to_utc_naive(start_time)
    end_norm = _normalize_to_utc_naive(end_time)

    query = SensorMeasurement.query.filter(
        SensorMeasurement.recorded_at.between(start_norm, end_norm)
    )
    if group_types:
        query = query.filter(SensorMeasurement.group_type.in_(group_types))

    raw_rows = query.all()
    if not raw_rows:
        print(f"[Aggregation] No raw rows for {bucket_type} in range [{start_norm} - {end_norm}]")
        return 0

    grouped: Dict[Tuple[str, str, str, str, datetime], List[SensorMeasurement]] = defaultdict(list)
    for row in raw_rows:
        bucket_start = round_to_bucket(row.recorded_at, bucket_minutes)
        key = (
            row.station_id,
            row.group_type,
            row.measurement_type,
            row.unit,
            bucket_start,
        )
        grouped[key].append(row)

    touched = 0
    now = datetime.utcnow()

    for (station_id, group_type, measurement_type, unit, bucket_start), rows in grouped.items():
        stats = compute_aggregates_for_bucket(rows)

        existing = agg_model.query.filter_by(
            station_id=station_id,
            measurement_type=measurement_type,
            bucket_start=bucket_start,
        ).first()

        if existing:
            existing.group_type = group_type
            existing.unit = unit
            existing.value_min = stats["value_min"]
            existing.value_max = stats["value_max"]
            existing.value_avg = stats["value_avg"]
            existing.value_sum = stats["value_sum"]
            existing.value_count = stats["value_count"]
            existing.has_nulls = bool(stats["has_nulls"])
            existing.computed_at = now
        else:
            db.session.add(
                agg_model(
                    station_id=station_id,
                    group_type=group_type,
                    measurement_type=measurement_type,
                    unit=unit,
                    bucket_start=bucket_start,
                    value_min=stats["value_min"],
                    value_max=stats["value_max"],
                    value_avg=stats["value_avg"],
                    value_sum=stats["value_sum"],
                    value_count=stats["value_count"],
                    has_nulls=bool(stats["has_nulls"]),
                    computed_at=now,
                )
            )

        touched += 1

    db.session.commit()
    print(f"[Aggregation] {bucket_type}: touched {touched} bucket rows")
    return touched


def aggregate_latest_hours(bucket_types: Optional[List[str]] = None, lookback_hours: int = 6) -> None:
    if bucket_types is None:
        bucket_types = ["30min", "1hour"]

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=lookback_hours)

    for bucket_type in bucket_types:
        try:
            aggregate_raw_to_level(start_time, end_time, bucket_type=bucket_type)
        except Exception as exc:
            print(f"[Aggregation ERROR] {bucket_type}: {exc}")
            db.session.rollback()


def refresh_recent_aggregates() -> None:
    now = datetime.utcnow()

    plans = [
        (["30min"], 12),
        (["1hour", "3hour"], 48),
        (["6hour", "12hour"], 168),
        (["24hour", "1week"], 720),
    ]

    for bucket_types, lookback_hours in plans:
        start_time = now - timedelta(hours=lookback_hours)
        for bucket_type in bucket_types:
            try:
                aggregate_raw_to_level(start_time, now, bucket_type=bucket_type)
            except Exception as exc:
                print(f"[Aggregation ERROR] refresh {bucket_type}: {exc}")
                db.session.rollback()


def backfill_aggregations(start_time: datetime, end_time: datetime, bucket_types: Optional[List[str]] = None) -> None:
    if bucket_types is None:
        bucket_types = list(BUCKET_CONFIG.keys())

    start_norm = _normalize_to_utc_naive(start_time)
    end_norm = _normalize_to_utc_naive(end_time)

    print(f"[Aggregation Backfill] range [{start_norm} - {end_norm}]")
    for bucket_type in bucket_types:
        if bucket_type not in BUCKET_CONFIG:
            print(f"[Aggregation Backfill] skipping unknown bucket type: {bucket_type}")
            continue
        try:
            count = aggregate_raw_to_level(start_norm, end_norm, bucket_type=bucket_type)
            print(f"[Aggregation Backfill] {bucket_type}: touched {count}")
        except Exception as exc:
            print(f"[Aggregation Backfill ERROR] {bucket_type}: {exc}")
            db.session.rollback()
