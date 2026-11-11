# This file defines the SQLAlchemy ORM models for sensor and sampling measurements.
# Sensor readings, lab sampling results and export jobs each get one table.

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.types import DateTime, TypeDecorator

from db.database import db
from utils.timezone import UTC, as_utc, est_now

OLD_SCHEMA = ("sensor_measurements.recorded_at is still timestamp without time zone (naive Toronto time), but this "
              "code stores and reads instants: run scripts/migrate.py (migration 0002) before starting it")


class OldSchemaError(RuntimeError):
    """The database predates migration 0002; this code would show every reading time 4-5 hours off."""


class Instant(TypeDecorator):
    """A timestamptz column that always gives back aware UTC datetimes.

    PostgreSQL stores the instant. SQLite (the tests) stores the UTC wall time, which comes back naive and is
    marked UTC here, so both databases return the same values. A naive value written or compared is taken as site
    (Toronto) wall time, the meaning naive times had before; see utils.timezone.as_utc.

    PostgreSQL returns timestamptz aware, so a naive value from it means the column is still the old naive type:
    that raises rather than being read as UTC, which would shift every time by the Toronto offset."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else as_utc(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo:
            return value.astimezone(UTC)
        if dialect.name == "postgresql":
            raise OldSchemaError(OLD_SCHEMA)
        return value.replace(tzinfo=UTC)


def recorded_at_type(url, engine_options=None):
    """The PostgreSQL type of sensor_measurements.recorded_at at `url` (e.g. 'timestamp with time zone'), None when
    the table doesn't exist yet. Its own short-lived engine, with a 5 s connect timeout."""
    options = dict(engine_options or {})
    options["connect_args"] = {"connect_timeout": 5, **options.get("connect_args", {})}
    engine = create_engine(url, **options)
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                "SELECT a.atttypid::regtype::text FROM pg_attribute a "
                "WHERE a.attrelid = to_regclass('sensor_measurements') AND a.attname = 'recorded_at' "
                "AND NOT a.attisdropped")).scalar()
    finally:
        engine.dispose()


def check_schema(url, engine_options=None, log=None):
    """Refuse (OldSchemaError) to run this code on a database that hasn't had migration 0002. Only PostgreSQL is
    checked; a database that can't be reached is logged and let through, since nothing can be read from it anyway
    (and the CI import check runs with an unreachable one)."""
    if not url or not url.startswith("postgresql"):
        return
    try:
        kind = recorded_at_type(url, engine_options)
    except OperationalError as e:
        if log:
            log(f"schema check skipped, the database can't be reached: {type(e).__name__}")
        return
    if kind == "timestamp without time zone":
        raise OldSchemaError(OLD_SCHEMA)


class SensorMeasurement(db.Model):
    __tablename__ = "sensor_measurements"
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String) # Weather, Quality, Logger
    measurement_type = db.Column(db.String)
    value = db.Column(db.Float)
    unit = db.Column(db.String)
    # The reading's instant (timestamptz since db/migrations/0002_*.sql), so both copies of the hour repeated when
    # clocks fall back are kept. The API and the CSV files still show site wall-clock time (utils.timezone).
    recorded_at = db.Column(Instant, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("station_id", "measurement_type", "recorded_at"),
        # For queries by group and time range; existing databases get it from db/migrations/0001_*.sql.
        db.Index("ix_sensor_measurements_group_type_recorded_at", "group_type", "recorded_at"),
    )


class SamplingMeasurement(db.Model):
    __tablename__ = "sampling_measurements"
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.String, nullable=False)
    creek_id = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String)
    value = db.Column(db.Float)
    unit = db.Column(db.String)
    recorded_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("site_id", "measurement_type", "recorded_at"),
    )


class ExportJob(db.Model):
    __tablename__ = "export_jobs"

    id = db.Column(db.String(36), primary_key=True)
    status = db.Column(db.String(20), nullable=False, index=True, default="queued")
    domain = db.Column(db.String(20), nullable=False)  # sensor | sampling
    payload = db.Column(db.JSON, nullable=False)
    estimated_rows = db.Column(db.Integer, nullable=True)
    produced_rows = db.Column(db.Integer, nullable=True)
    progress_pct = db.Column(db.Float, nullable=False, default=0.0)
    artifact_path = db.Column(db.String(512), nullable=True)
    artifact_name = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    requester_fingerprint = db.Column(db.String(128), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=est_now)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "domain": self.domain,
            "estimated_rows": self.estimated_rows,
            "produced_rows": self.produced_rows,
            "progress_pct": self.progress_pct,
            "error_message": self.error_message,
            "artifact_name": self.artifact_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


# The two tables below hold the state of the worker's email alerts (scripts/check_alerts.py). Existing databases
# get them from db/migrations/0003_monitoring_alerts.sql; keep the two in step.

class VendorStatus(db.Model):
    """The outcome of the latest vendor API call of each ingestion source ("LI-COR", "WQData"), written by
    scripts/inject_from_api.py every run. Times are aware (UTC in the database)."""
    __tablename__ = "vendor_status"
    source = db.Column(db.String(32), primary_key=True)
    last_attempt_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_success_at = db.Column(db.DateTime(timezone=True))
    last_failure_at = db.Column(db.DateTime(timezone=True))
    failing_since = db.Column(db.DateTime(timezone=True))       # first failure of the current run of failures
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)
    last_error_kind = db.Column(db.String(32))                  # auth, quota, server, timeout, network, ...
    last_http_status = db.Column(db.Integer)
    last_error = db.Column(db.Text)                             # type and HTTP status only, never a URL or key


class AlertIncident(db.Model):
    """One alert condition from when it is first seen until it clears. At most one open (resolved_at IS NULL)
    incident per incident_key, so each condition is emailed once, then reminded about at most once a day."""
    __tablename__ = "alert_incidents"
    id = db.Column(db.Integer, primary_key=True)
    incident_key = db.Column(db.String(255), nullable=False)    # e.g. "stale:4501", "vendor:LI-COR"
    kind = db.Column(db.String(32), nullable=False)             # STALE_SENSOR, VENDOR_DOWN, SUSPECT_VALUES
    title = db.Column(db.Text, nullable=False)                  # the email subject line, without "[WELL] "
    detail = db.Column(db.Text, nullable=False)                 # what is wrong and what to check
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)   # when the condition began
    opened_at = db.Column(db.DateTime(timezone=True), nullable=False)    # when the alert check first saw it
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_notified_at = db.Column(db.DateTime(timezone=True))    # NULL until it is emailed
    notifications = db.Column(db.Integer, nullable=False, default=0)
    resolved_at = db.Column(db.DateTime(timezone=True))
    close_reason = db.Column(db.String(16))   # "cleared", or "superseded" (replaced or muted; no recovery email)
    reopened_at = db.Column(db.DateTime(timezone=True))     # came back after its recovery was emailed
    back_again_at = db.Column(db.DateTime(timezone=True))   # when "back again" was last emailed
    flaps = db.Column(db.Integer, nullable=False, default=0)    # "back again" emails so far; lengthens the clear time
    present_since = db.Column(db.DateTime(timezone=True))   # start of the current unbroken presence; NULL while gone
    recovery_notified_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.Index("ux_alert_incidents_open_key", "incident_key", unique=True,
                 postgresql_where=db.text("resolved_at IS NULL"), sqlite_where=db.text("resolved_at IS NULL")),
        db.Index("ix_alert_incidents_resolved_at", "resolved_at"),
    )
