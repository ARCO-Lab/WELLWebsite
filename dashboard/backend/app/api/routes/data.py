# This file defines the /api/data route for retrieving and filtering raw sensor measurement data from the database.
# It also triggers background summarization for weather, logger, and quality data.

from flask import request, jsonify
import pandas as pd
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
from datetime import datetime
from scripts.downsample import downsample
import threading
import math


def _aggregate_series_rows(rows, max_points):
    """Aggregate one series into at most max_points using average chunks."""
    if len(rows) <= max_points:
        return rows, 1

    step = max(1, math.ceil(len(rows) / max_points))
    aggregated = []

    for i in range(0, len(rows), step):
        chunk = rows[i:i + step]
        if not chunk:
            continue

        first = chunk[0]
        avg_value = sum(item.value for item in chunk) / len(chunk)

        aggregated.append(
            {
                "station_id": first.station_id,
                "group_type": first.group_type,
                "measurement_type": first.measurement_type,
                "value": avg_value,
                "unit": first.unit,
                "recorded_at": first.recorded_at.isoformat(),
            }
        )

    return aggregated, step


def _aggregate_rows_per_series(rows, max_points):
    """Aggregate each series independently so station/metric lines do not mix."""
    series_rows = {}
    for row in rows:
        key = (row.group_type, row.station_id, row.measurement_type, row.unit)
        series_rows.setdefault(key, []).append(row)

    aggregated_rows = []
    max_step = 1
    for key_rows in series_rows.values():
        key_rows.sort(key=lambda r: r.recorded_at)
        reduced, step = _aggregate_series_rows(key_rows, max_points)
        max_step = max(max_step, step)
        aggregated_rows.extend(reduced)

    aggregated_rows.sort(key=lambda r: r["recorded_at"])
    return aggregated_rows, max_step


