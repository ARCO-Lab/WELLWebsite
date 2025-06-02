import os
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.quality import QualityService
from config import Config
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError

app = create_app()
weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
quality_service = QualityService(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)

QUALITY_PARAM_ID_MAP = {
    125001: {"key": "Water Temperature", "unit": "°C"},
    125002: {"key": "Conductivity", "unit": "uS/cm"},
    125004: {"key": "Salinity", "unit": "PPT"},
    125005: {"key": "TDS", "unit": "g/L"},
    125006: {"key": "ODO", "unit": "mg/L"},
    125007: {"key": "ODOSat", "unit": "%"},
    125008: {"key": "Turbidity", "unit": "NTU"},
    125009: {"key": "TSS", "unit": "mg/L"}
}

def parse_weather_entry(entry, logger_id):
    sensor_sn = entry.get("sensor_sn")
    measurement_type = entry.get("sensor_measurement_type")
    value = float(entry.get("value", 0))
    unit = entry.get("unit", "")
    timestamp = datetime.fromisoformat(entry.get("timestamp"))

    if sensor_sn == "21948438-1":
        measurement_type = "Soil Temperature"
    elif sensor_sn == "22154270-1":
        measurement_type = "Air Temperature"
    if sensor_sn == "21948438-2":
        measurement_type = "Relative Humidity"

    return SensorMeasurement(
        station_id=logger_id,
        group_type="Weather",
        measurement_type=measurement_type,
        value=value,
        unit=unit,
        recorded_at=timestamp
    )

def parse_quality_entry(entry, station_id):
    timestamp = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    results = []
    for reading in entry["values"]:
        param_id = reading["parameterId"]
        if param_id not in QUALITY_PARAM_ID_MAP:
            continue
        try:
            value = float(reading["value"])
        except (ValueError, TypeError):
            continue
        results.append(SensorMeasurement(
            station_id=station_id,
            group_type="Quality",
            measurement_type=QUALITY_PARAM_ID_MAP[param_id]["key"],
            value=value,
            unit=QUALITY_PARAM_ID_MAP[param_id]["unit"],
            recorded_at=timestamp
        ))
    return results

def inject_new_weather_data(return_only=False):
    logger_id = Config.HOBO_LOGGERS.split(",")[0]

    # Get the most recent timestamp for weather data
    latest = db.session.query(SensorMeasurement.recorded_at).filter_by(
        group_type="Weather"
    ).order_by(SensorMeasurement.recorded_at.desc()).first()

    start_time = latest[0].isoformat() if latest else None
    entries = weather_service.get_weather_data(start_time=start_time)

    weather_data = []
    for entry in entries:
        try:
            obj = parse_weather_entry(entry, logger_id)
            weather_data.append(obj)
        except Exception as e:
            print(f"[ERROR] Failed to parse weather entry: {e}")

    if return_only:
        return weather_data

    inserted = 0
    for obj in sorted(weather_data, key=lambda x: x.recorded_at):
        try:
            db.session.add(obj)
            db.session.commit()
            inserted += 1
            print(f"[NEW] Inserted: {obj.measurement_type} = {obj.recorded_at} with value {obj.value} {obj.unit}")
        except IntegrityError:
            db.session.rollback()
        except Exception as e:
            print(f"[ERROR] Failed to insert weather record: {e}")
            db.session.rollback()

    print(f"[INFO] Inserted {inserted} new weather records.")

def inject_new_quality_data(return_only=False):
    station_id = Config.WQ_DEVICE_ID

    # Get the most recent timestamp for quality data
    latest = db.session.query(SensorMeasurement.recorded_at).filter_by(
        group_type="Quality"
    ).order_by(SensorMeasurement.recorded_at.desc()).first()

    start_time = latest[0].strftime("%Y-%m-%d %H:%M:%S") if latest else None
    entries = quality_service.get_quality_data(start_time=start_time)
    
    quality_data = []
    for entry in entries:
        try:
            objs = parse_quality_entry(entry, station_id)
            quality_data.extend(objs)
        except Exception as e:
            print(f"[ERROR] Failed to parse quality entry: {e}")

    if return_only:
        return quality_data

    inserted = 0
    for obj in sorted(quality_data, key=lambda x: x.recorded_at):
        try:
            db.session.add(obj)
            db.session.commit()
            inserted += 1
            print(f"[NEW] Inserted: {obj.measurement_type} = {obj.recorded_at} with value {obj.value} {obj.unit}")
        except IntegrityError:
            db.session.rollback()
        except Exception as e:
            print(f"[ERROR] Failed to insert quality record: {e}")
            db.session.rollback()

    print(f"[INFO] Inserted {inserted} new quality records.")

def inject_all_new_data():
    with app.app_context():
        weather_data = inject_new_weather_data(return_only=True)
        quality_data = inject_new_quality_data(return_only=True)

        all_data = sorted(weather_data + quality_data, key=lambda x: x.recorded_at)

        inserted = 0
        for obj in all_data:
            try:
                db.session.add(obj)
                db.session.commit()
                inserted += 1
                print(f"[NEW] Inserted: {obj.measurement_type} = {obj.recorded_at} with value {obj.value} {obj.unit}")
            except IntegrityError:
                db.session.rollback()
            except Exception as e:
                print(f"[ERROR] Failed to insert record: {e}")
                db.session.rollback()

        print(f"[INFO] Inserted {inserted} new total records.")

if __name__ == "__main__":
    print("[INFO] Starting new data injection...")
    try:
        inject_all_new_data()
    except Exception as e:
        print(f"[ERROR] An error occurred during injection: {e}")
