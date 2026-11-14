import csv
import math
import os
import shutil
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional

from sqlalchemy import and_, func, or_, select

from api.services.catalog import known_series
from api.validation import bad_text
from config import Config
from db.database import db
from db.models import ExportJob, SamplingMeasurement, SensorMeasurement
from db.ordering import bytewise, sampling_order
from utils.parsers import SENTINEL_MAX
from utils.timezone import EST_TZ, check_site_years, est_now, iso_time

ALLOWED_DOMAINS = {"sensor", "sampling"}
SENSOR_GROUPS = ("Weather", "Quality", "Logger")

# Each list in a request (stations, metrics, creeks, sites) may hold at most MAX_LIST_VALUES names of at most
# MAX_NAME_CHARS characters; duplicates are dropped. The dashboard sends a handful of each. Without a cap, a list of
# thousands of station ids made every row of a sensor export that many column groups wide.
MAX_LIST_VALUES = 50
MAX_NAME_CHARS = 64


class ExportValidationError(ValueError):
    """A request that isn't a valid export. Its message is written for the user and is the only error text the
    export routes (and a failed job's status) pass on; any other error gets a fixed message."""


class ExportAborted(Exception):
    """An export stopped while it was being written, because its file grew past what the disk can spare or past
    EXPORT_MAX_FILE_MB, or because it ran past its deadline. The message is for the user; the caller deletes the
    file. `status` is the HTTP status a direct download answers with."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


# Rows fetched from the database at a time while an export is written (and how often its progress is saved).
STREAM_BATCH_ROWS = 5000

# A text cell starting with one of these is read as a formula by Excel and other spreadsheets, so a value such as
# "=HYPERLINK(...)" stored in a site or measurement name could run when the CSV is opened. Such cells get a leading
# apostrophe, which spreadsheets show as plain text. Numbers are never changed: -3.2 stays a number.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# Times in the CSV files are written as stored: America/Toronto wall-clock time (EST or EDT, whichever was in effect),
# ISO 8601 without an offset. The time column's header names the zone, so a file read on its own says how to read
# its times. (No offset is written because the stored time doesn't say which of the two 01:xx it was in the hour
# repeated when clocks fall back.) The monthly Borealis file (scripts/upload_data.py) uses the same header.
TIMESTAMP_HEADER = f"Timestamp ({EST_TZ.key})"
RECORDED_AT_HEADER = f"recorded_at ({EST_TZ.key})"


def safe_csv_cell(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def csv_cell(value):
    """A cell as the CSV files write it: a missing value (None, or a NaN, infinity or "no reading" sentinel as some
    older rows store) is an empty field, never "nan"; text goes through safe_csv_cell."""
    if value is None or (isinstance(value, float) and (not math.isfinite(value) or value <= SENTINEL_MAX)):
        return ""
    return safe_csv_cell(value)


class SafeCsvWriter:
    """csv.writer whose cells are passed through csv_cell. With a budget (WriteBudget), it raises ExportAborted
    once the file has grown past the budget's bytes or the clock past its deadline."""

    def __init__(self, file_obj, budget=None):
        self._budget = budget
        self._writer = csv.writer(_CountingFile(file_obj, budget) if budget else file_obj)

    def writerow(self, row):
        self._writer.writerow([csv_cell(cell) for cell in row])
        if self._budget:
            self._budget.check()

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# How often (in rows written) a budget looks at the clock: cheap enough for every row, but there's no need.
DEADLINE_CHECK_ROWS = 200


class WriteBudget:
    """The most an export may write (max_bytes) and when it must be done by (deadline, a time.monotonic() value),
    either None for no limit."""

    def __init__(self, max_bytes=None, deadline=None):
        self.max_bytes, self.deadline = max_bytes, deadline
        self.written = 0
        self._rows = 0

    def check(self):
        if self.max_bytes is not None and self.written > self.max_bytes:
            raise ExportAborted("This export is too large to prepare. Choose a shorter date range or fewer "
                                "measurements.", 413)
        self._rows += 1
        if self.deadline is not None and self._rows % DEADLINE_CHECK_ROWS == 0 and time.monotonic() > self.deadline:
            raise ExportAborted("This export took too long to prepare. Choose a shorter date range or fewer "
                                "measurements.", 504)


