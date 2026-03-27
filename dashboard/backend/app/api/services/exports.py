import csv
import os
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional

from sqlalchemy import and_, or_

from db.database import db
from db.models import SamplingMeasurement, SensorMeasurement

ALLOWED_DOMAINS = {"sensor", "sampling"}

SENSOR_FILTER_CONFIG = {
    "gauges": {
        "sites": {
            "2577531": "Logger 1",
            "2577532": "Logger 2",
            "2577533": "Logger 3",
            "2577534": "Logger 4",
            "2577535": "Logger 5",
        }
    }
}

SENSOR_STATION_COORDINATES = [
    {"id": "2577531", "lat": 43.267100, "lng": -79.928830, "group": "gauges"},
    {"id": "2577532", "lat": 43.266390, "lng": -79.929400, "group": "gauges"},
    {"id": "2577533", "lat": 43.264720, "lng": -79.928440, "group": "gauges"},
    {"id": "2577534", "lat": 43.264140, "lng": -79.928310, "group": "gauges"},
    {"id": "2577535", "lat": 43.263850, "lng": -79.929850, "group": "gauges"},
    {"id": "Water Quality Station", "lat": 43.264700, "lng": -79.928400, "group": "quality"},
    {"id": "Weather Station", "lat": 43.266110, "lng": -79.928660, "group": "weather"},
]


def normalize_export_payload(payload: Dict) -> Dict:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    domain = payload.get("domain")
    if domain not in ALLOWED_DOMAINS:
        raise ValueError("Invalid domain. Expected 'sensor' or 'sampling'.")

    start = payload.get("start")
    end = payload.get("end")
    if not start or not end:
        raise ValueError("Missing required fields: start, end")

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("Invalid ISO datetime in start/end") from exc

    if start_dt > end_dt:
        raise ValueError("start must be before end")

    normalized = {
        "domain": domain,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "measurement_types": _as_string_list(payload.get("measurement_types", [])),
    }

    if domain == "sensor":
        group_types = _as_string_list(payload.get("group_types", []))
        if not group_types:
            raise ValueError("Sensor exports require at least one group_type")
        normalized["group_types"] = group_types
        normalized["station_ids"] = _as_string_list(payload.get("station_ids", []))

        group_measurement_types = _as_group_metric_map(payload.get("group_measurement_types"))
        normalized_group_measurement_types = {
            group: _as_string_list(group_measurement_types.get(group, []))
            for group in group_types
            if group in group_measurement_types
        }
        normalized["group_measurement_types"] = normalized_group_measurement_types

        if normalized_group_measurement_types:
            merged_measurements = set(normalized["measurement_types"])
            for metrics in normalized_group_measurement_types.values():
                merged_measurements.update(metrics)
            normalized["measurement_types"] = sorted(merged_measurements)
    else:
        normalized["creek_ids"] = _as_string_list(payload.get("creek_ids", []))
        normalized["site_ids"] = _as_string_list(payload.get("site_ids", []))

    return normalized


def estimate_rows(payload: Dict) -> int:
    filters = normalize_export_payload(payload)
    if filters["domain"] == "sensor":
        query = _sensor_query(filters)
    else:
        query = _sampling_query(filters)
    return int(query.count())


def default_export_filename(filters: Dict) -> str:
    start = datetime.fromisoformat(filters["start"]).strftime("%Y%m%d")
    end = datetime.fromisoformat(filters["end"]).strftime("%Y%m%d")

    if filters["domain"] == "sensor":
        parts = ["WELLWestCampus"]
        groups = set(filters.get("group_types", []))
        if "Logger" in groups:
            parts.append("WaterLogger")
        if "Quality" in groups:
            parts.append("WaterQuality")
        if "Weather" in groups:
            parts.append("WeatherStation")
        return f"{'_'.join(parts)}_{start}_{end}.csv"

    return f"well_export_sampling_{start}_{end}.csv"


def write_export_csv(
    payload: Dict,
    output_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    estimated_rows: Optional[int] = None,
) -> int:
    filters = normalize_export_payload(payload)
    total = estimated_rows if estimated_rows is not None else estimate_rows(filters)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if filters["domain"] == "sensor":
        rows_written = _write_sensor_frontend_style_csv(filters, output_path)
        if progress_callback:
            progress_callback(rows_written, total)
        return rows_written

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "domain",
                "recorded_at",
                "group_type",
                "station_id",
                "creek_id",
                "site_id",
                "measurement_type",
                "value",
                "unit",
            ]
        )

        for row in iter_export_rows(filters):
            writer.writerow(
                [
                    row.get("domain", ""),
                    row.get("recorded_at", ""),
                    row.get("group_type", ""),
                    row.get("station_id", ""),
                    row.get("creek_id", ""),
                    row.get("site_id", ""),
                    row.get("measurement_type", ""),
                    row.get("value", ""),
                    row.get("unit", ""),
                ]
            )
            rows_written += 1
            if progress_callback and rows_written % 5000 == 0:
                progress_callback(rows_written, total)

    if progress_callback:
        progress_callback(rows_written, total)

    return rows_written


