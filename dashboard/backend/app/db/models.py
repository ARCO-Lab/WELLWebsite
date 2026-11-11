# This file defines the SQLAlchemy ORM models for sensor and sampling measurements.
# Sensor readings, lab sampling results and export jobs each get one table.

from db.database import db
from utils.timezone import est_now

class SensorMeasurement(db.Model):
    __tablename__ = "sensor_measurements"
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String) # Weather, Quality, Logger
    measurement_type = db.Column(db.String)
    value = db.Column(db.Float)
    unit = db.Column(db.String)
    recorded_at = db.Column(db.DateTime, nullable=False)

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
    recovery_notified_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.Index("ux_alert_incidents_open_key", "incident_key", unique=True,
                 postgresql_where=db.text("resolved_at IS NULL"), sqlite_where=db.text("resolved_at IS NULL")),
        db.Index("ix_alert_incidents_resolved_at", "resolved_at"),
    )
