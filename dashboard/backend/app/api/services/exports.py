import csv
import os
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional

from sqlalchemy import and_, func, or_, select

from config import Config
from db.database import db
from db.models import ExportJob, SamplingMeasurement, SensorMeasurement
from utils.timezone import EST_TZ, est_now

ALLOWED_DOMAINS = {"sensor", "sampling"}

# Rows fetched from the database at a time while an export is written (and how often its progress is saved).
STREAM_BATCH_ROWS = 5000

# A text cell starting with one of these is read as a formula by Excel and other spreadsheets, so a value such as
# "=HYPERLINK(...)" stored in a site or measurement name could run when the CSV is opened. Such cells get a leading
# apostrophe, which spreadsheets show as plain text. Numbers are never changed: -3.2 stays a number.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_csv_cell(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


class _SafeCsvWriter:
    """csv.writer whose text cells are passed through safe_csv_cell."""

    def __init__(self, file_obj):
        self._writer = csv.writer(file_obj)

    def writerow(self, row):
        self._writer.writerow([safe_csv_cell(cell) for cell in row])


@contextmanager
def _streaming_connection():
    """A connection of its own that reads results STREAM_BATCH_ROWS at a time (a server-side cursor on
    PostgreSQL) instead of loading them all. Separate from db.session, whose progress commits would otherwise end
    the transaction the cursor lives in.

    On PostgreSQL its transaction is REPEATABLE READ, so every query on it sees the same snapshot: the sensor
    export's header query and its rows agree even while new readings arrive (a range ending "now")."""
    with db.engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="REPEATABLE READ")
        yield conn.execution_options(stream_results=True, yield_per=STREAM_BATCH_ROWS)


def _iso(value) -> str:
    return value.isoformat() if value else ""


# A queued job that hasn't started after this long has lost its task (Redis restarted, say), and a running job
# past the hard time limit has lost its worker process: neither will finish. The hourly cleanup marks them failed,
# and until then they don't count against the job limits.
QUEUED_STALE_AFTER = timedelta(hours=1)


def running_stale_after() -> timedelta:
    return timedelta(seconds=Config.EXPORT_HARD_TIME_LIMIT_SECONDS) + timedelta(minutes=5)


def _wall_to_utc(wall_time: datetime) -> datetime:
    """A naive local wall time (as est_now() stores them) as a UTC instant. An ambiguous time (the hour repeated
    when clocks fall back) is read as the later instant, so a job never looks older than it is."""
    return wall_time.replace(tzinfo=EST_TZ, fold=1).astimezone(timezone.utc)


def job_is_stuck(job, now_utc: Optional[datetime] = None) -> bool:
    """Whether a queued or running job will never finish (see QUEUED_STALE_AFTER). Ages are real elapsed time:
    naive wall times would make a job look an hour older or younger across a DST change."""
    now_utc = now_utc or datetime.now(timezone.utc)
    if job.status == "queued":
        since, limit = job.created_at, QUEUED_STALE_AFTER
    elif job.status == "running":
        since, limit = job.started_at or job.created_at, running_stale_after()
    else:
        return False
    return since is not None and now_utc - _wall_to_utc(since) > limit


def live_jobs(now_utc: Optional[datetime] = None) -> List:
    """The export jobs that are queued or running and may still finish. There are only ever a few queued or
    running rows (the hourly cleanup settles the rest), so the age check is done here rather than in SQL."""
    candidates = db.session.query(ExportJob).filter(ExportJob.status.in_(("queued", "running"))).all()
    return [job for job in candidates if not job_is_stuck(job, now_utc)]


# What a failed job reports to the page when the cause isn't a validation error.
EXPORT_FAILED_MESSAGE = "The server couldn't build this export. Please try again later."
# For an export stopped at the time limit, or found stuck while running.
EXPORT_TOO_SLOW_MESSAGE = "This export took too long to build. Try a shorter date range."


def settle_if_stuck(job, now_utc: Optional[datetime] = None) -> bool:
    """Mark a queued or running job that will never finish (job_is_stuck) failed, without committing. Returns
    whether it did. Used by the hourly cleanup, and by the job status route so the page learns at once."""
    if not job_is_stuck(job, now_utc):
        return False
    job.error_message = EXPORT_TOO_SLOW_MESSAGE if job.status == "running" else EXPORT_FAILED_MESSAGE
    job.status = "failed"
    job.completed_at = est_now()
    return True


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


def _local_date(value: str) -> str:
    """YYYYMMDD of an ISO timestamp in the site's time zone, i.e. the day the user picked.

    The dashboard sends local midnight and 23:59:59.999 converted to UTC, so formatting the UTC value
    would name a download for Nov 9 "..._20261109_20261110". Naive values are already local time.
    """
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is not None:
        ts = ts.astimezone(EST_TZ)
    return ts.strftime("%Y%m%d")