def iter_export_rows(filters: Dict) -> Iterable[Dict]:
    if filters["domain"] == "sensor":
        query = _sensor_query(filters)
        for r in query.order_by(SensorMeasurement.recorded_at).yield_per(5000):
            yield {
                "domain": "sensor",
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else "",
                "group_type": r.group_type or "",
                "station_id": r.station_id or "",
                "creek_id": "",
                "site_id": "",
                "measurement_type": r.measurement_type or "",
                "value": r.value,
                "unit": r.unit or "",
            }
    else:
        query = _sampling_query(filters)
        for r in query.order_by(SamplingMeasurement.recorded_at).yield_per(5000):
            yield {
                "domain": "sampling",
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else "",
                "group_type": "",
                "station_id": "",
                "creek_id": r.creek_id or "",
                "site_id": r.site_id or "",
                "measurement_type": r.measurement_type or "",
                "value": r.value,
                "unit": r.unit or "",
            }


def _sensor_query(filters: Dict):
    start_dt = datetime.fromisoformat(filters["start"])
    end_dt = datetime.fromisoformat(filters["end"])

    query = db.session.query(SensorMeasurement).filter(
        SensorMeasurement.recorded_at.between(start_dt, end_dt),
        SensorMeasurement.group_type.in_(filters["group_types"]),
    )

    group_measurement_types = filters.get("group_measurement_types") or {}
    if group_measurement_types:
        per_group_clauses = []
        for group in filters["group_types"]:
            selected_metrics = group_measurement_types.get(group, [])
            if selected_metrics:
                per_group_clauses.append(
                    and_(
                        SensorMeasurement.group_type == group,
                        SensorMeasurement.measurement_type.in_(selected_metrics),
                    )
                )
            else:
                per_group_clauses.append(SensorMeasurement.group_type == group)

        if per_group_clauses:
            query = query.filter(or_(*per_group_clauses))
    elif filters.get("measurement_types"):
        query = query.filter(SensorMeasurement.measurement_type.in_(filters["measurement_types"]))

    if filters.get("station_ids"):
        query = query.filter(
            or_(
                SensorMeasurement.group_type != "Logger",
                SensorMeasurement.station_id.in_(filters["station_ids"]),
            )
        )

    return query


def _sampling_query(filters: Dict):
    start_dt = datetime.fromisoformat(filters["start"])
    end_dt = datetime.fromisoformat(filters["end"])

    query = db.session.query(SamplingMeasurement).filter(
        SamplingMeasurement.recorded_at.between(start_dt, end_dt)
    )

    if filters.get("creek_ids"):
        query = query.filter(SamplingMeasurement.creek_id.in_(filters["creek_ids"]))

    if filters.get("measurement_types"):
        query = query.filter(SamplingMeasurement.measurement_type.in_(filters["measurement_types"]))

    if filters.get("site_ids"):
        query = query.filter(SamplingMeasurement.site_id.in_(filters["site_ids"]))

    return query


def _as_string_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    raise ValueError("Expected a list for list-type fields")


