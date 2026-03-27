# This file defines the SQLAlchemy ORM models for sensor and sampling measurements.
# It provides table schemas and utility methods for database operations.

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
    )

    def to_dict(self):
        # Convert model instance to dictionary for serialization
        return {
            "station_id", self.station_id,
            "group_type", self.group_type,
            "measurement_type", self.measurement_type,
            "value", self.value,
            "unit", self.unit,
            "timestamp", self.recorded_at.isoformat()
        }
    
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

    def to_dict(self):
        # Convert model instance to dictionary for serialization
        return {
            "id", self.id,
            "creek_id", self.creek_id,
            "site_id", self.site_id,
            "measurement_type", self.measurement_type,
            "value", self.value,
            "unit", self.unit,
            "timestamp", self.recorded_at.isoformat()
        }


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