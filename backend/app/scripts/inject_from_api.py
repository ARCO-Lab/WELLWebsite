import os
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from main import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services import WeatherService
from config import Config
from datetime import datetime
from sqlalchemy.exc import IntegrityError

app = create_app()
weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)

def parse_weather_entry(entry, logger_id):
    sensor_sn = entry.get("sensor_sn")
    measurement_type = entry.get("sensor_measurement_type")
    value = float(entry.get("value", 0))
    unit = entry.get("unit","")
    timestamp = datetime.fromisoformat(entry.get("timestamp"))

    # Distinguish between Soil and Air Temperature
    if sensor_sn == "22047792-1":
        measurement_type = "Soil Temperature"
    elif sensor_sn == "22154270-1":
        measurement_type = "Air Temperature"

    return SensorMeasurement(
        station_id=logger_id,
        group_type="Weather",
        measurement_type=measurement_type,
        value=value,
        unit=unit,
        recorded_at=timestamp
    )

def inject_weather_data():
    with app.app_context():
        logger_id = Config.HOBO_LOGGERS.split(",")[0]
        entries = weather_service.get_weather_data(logger_id)
        if not entries:
            print(f"[WARN] No data returned for logger {logger_id}")
            return
        
        total_inserted = 0
        for entry in entries:
            obj = parse_weather_entry(entry, logger_id)
            try: 
                db.session.add(obj)
                db.session.commit()
                total_inserted += 1
                print(f"[NEW] Inserted: {obj.measurement_type} = {obj.recorded_at} with value {obj.value} {obj.unit}")
            except IntegrityError:
                db.session.rollback()
            except Exception as e:
                print(f"[ERROR] Failed to insert record: {e}")
                db.session.rollback()
        
        print(f"[INFO] Inserted {total_inserted} records for logger {logger_id}")