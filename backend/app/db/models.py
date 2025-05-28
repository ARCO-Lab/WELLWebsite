from db.database import db

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
        return {
            "station_id", self.station_id,
            "group_type", self.group_type,
            "measurement_type", self.measurement_type,
            "value", self.value,
            "unit", self.unit,
            "timestamp", self.recorded_at.isoformat()
        }