class _CountingFile:
    """A text file that adds what is written to a WriteBudget (characters, close enough to bytes: the cells are
    numbers and plain names)."""

    def __init__(self, file_obj, budget):
        self._file, self._budget = file_obj, budget

    def write(self, text):
        self._budget.written += len(text)
        return self._file.write(text)


def write_budget(deadline_seconds=None):
    """The WriteBudget for an export starting now: no more than EXPORT_MAX_FILE_MB, and no more than the exports
    disk can give while keeping EXPORT_MIN_FREE_MB free (the database shares that disk), whatever the estimate said.
    deadline_seconds from now, if given."""
    max_bytes = Config.EXPORT_MAX_FILE_MB * 1024 * 1024 if Config.EXPORT_MAX_FILE_MB > 0 else None
    free = _free_bytes()
    if free is not None:
        room = max(0, free - Config.EXPORT_MIN_FREE_MB * 1024 * 1024)
        max_bytes = room if max_bytes is None else min(max_bytes, room)
    deadline = time.monotonic() + deadline_seconds if deadline_seconds else None
    return WriteBudget(max_bytes, deadline)


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


def jobs_started_since(fingerprint: str, since_utc: datetime) -> int:
    """How many jobs this visitor started since since_utc, whatever became of them (for the hourly quota). Rows
    are kept for weeks (tasks/exports.py JOB_ROW_RETENTION), and created_at is naive wall time, so rows from a little
    before are fetched and their real ages checked here (wall times are an hour off across a DST change)."""
    wall_cutoff = since_utc.astimezone(EST_TZ).replace(tzinfo=None) - timedelta(hours=1)
    rows = (db.session.query(ExportJob.created_at, ExportJob.error_message)
            .filter(ExportJob.requester_fingerprint == fingerprint, ExportJob.created_at >= wall_cutoff).all())
    # A job that couldn't be queued (Redis down) never ran, so it doesn't use up the quota
    return sum(1 for created_at, error in rows
               if _wall_to_utc(created_at) >= since_utc and error != EXPORT_QUEUE_DOWN_MESSAGE)


# Shown on the Download panel when a background export can't be queued (the job is marked failed with it too, by
# api/routes/exports.py). Such a job never ran, so it doesn't count against the visitor's hourly quota.
EXPORT_QUEUE_DOWN_MESSAGE = ("Large exports are unavailable right now. Please try again in a few minutes, "
                             "or pick a shorter range to download directly.")


# A ready job is handed to another request for the same export only if its file has at least this long left, so
# the second download can't find it expired, and only if its data can't have changed: its range ended a day before
# the job was made (readings that old are settled), or it was built in the last REUSE_FRESH.
REUSE_MIN_LEFT = timedelta(minutes=10)
REUSE_FRESH = timedelta(minutes=10)
REUSE_SETTLED = timedelta(days=1)