def _as_group_metric_map(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected an object for group_measurement_types")

    normalized = {}
    for group, metrics in value.items():
        group_name = str(group).strip()
        if not group_name:
            continue
        normalized[group_name] = _as_string_list(metrics)

    return normalized


def _write_sensor_frontend_style_csv(filters: Dict, output_path: str) -> int:
    """
    Export sensor data matching the exact CSV format from upload_data.py
    Structure: [ID, Timestamp, Weather section, blank, Quality section, blank, Logger section]
    Each section has Group label, then metrics. Logger section repeats Sensor+metrics for each logger.
    """
    requested_groups = set(filters.get("group_types", []))

    query = _sensor_query(filters)
    records = query.order_by(SensorMeasurement.recorded_at).all()

    # Build lookup dictionaries by group and timestamp
    weather_data = {}  # (timestamp, metric) -> value
    quality_data = {}  # (timestamp, metric) -> value
    logger_data = {}   # (timestamp, station_id, metric) -> value
    
    all_timestamps = set()
    all_weather_metrics = set()
    all_quality_metrics = set()
    all_logger_metrics = set()
    all_logger_stations = set()
    units_by_metric = {}

    # First pass: collect all data and organize by group
    for record in records:
        timestamp = record.recorded_at.isoformat() if record.recorded_at else ""
        metric = record.measurement_type or ""
        value = record.value
        unit = record.unit or ""
        group_type = record.group_type or ""
        station_id = str(record.station_id or "") if record.station_id else ""

        all_timestamps.add(timestamp)
        units_by_metric[metric] = unit

        if group_type == "Weather" and "Weather" in requested_groups:
            weather_data[(timestamp, metric)] = value
            all_weather_metrics.add(metric)
        elif group_type == "Quality" and "Quality" in requested_groups:
            quality_data[(timestamp, metric)] = value
            all_quality_metrics.add(metric)
        elif group_type == "Logger" and "Logger" in requested_groups and station_id:
            logger_data[(timestamp, station_id, metric)] = value
            all_logger_metrics.add(metric)
            all_logger_stations.add(station_id)

    # Set up which groups we should include (based on request, not just what has data)
    include_weather = "Weather" in requested_groups
    include_quality = "Quality" in requested_groups
    include_logger = "Logger" in requested_groups

    # Apply measurement type filters
    allowed_metrics = set(filters.get("measurement_types", []))
    if allowed_metrics:
        all_weather_metrics = {m for m in all_weather_metrics if m in allowed_metrics}
        all_quality_metrics = {m for m in all_quality_metrics if m in allowed_metrics}
        all_logger_metrics = {m for m in all_logger_metrics if m in allowed_metrics}

    requested_metric_map: Dict[str, List[str]] = filters.get("group_measurement_types", {}) or {}

    weather_metrics = requested_metric_map.get("Weather") or sorted(all_weather_metrics)
    quality_metrics = requested_metric_map.get("Quality") or sorted(all_quality_metrics)
    logger_metrics = requested_metric_map.get("Logger") or sorted(all_logger_metrics)

    # Determine logger stations to include
    selected_station_ids = filters.get("station_ids") or []
    if selected_station_ids:
        effective_logger_stations = [str(sid) for sid in selected_station_ids]
    else:
        configured_ids = list(SENSOR_FILTER_CONFIG["gauges"]["sites"].keys())
        effective_logger_stations = configured_ids
        extras = sorted(all_logger_stations.difference(set(configured_ids)))
        effective_logger_stations.extend(extras)

    # Build header row - ALWAYS include requested groups in the output order: Weather, Quality, Logger
    headers = ["ID", "Timestamp"]
    
    # Weather section: Include if requested (even if no data)
    if include_weather:
        headers.append("Group")
        for metric in weather_metrics:
            unit = units_by_metric.get(metric, "")
            unit = unit.replace(" asl", "").strip() if unit else ""
            headers.append(f"{metric}: {unit}" if unit else metric)
    
    # Blank column separator between Weather and Quality
    if include_quality and include_weather:
        headers.append("")
    
    # Quality section: Include if requested (even if no data)
    if include_quality:
        headers.append("Group")
        for metric in quality_metrics:
            unit = units_by_metric.get(metric, "")
            unit = unit.replace(" asl", "").strip() if unit else ""
            headers.append(f"{metric}: {unit}" if unit else metric)
    
    # Blank column separator between Quality and Logger
    if include_logger and (include_weather or include_quality):
        headers.append("")
    
    # Logger section: Include if requested (even if no data)
    if include_logger:
        headers.append("Group")
        if effective_logger_stations:
            for station_id in effective_logger_stations:
                headers.append("Sensor")
                for metric in logger_metrics:
                    unit = units_by_metric.get(metric, "")
                    unit = unit.replace(" asl", "").strip() if unit else ""
                    headers.append(f"{metric}: {unit}" if unit else metric)

    with open(output_path, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(headers)

        # Write data rows
        sorted_timestamps = sorted(all_timestamps)
        for row_num, timestamp in enumerate(sorted_timestamps, 1):
            csv_row = [row_num, timestamp]

            # Weather section data
            if include_weather:
                csv_row.append("Weather")
                for metric in weather_metrics:
                    csv_row.append(weather_data.get((timestamp, metric), ""))

            # Blank separator
            if include_quality and include_weather:
                csv_row.append("")

            # Quality section data
            if include_quality:
                csv_row.append("Quality")
                for metric in quality_metrics:
                    csv_row.append(quality_data.get((timestamp, metric), ""))

            # Blank separator
            if include_logger and (include_weather or include_quality):
                csv_row.append("")

            # Logger section data
            if include_logger:
                csv_row.append("Logger")
                for station_id in effective_logger_stations:
                    csv_row.append(_get_logger_label(station_id))
                    for metric in logger_metrics:
                        csv_row.append(logger_data.get((timestamp, station_id, metric), ""))

            if len(csv_row) < len(headers):
                csv_row.extend([""] * (len(headers) - len(csv_row)))
            elif len(csv_row) > len(headers):
                csv_row = csv_row[: len(headers)]

            writer.writerow(csv_row)

    return len(records)


def _get_station_coords(station_id: str):
    for station in SENSOR_STATION_COORDINATES:
        if str(station["id"]) == str(station_id):
            return station["lat"], station["lng"]
    return "", ""


def _get_group_coords(group: str):
    for station in SENSOR_STATION_COORDINATES:
        if station.get("group") == group:
            return station["lat"], station["lng"]
    return "", ""


def _get_logger_label(station_id: str):
    return SENSOR_FILTER_CONFIG["gauges"]["sites"].get(str(station_id), f"Logger {station_id}")