def default_export_filename(filters: Dict) -> str:
    start = _local_date(filters["start"])
    end = _local_date(filters["end"])

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
        rows_written = _write_sensor_frontend_style_csv(filters, output_path, progress_callback, total)
        if progress_callback:
            progress_callback(rows_written, total)
        return rows_written

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = _SafeCsvWriter(csv_file)
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

        # closing(): if writing fails part way, the generator is closed at once, which returns its connection
        # instead of leaving it checked out mid-transaction until garbage collection.
        with closing(iter_export_rows(filters)) as rows:
            for row in rows:
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
                if progress_callback and rows_written % STREAM_BATCH_ROWS == 0:
                    progress_callback(rows_written, total)

    if progress_callback:
        progress_callback(rows_written, total)

    return rows_written


def iter_export_rows(filters: Dict) -> Iterable[Dict]:
    """The export's readings, one dict each, in time order, streamed from the database (_streaming_connection)."""
    sensor = filters["domain"] == "sensor"
    if sensor:
        model = SensorMeasurement
        columns = (model.recorded_at, model.group_type, model.station_id, model.measurement_type, model.value,
                   model.unit)
        conditions = _sensor_conditions(filters)
    else:
        model = SamplingMeasurement
        columns = (model.recorded_at, model.creek_id, model.site_id, model.measurement_type, model.value, model.unit)
        conditions = _sampling_conditions(filters)

    statement = select(*columns).where(*conditions).order_by(model.recorded_at)
    with _streaming_connection() as conn:
        for r in conn.execute(statement):
            yield {
                "domain": filters["domain"],
                "recorded_at": _iso(r.recorded_at),
                "group_type": (r.group_type or "") if sensor else "",
                "station_id": (r.station_id or "") if sensor else "",
                "creek_id": "" if sensor else (r.creek_id or ""),
                "site_id": "" if sensor else (r.site_id or ""),
                "measurement_type": r.measurement_type or "",
                "value": r.value,
                "unit": r.unit or "",
            }


def _sensor_query(filters: Dict):
    return db.session.query(SensorMeasurement).filter(*_sensor_conditions(filters))


def _sampling_query(filters: Dict):
    return db.session.query(SamplingMeasurement).filter(*_sampling_conditions(filters))


def _sensor_conditions(filters: Dict) -> List:
    start_dt = datetime.fromisoformat(filters["start"])
    end_dt = datetime.fromisoformat(filters["end"])

    conditions = [
        SensorMeasurement.recorded_at.between(start_dt, end_dt),
        SensorMeasurement.group_type.in_(filters["group_types"]),
    ]

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
            conditions.append(or_(*per_group_clauses))
    elif filters.get("measurement_types"):
        conditions.append(SensorMeasurement.measurement_type.in_(filters["measurement_types"]))

    if filters.get("station_ids"):
        conditions.append(
            or_(
                SensorMeasurement.group_type != "Logger",
                SensorMeasurement.station_id.in_(filters["station_ids"]),
            )
        )

    return conditions


def _sampling_conditions(filters: Dict) -> List:
    start_dt = datetime.fromisoformat(filters["start"])
    end_dt = datetime.fromisoformat(filters["end"])

    conditions = [SamplingMeasurement.recorded_at.between(start_dt, end_dt)]

    if filters.get("creek_ids"):
        conditions.append(SamplingMeasurement.creek_id.in_(filters["creek_ids"]))

    if filters.get("measurement_types"):
        conditions.append(SamplingMeasurement.measurement_type.in_(filters["measurement_types"]))

    if filters.get("site_ids"):
        conditions.append(SamplingMeasurement.site_id.in_(filters["site_ids"]))

    return conditions


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


def _sensor_columns_summary(conn, conditions) -> Dict:
    """What the header of a sensor export needs, from one GROUP BY query instead of every row: the metrics seen in
    each group, the logger stations seen, and each metric's unit (the one of its latest reading)."""
    latest = func.max(SensorMeasurement.recorded_at)
    summary = conn.execute(
        select(
            SensorMeasurement.group_type,
            SensorMeasurement.measurement_type,
            SensorMeasurement.station_id,
            SensorMeasurement.unit,
            latest,
        )
        .where(*conditions)
        .group_by(
            SensorMeasurement.group_type,
            SensorMeasurement.measurement_type,
            SensorMeasurement.station_id,
            SensorMeasurement.unit,
        )
    ).all()

    metrics = {"Weather": set(), "Quality": set(), "Logger": set()}
    logger_stations = set()
    unit_seen_at = {}  # metric -> (latest reading, unit)
    for group_type, measurement_type, station_id, unit, seen_at in summary:
        metric = measurement_type or ""
        unit = unit or ""
        if metric not in unit_seen_at or (seen_at, unit) > unit_seen_at[metric]:
            unit_seen_at[metric] = (seen_at, unit)
        if group_type in ("Weather", "Quality"):
            metrics[group_type].add(metric)
        elif group_type == "Logger" and station_id:
            metrics["Logger"].add(metric)
            logger_stations.add(str(station_id))

    return {
        "metrics": metrics,
        "logger_stations": logger_stations,
        "units_by_metric": {metric: unit for metric, (_, unit) in unit_seen_at.items()},
    }