def reusable_job(filters: Dict, now_utc: Optional[datetime] = None):
    """A ready job whose payload is exactly these normalised filters and whose file can be sent instead of building
    the same export again, or None."""
    now_utc = now_utc or datetime.now(timezone.utc)
    end = datetime.fromisoformat(filters["end"])
    candidates = (db.session.query(ExportJob)
                  .filter(ExportJob.status == "ready", ExportJob.domain == filters["domain"],
                          ExportJob.expires_at.isnot(None), ExportJob.artifact_path.isnot(None))
                  .order_by(ExportJob.completed_at.desc()).all())
    for job in candidates:
        if job.payload != filters or _wall_to_utc(job.expires_at) - now_utc < REUSE_MIN_LEFT:
            continue
        settled = end < job.created_at - REUSE_SETTLED
        fresh = job.completed_at is not None and now_utc - _wall_to_utc(job.completed_at) < REUSE_FRESH
        if (settled or fresh) and os.path.isfile(job.artifact_path):
            return job
    return None


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
        raise ExportValidationError("Payload must be a JSON object")

    domain = payload.get("domain")
    if not isinstance(domain, str) or domain not in ALLOWED_DOMAINS:
        raise ExportValidationError("Invalid domain. Expected 'sensor' or 'sampling'.")

    start = payload.get("start")
    end = payload.get("end")
    if not start or not end:
        raise ExportValidationError("Missing required fields: start, end")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ExportValidationError("start and end must be ISO datetime strings")

    try:
        start_in = iso_time(start)
        end_in = iso_time(end)
        # recorded_at is naive America/Toronto wall-clock time. Compared with an aware time, PostgreSQL reads it in
        # the session's time zone: America/New_York on the VM (the same rules, so no shift), but in any other zone
        # the export would be hours off. So aware times become site wall-clock time here, before they are compared
        # (comparing an aware with a naive time raises TypeError). OverflowError: a time such as
        # 0001-01-01T00:00+05:00 has no local time.
        start_dt, end_dt = _site_naive(start_in), _site_naive(end_in)
        check_site_years(start_dt, end_dt)
    except (ValueError, OverflowError) as exc:
        raise ExportValidationError("Invalid ISO datetime in start/end") from exc

    if start_in.tzinfo and end_in.tzinfo:
        # Two real instants: compare those. Inside the hour repeated when clocks fall back their wall-clock times
        # can run backwards (05:50Z is 01:50 EDT, 06:10Z is 01:10 EST), so they're put in order, as the read
        # routes do (utils/timezone.site_range).
        if start_in > end_in:
            raise ExportValidationError("start must be before end")
        start_dt, end_dt = min(start_dt, end_dt), max(start_dt, end_dt)
    elif start_dt > end_dt:
        raise ExportValidationError("start must be before end")

    normalized = {
        "domain": domain,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "measurement_types": _as_string_list(payload.get("measurement_types", []), "measurement_types"),
    }

    if domain == "sensor":
        group_types = _as_string_list(payload.get("group_types", []), "group_types")
        if not group_types:
            raise ExportValidationError("Sensor exports require at least one group_type")
        if any(group not in SENSOR_GROUPS for group in group_types):
            raise ExportValidationError(f"group_types must be among {', '.join(SENSOR_GROUPS)}")
        normalized["group_types"] = group_types
        normalized["station_ids"] = _as_string_list(payload.get("station_ids", []), "station_ids")

        group_measurement_types = _as_group_metric_map(payload.get("group_measurement_types"))
        normalized_group_measurement_types = {
            group: _as_string_list(group_measurement_types.get(group, []), "group_measurement_types")
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
        normalized["creek_ids"] = _as_string_list(payload.get("creek_ids", []), "creek_ids")
        normalized["site_ids"] = _as_string_list(payload.get("site_ids", []), "site_ids")

    return normalized


# About how many bytes of CSV one reading takes in a sampling export (one reading per row), and in an estimate made
# without the request's filters: enough to tell whether a file fits.
EXPORT_BYTES_PER_ROW = 80
# A sensor export has one row per timestamp and one cell per column. These err large: a cell is a number such as
# 12.345 or 0.30000000000000004 (str of a float) and its comma, and a row starts with its number and its time.
SENSOR_ROW_BYTES = 48
SENSOR_CELL_BYTES = 20
READING_INTERVAL = timedelta(minutes=10)  # every sensor reports every 10 minutes, on the 10-minute marks

DISK_FULL_MESSAGE = ("The server is short of disk space, so it can't prepare this export right now. Please try "
                     "again later.")


def _free_bytes() -> Optional[int]:
    """Free bytes on EXPORTS_DIR's disk, or None when that can't be told."""
    directory = Config.EXPORTS_DIR
    while directory and not os.path.isdir(directory):  # not created yet: check the disk it will be on
        parent = os.path.dirname(directory)
        directory = parent if parent != directory else ""
    try:
        return shutil.disk_usage(directory or ".").free
    except OSError:
        return None


def export_size_bytes(filters: Dict, row_count: int) -> int:
    """About how large an export of `row_count` readings will be, erring large. A sensor export's size is set by its
    columns as much as its readings: it has one row per timestamp (at most one per 10-minute mark of the range, and
    no more than the readings) and a cell per column (sensor_header_cells)."""
    row_count = max(0, row_count)
    if filters.get("domain") != "sensor":
        return row_count * EXPORT_BYTES_PER_ROW
    span = datetime.fromisoformat(filters["end"]) - datetime.fromisoformat(filters["start"])
    timestamps = min(row_count, int(span / READING_INTERVAL) + 1)
    return timestamps * (SENSOR_ROW_BYTES + SENSOR_CELL_BYTES * len(sensor_header_cells(filters)))


def disk_space_error(estimated_rows: int, filters: Optional[Dict] = None) -> Optional[str]:
    """None when EXPORTS_DIR's disk can take an export of this many readings (sized by export_size_bytes when the
    request's normalised filters are given) and still keep EXPORT_MIN_FREE_MB free; otherwise the message for the
    user. The database shares this disk on the VM, so a full disk would stop ingestion: running short of space
    refuses exports rather than filling it. An estimate can be off, so the writer also stops at that limit
    (write_budget)."""
    free = _free_bytes()
    if free is None:
        return None  # can't tell: don't refuse every export over it
    size = export_size_bytes(filters, estimated_rows) if filters else max(0, estimated_rows) * EXPORT_BYTES_PER_ROW
    if free >= size + Config.EXPORT_MIN_FREE_MB * 1024 * 1024:
        return None
    return DISK_FULL_MESSAGE


def estimate_rows(payload: Dict) -> int:
    filters = normalize_export_payload(payload)
    if filters["domain"] == "sensor":
        query = _sensor_query(filters)
    else:
        query = _sampling_query(filters)
    return int(query.count())


def _site_naive(ts: datetime) -> datetime:
    """An aware time as naive site (America/Toronto) wall-clock time; naive times are taken as site time already."""
    return ts.astimezone(EST_TZ).replace(tzinfo=None) if ts.tzinfo is not None else ts


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
    budget: Optional[WriteBudget] = None,
) -> int:
    """Writes the export's CSV to output_path and returns the readings in it. Raises ExportAborted (leaving the
    partial file for the caller to delete) when the file outgrows `budget` or runs past its deadline; without a
    budget, write_budget()'s size limit applies."""
    filters = normalize_export_payload(payload)
    total = estimated_rows if estimated_rows is not None else estimate_rows(filters)
    budget = budget or write_budget()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if filters["domain"] == "sensor":
        rows_written = _write_sensor_frontend_style_csv(filters, output_path, progress_callback, total, budget)
        if progress_callback:
            progress_callback(rows_written, total)
        return rows_written

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = SafeCsvWriter(csv_file, budget)
        writer.writerow(
            [
                "domain",
                RECORDED_AT_HEADER,
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

    with _streaming_connection() as conn:
        # Rows that share a time come in a fixed order: sampling by site, then parameter (db/ordering.py); sensor
        # readings by station, then measurement.
        if sensor:
            order = (model.recorded_at, bytewise(model.station_id, conn.dialect.name),
                     bytewise(model.measurement_type, conn.dialect.name))
        else:
            order = sampling_order(conn.dialect.name)
        statement = select(*columns).where(*conditions).order_by(*order)
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


def _as_string_list(value, field="list"):
    """A request's list of names: blanks dropped, duplicates dropped (the first kept, in order), and an
    ExportValidationError for anything but a list of names, a name with control characters (api/validation.py) or
    over MAX_NAME_CHARS, or more than MAX_LIST_VALUES names."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ExportValidationError("Expected a list for list-type fields")
    names = []
    for item in value:
        if isinstance(item, (dict, list)):
            raise ExportValidationError(f"{field} must be a list of names")
        name = str(item)
        if not name.strip() or name in names:
            continue
        if bad_text(name) or len(name) > MAX_NAME_CHARS:
            raise ExportValidationError(f"{field} has a name that isn't valid")
        names.append(name)
        if len(names) > MAX_LIST_VALUES:
            raise ExportValidationError(f"{field} may hold at most {MAX_LIST_VALUES} names")
    return names


def _as_group_metric_map(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ExportValidationError("Expected an object for group_measurement_types")

    normalized = {}
    for group, metrics in value.items():
        group_name = str(group).strip()
        if group_name not in SENSOR_GROUPS:  # only these are ever read, and only when group_types names them
            continue
        normalized[group_name] = metrics

    return normalized


def _known_columns():
    """What exists to be a column (api/services/catalog.py): each group's metrics, and the logger stations."""
    series = known_series()
    metrics = {group: {m for g, _, m in series if g == group} for group in SENSOR_GROUPS}
    return metrics, {s for g, s, _ in series if g == "Logger"}


def sensor_columns(filters: Dict, found: Optional[Dict] = None) -> Dict:
    """The columns of a sensor export: {"Weather": [metric, ...], "Quality": [...], "Logger": [...],
    "stations": [logger station id, ...]}.

    Metrics and stations the request names are kept, in its order, only if they exist (_known_columns): a name that
    matches no series would only add an empty column to every row. A group with no metrics named gets the metrics
    `found` holds for it (the readings in the export's range, from _sensor_columns_summary) or, without `found` (the
    size estimate, made before any reading is read), every metric it has, narrowed to measurement_types if those are
    given. Without station_ids, the configured loggers come first, then any other logger in `found` (or that exists)."""
    known_metrics, known_stations = _known_columns()
    allowed = set(filters.get("measurement_types", []))
    requested = filters.get("group_measurement_types", {}) or {}
    columns = {}
    for group in SENSOR_GROUPS:
        if requested.get(group):
            columns[group] = [m for m in requested[group] if m in known_metrics[group]]
        else:
            seen = found["metrics"][group] if found else known_metrics[group]
            columns[group] = sorted(m for m in seen if not allowed or m in allowed)
    configured = list(SENSOR_FILTER_CONFIG["gauges"]["sites"].keys())
    if filters.get("station_ids"):
        columns["stations"] = [s for s in filters["station_ids"] if s in known_stations]
    else:
        others = found["logger_stations"] if found else known_stations
        columns["stations"] = configured + sorted(set(others).difference(configured))
    return columns


def sensor_header_cells(filters: Dict, found: Optional[Dict] = None) -> List[str]:
    """The header row's cells, before each metric gets its unit: ID, the time, then each requested group's label and
    metrics (Logger: a Sensor label and the metrics for each station), with a blank cell between groups. Every row
    has a cell under each of these."""
    groups = set(filters.get("group_types", []))
    columns = sensor_columns(filters, found)
    cells = ["ID", TIMESTAMP_HEADER]
    for group in SENSOR_GROUPS:
        if group not in groups:
            continue
        if len(cells) > 2:
            cells.append("")
        cells.append("Group")
        if group == "Logger":
            for _ in columns["stations"]:
                cells.append("Sensor")
                cells.extend(columns["Logger"])
        else:
            cells.extend(columns[group])
    return cells


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
    budget: Optional[WriteBudget] = None,
) -> int:
    # The header query and the rows share one connection, and so one snapshot (_streaming_connection).
    with _streaming_connection() as conn:
        return _write_sensor_csv(conn, filters, output_path, progress_callback, total, budget)


def _write_sensor_csv(
    conn,
    filters: Dict,
    output_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    total: int = 0,
    budget: Optional[WriteBudget] = None,
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

    # Set up which groups we should include (based on request, not just what has data)
    include_weather = "Weather" in requested_groups
    include_quality = "Quality" in requested_groups
    include_logger = "Logger" in requested_groups

    # The metrics and logger stations that get columns: those asked for that exist or, for a group with none asked
    # for, those with readings in the range (sensor_columns)
    columns = sensor_columns(filters, summary)
    weather_metrics = columns["Weather"]
    quality_metrics = columns["Quality"]
    logger_metrics = columns["Logger"]
    effective_logger_stations = columns["stations"]

    def metric_header(metric):
        unit = units_by_metric.get(metric, "")
        unit = unit.replace(" asl", "").strip() if unit else ""
        return f"{metric}: {unit}" if unit else metric

    # Build header row - ALWAYS include requested groups in the output order: Weather, Quality, Logger
    headers = ["ID", TIMESTAMP_HEADER]

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

    # Readings of one time in a fixed order (station, then metric): where two stations of a group report the same
    # metric, the cell is always the same one's.
    readings = (
        select(
            SensorMeasurement.recorded_at,
            SensorMeasurement.group_type,
            SensorMeasurement.station_id,
            SensorMeasurement.measurement_type,
            SensorMeasurement.value,
        )
        .where(*conditions)
        .order_by(SensorMeasurement.recorded_at, bytewise(SensorMeasurement.station_id, conn.dialect.name),
                  bytewise(SensorMeasurement.measurement_type, conn.dialect.name))
    )

    records = 0
    row_num = 0
    with open(output_path, "w", newline="", encoding="utf-8") as file_obj:
        writer = SafeCsvWriter(file_obj, budget)
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
