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
        db.Index("idx_sensor_group_recorded", "group_type", "recorded_at"),
        db.Index("idx_sensor_station_type_recorded", "station_id", "measurement_type", "recorded_at"),
        db.Index("idx_sensor_recorded_asc", "recorded_at"),
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


class SensorMeasurementAgg30Min(db.Model):
    __tablename__ = "sensor_measurements_agg_30min"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg30m_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg30m_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg30m"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "30min",
        }


class SensorMeasurementAgg1Hour(db.Model):
    __tablename__ = "sensor_measurements_agg_1hour"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg1h_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg1h_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg1h"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "1hour",
        }


class SensorMeasurementAgg3Hour(db.Model):
    __tablename__ = "sensor_measurements_agg_3hour"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg3h_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg3h_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg3h"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "3hour",
        }


class SensorMeasurementAgg6Hour(db.Model):
    __tablename__ = "sensor_measurements_agg_6hour"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg6h_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg6h_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg6h"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "6hour",
        }


class SensorMeasurementAgg12Hour(db.Model):
    __tablename__ = "sensor_measurements_agg_12hour"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg12h_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg12h_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg12h"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "12hour",
        }


class SensorMeasurementAgg24Hour(db.Model):
    __tablename__ = "sensor_measurements_agg_24hour"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg24h_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg24h_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg24h"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "24hour",
        }


class SensorMeasurementAgg1Week(db.Model):
    __tablename__ = "sensor_measurements_agg_1week"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.String, nullable=False)
    group_type = db.Column(db.String, nullable=False)
    measurement_type = db.Column(db.String, nullable=False)
    unit = db.Column(db.String, nullable=False)
    bucket_start = db.Column(db.DateTime, nullable=False, index=True)

    value_min = db.Column(db.Float, nullable=True)
    value_max = db.Column(db.Float, nullable=True)
    value_avg = db.Column(db.Float, nullable=True)
    value_sum = db.Column(db.Float, nullable=True)
    value_count = db.Column(db.Integer, nullable=False, default=0)

    has_nulls = db.Column(db.Boolean, nullable=False, default=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=est_now)

    __table_args__ = (
        db.Index(
            "idx_agg1w_group_station_type_bucket",
            "group_type",
            "station_id",
            "measurement_type",
            "bucket_start",
        ),
        db.Index("idx_agg1w_bucket_asc", "bucket_start"),
        db.UniqueConstraint("station_id", "measurement_type", "bucket_start", name="uq_agg1w"),
    )

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "group_type": self.group_type,
            "measurement_type": self.measurement_type,
            "unit": self.unit,
            "recorded_at": self.bucket_start.isoformat(),
            "value": self.value_avg,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "value_count": self.value_count,
            "has_nulls": self.has_nulls,
            "granularity": "1week",
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