def _write_sensor_frontend_style_csv(
    filters: Dict,
    output_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    total: int = 0,
) -> int:
    # The header query and the rows share one connection, and so one snapshot (_streaming_connection).
    with _streaming_connection() as conn:
        return _write_sensor_csv(conn, filters, output_path, progress_callback, total)


def _write_sensor_csv(
    conn,
    filters: Dict,
    output_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    total: int = 0,
) -> int:
    """
    Export sensor data matching the exact CSV format from upload_data.py
    Structure: [ID, Timestamp, Weather section, blank, Quality section, blank, Logger section]
    Each section has Group label, then metrics. Logger section repeats Sensor+metrics for each logger.

    Readings are streamed in time order, STREAM_BATCH_ROWS at a time, and each CSV row is written as soon as its
    timestamp's readings are all in, so memory stays flat however long the range. Returns the readings exported.
    """
    requested_groups = set(filters.get("group_types", []))
    conditions = _sensor_conditions(filters)
    summary = _sensor_columns_summary(conn, conditions)
    units_by_metric = summary["units_by_metric"]
    all_weather_metrics = summary["metrics"]["Weather"]
    all_quality_metrics = summary["metrics"]["Quality"]
    all_logger_metrics = summary["metrics"]["Logger"]
    all_logger_stations = summary["logger_stations"]

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

    def metric_header(metric):
        unit = units_by_metric.get(metric, "")
        unit = unit.replace(" asl", "").strip() if unit else ""
        return f"{metric}: {unit}" if unit else metric

    # Build header row - ALWAYS include requested groups in the output order: Weather, Quality, Logger
    headers = ["ID", "Timestamp"]

    # Weather section: Include if requested (even if no data)
    if include_weather:
        headers.append("Group")
        headers.extend(metric_header(metric) for metric in weather_metrics)

    # Blank column separator between Weather and Quality
    if include_quality and include_weather:
        headers.append("")

    # Quality section: Include if requested (even if no data)
    if include_quality:
        headers.append("Group")
        headers.extend(metric_header(metric) for metric in quality_metrics)

    # Blank column separator between Quality and Logger
    if include_logger and (include_weather or include_quality):
        headers.append("")

    # Logger section: Include if requested (even if no data)
    if include_logger:
        headers.append("Group")
        for _ in effective_logger_stations:
            headers.append("Sensor")
            headers.extend(metric_header(metric) for metric in logger_metrics)

    def csv_row(row_num, timestamp, weather_data, quality_data, logger_data):
        row = [row_num, timestamp]
        if include_weather:
            row.append("Weather")
            row.extend(weather_data.get(metric, "") for metric in weather_metrics)
        if include_quality and include_weather:
            row.append("")
        if include_quality:
            row.append("Quality")
            row.extend(quality_data.get(metric, "") for metric in quality_metrics)
        if include_logger and (include_weather or include_quality):
            row.append("")
        if include_logger:
            row.append("Logger")
            for station_id in effective_logger_stations:
                row.append(_get_logger_label(station_id))
                row.extend(logger_data.get((station_id, metric), "") for metric in logger_metrics)
        return row

    readings = (
        select(
            SensorMeasurement.recorded_at,
            SensorMeasurement.group_type,
            SensorMeasurement.station_id,
            SensorMeasurement.measurement_type,
            SensorMeasurement.value,
        )
        .where(*conditions)
        .order_by(SensorMeasurement.recorded_at)
    )

    records = 0
    row_num = 0
    with open(output_path, "w", newline="", encoding="utf-8") as file_obj:
        writer = _SafeCsvWriter(file_obj)
        writer.writerow(headers)

        # The readings of one timestamp: metric -> value for Weather and Quality, (station, metric) -> value for
        # loggers. Rows arrive ordered by time, so a new timestamp means the previous one is complete.
        current = None
        weather_data, quality_data, logger_data = {}, {}, {}
        for recorded_at, group_type, station_id, measurement_type, value in conn.execute(readings):
            if records == 0 or recorded_at != current:
                if records:
                    row_num += 1
                    writer.writerow(csv_row(row_num, _iso(current), weather_data, quality_data, logger_data))
                current = recorded_at
                weather_data, quality_data, logger_data = {}, {}, {}

            records += 1
            metric = measurement_type or ""
            if group_type == "Weather" and include_weather:
                weather_data[metric] = value
            elif group_type == "Quality" and include_quality:
                quality_data[metric] = value
            elif group_type == "Logger" and include_logger and station_id:
                logger_data[(str(station_id), metric)] = value

            if progress_callback and records % STREAM_BATCH_ROWS == 0:
                progress_callback(records, total)

        if records:
            row_num += 1
            writer.writerow(csv_row(row_num, _iso(current), weather_data, quality_data, logger_data))

    return records


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