def _parse_iso_datetime(value: str) -> datetime:
    """Parse ISO datetime values and accept UTC 'Z' suffix."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _select_granularity(start_dt: datetime, end_dt: datetime) -> str:
    """Select granularity by requested time span."""
    span_days = (end_dt - start_dt).total_seconds() / (24 * 3600)
    if span_days > 180:
        return "1week"
    if span_days > 90:
        return "24hour"
    if span_days > 45:
        return "12hour"
    if span_days > 21:
        return "6hour"
    if span_days > 7:
        return "3hour"
    if span_days > 2:
        return "1hour"
    if span_days > 1:
        return "30min"
    return "raw"


def _get_agg_model(granularity: str):
    return {
        "30min": SensorMeasurementAgg30Min,
        "1hour": SensorMeasurementAgg1Hour,
        "3hour": SensorMeasurementAgg3Hour,
        "6hour": SensorMeasurementAgg6Hour,
        "12hour": SensorMeasurementAgg12Hour,
        "24hour": SensorMeasurementAgg24Hour,
        "1week": SensorMeasurementAgg1Week,
    }.get(granularity)


def _serialize_raw_rows(rows):
    return [
        {
            "station_id": r.station_id,
            "group_type": r.group_type,
            "measurement_type": r.measurement_type,
            "value": r.value,
            "unit": r.unit,
            "recorded_at": r.recorded_at.isoformat(),
            "granularity": "raw",
        }
        for r in rows
    ]


def register_adaptive_data_route(app):
    @app.route("/api/data/adaptive", methods=["GET"])
    def get_adaptive_data():
        start = request.args.get("start")
        end = request.args.get("end")
        group_types = request.args.getlist("group_type")
        granularity_param = request.args.get("granularity", "auto")

        if not start or not end or not group_types:
            return jsonify({"error": "Missing required parameters: start, end, group_type"}), 400

        try:
            start_dt = _parse_iso_datetime(start)
            end_dt = _parse_iso_datetime(end)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400

        if start_dt >= end_dt:
            return jsonify({"error": "start must be before end"}), 400

        allowed = {"auto", "raw", "30min", "1hour", "3hour", "6hour", "12hour", "24hour", "1week"}
        if granularity_param not in allowed:
            return jsonify({"error": f"Invalid granularity: {granularity_param}"}), 400

        selected_granularity = (
            _select_granularity(start_dt, end_dt)
            if granularity_param == "auto"
            else granularity_param
        )

        source = "sensor_measurements"
        has_nulls = False

        if selected_granularity == "raw":
            rows = db.session.query(SensorMeasurement).filter(
                SensorMeasurement.group_type.in_(group_types),
                SensorMeasurement.recorded_at.between(start_dt, end_dt),
            ).order_by(SensorMeasurement.recorded_at).all()
            data = _serialize_raw_rows(rows)
        else:
            agg_model = _get_agg_model(selected_granularity)
            if not agg_model:
                return jsonify({"error": f"Invalid granularity: {selected_granularity}"}), 400

            rows = db.session.query(agg_model).filter(
                agg_model.group_type.in_(group_types),
                agg_model.bucket_start.between(start_dt, end_dt),
            ).order_by(agg_model.bucket_start).all()

            if rows:
                data = [row.to_dict() for row in rows]
                has_nulls = any(getattr(row, "has_nulls", False) for row in rows)
                source = f"sensor_measurements_agg_{selected_granularity}"
            else:
                # Fallback to raw when aggregates for the requested window are not ready yet.
                raw_rows = db.session.query(SensorMeasurement).filter(
                    SensorMeasurement.group_type.in_(group_types),
                    SensorMeasurement.recorded_at.between(start_dt, end_dt),
                ).order_by(SensorMeasurement.recorded_at).all()
                data = _serialize_raw_rows(raw_rows)
                source = "fallback_raw"

        metadata = {
            "granularity": selected_granularity,
            "point_count": len(data),
            "time_span_days": (end_dt - start_dt).total_seconds() / (24 * 3600),
            "cached": False,
            "source": source,
            "has_nulls_somewhere": has_nulls,
        }

        return jsonify({"data": data, "metadata": metadata}), 200

def register_data_route(app, latest_summaries):
    @app.route("/api/data", methods=["GET"])
    def get_filtered_data():
        # Parse query parameters
        start = request.args.get("start")
        end = request.args.get("end")
        group_types = request.args.getlist("group_type")
        max_points_raw = request.args.get("max_points")
        with_metadata = request.args.get("with_metadata", "false").lower() == "true"

        if not start or not end or not group_types:
            return jsonify({"error": "Missing required parameters"}), 400

        max_points = 0
        if max_points_raw:
            try:
                max_points = max(0, int(max_points_raw))
            except ValueError:
                return jsonify({"error": "Invalid max_points"}), 400

        try:
            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400

        # Query the database for matching sensor measurements
        query = db.session.query(SensorMeasurement).filter(
            SensorMeasurement.group_type.in_(group_types),
            SensorMeasurement.recorded_at.between(start_dt, end_dt)
        )

        raw_rows = query.order_by(SensorMeasurement.recorded_at).all()

        # Format raw query results as a list of dicts
        raw_data = [
            {
                "station_id": r.station_id,
                "group_type": r.group_type,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }            
            for r in raw_rows
        ]

        data = raw_data
        metadata = {
            "original_count": len(raw_data),
            "returned_count": len(raw_data),
            "server_aggregated": False,
            "aggregation_step": 1,
        }

        if max_points > 0 and len(raw_rows) > max_points:
            data, step = _aggregate_rows_per_series(raw_rows, max_points)
            metadata = {
                "original_count": len(raw_data),
                "returned_count": len(data),
                "server_aggregated": True,
                "aggregation_step": step,
            }

        df = pd.DataFrame(raw_data)

        def background_summarize(df):
            # Split data by group type
            weather_df = df[df["group_type"] == "Weather"]
            logger_df = df[df["group_type"] == "Logger"]
            quality_df = df[df["group_type"] == "Quality"]

            # Downsample and summarize each group
            weather_summary, logger_summary, quality_summary = downsample(weather_df, logger_df, quality_df)

            # Store summaries in shared state
            latest_summaries["data"] = {
                "weather": weather_summary,
                "logger": logger_summary,
                "quality": quality_summary
            }

        # Start background thread for summarization
        threading.Thread(target=background_summarize, args=(df,)).start()

        # Legacy response remains a list unless with_metadata=true is requested.
        if with_metadata:
            return jsonify({
                "data": data,
                "metadata": metadata,
            })

        return jsonify(data)