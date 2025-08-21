import os
import sys
import pathlib
import math

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.quality import QualityService
from api.services.loggers import LoggerService
from config import Config
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError

app = create_app()
weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
quality_service = QualityService(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)
logger_service = LoggerService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)

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
# add M asl as unit for water surface elevation

LOGGER_CONFIG = {
    # sensor_sn_base: { "logger_num": #, "station_id": #, "z": #, "L": #, "theta": # }
    "22168653": { "logger_num": 1, "station_id": 2577531, "z": 39.701, "L": 1.525, "theta": 57.7 },
    "22168654": { "logger_num": 2, "station_id": 2577532, "z": 39.767, "L": 1.781, "theta": 46.5 },
    "22168655": { "logger_num": 3, "station_id": 2577533, "z": 39.711, "L": 1.685, "theta": 49.1 },
    "22168656": { "logger_num": 4, "station_id": 2577534, "z": 39.736, "L": 1.62, "theta": 55.2 },
    "22168657": { "logger_num": 5, "station_id": 2577535, "z": 39.568, "L": 1.75, "theta": 48.4 },
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

def parse_logger_entry(entry):
    sensor_sn = entry.get("sensor_sn", "")
    sn_parts = sensor_sn.split('-')
    if len(sn_parts) != 2:
        return None

    base_sn, metric_suffix = sn_parts
    if base_sn not in LOGGER_CONFIG:
        return None

    config = LOGGER_CONFIG[base_sn]
    station_id = config["station_id"]
    h = float(entry.get("value", 0))
    recorded_at = datetime.fromisoformat(entry.get("timestamp"))
    
    measurement = None
    
    if metric_suffix == '1':
        z = config["z"]
        L = config["L"]
        theta = config["theta"]
        wse = z - L * math.cos(math.radians(theta)) + h
        measurement = SensorMeasurement(
            station_id=station_id,
            group_type="Logger",
            measurement_type="Water Surface Elevation",
            value=wse,
            unit="m",
            recorded_at=recorded_at
        )
    elif metric_suffix == '3':
        measurement = SensorMeasurement(
            station_id=station_id,
            group_type="Logger",
            measurement_type="Water Temperature",
            value=h,
            unit=entry.get("unit"),
            recorded_at=recorded_at
        )
        
    return measurement

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

    latest = db.session.query(SensorMeasurement.recorded_at).filter_by(
        group_type="Quality"
    ).order_by(SensorMeasurement.recorded_at.desc()).first()

    all_quality_entries = []
    
    # --- NEW CHUNKING LOGIC ---
    date_format = "%Y-%m-%d %H:%M:%S"
    # Start from the latest record, or a default if none exist
    start_dt = latest[0] if latest else datetime.strptime("2025-05-08 11:00:00", date_format)
    final_end_dt = datetime.now(timezone.utc)

    # Ensure start_dt is timezone-aware
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    print("[INFO] Fetching new quality data in chunks if necessary...")
    current_start_dt = start_dt
    while current_start_dt < final_end_dt:
        chunk_end_dt = current_start_dt + timedelta(days=89)
        if chunk_end_dt > final_end_dt:
            chunk_end_dt = final_end_dt

        start_str = current_start_dt.strftime(date_format)
        end_str = chunk_end_dt.strftime(date_format)

        print(f"  - Fetching quality data from {start_str} to {end_str}")
        
        entries = quality_service.get_quality_data(start_str, end_str)
        all_quality_entries.extend(entries)
        
        current_start_dt = chunk_end_dt + timedelta(seconds=1)
    # --- END CHUNKING LOGIC ---

    quality_data = []
    for entry in all_quality_entries:
        try:
            objs = parse_quality_entry(entry, station_id)
            quality_data.extend(objs)
        except Exception as e:
            print(f"[ERROR] Failed to parse quality entry: {e}")

    if return_only:
        return quality_data

def inject_new_logger_data(return_only=False):
    latest = db.session.query(SensorMeasurement.recorded_at).filter_by(
        group_type="Logger"
    ).order_by(SensorMeasurement.recorded_at.desc()).first()

    start_time = latest[0].isoformat() if latest else None
    entries = logger_service.get_logger_data(start_time=start_time)

    logger_data = []
    for entry in entries:
        try:
            obj = parse_logger_entry(entry)
            if obj:
                logger_data.append(obj)
        except Exception as e:
            print(f"[ERROR] Failed to parse logger entry: {e}")

    if return_only:
        return logger_data

    inserted = 0
    for obj in sorted(logger_data, key=lambda x: x.recorded_at):
        try:
            db.session.add(obj)
            db.session.commit()
            inserted += 1
            print(f"[NEW] Inserted: {obj.measurement_type} = {obj.recorded_at} with value {obj.value} {obj.unit}")
        except IntegrityError:
            db.session.rollback()
        except Exception as e:
            print(f"[ERROR] Failed to insert logger record: {e}")
            db.session.rollback()
    
    print(f"[INFO] Inserted {inserted} new logger records.")

def inject_all_new_data():
    with app.app_context():
        weather_data = inject_new_weather_data(return_only=True)
        quality_data = inject_new_quality_data(return_only=True)
        logger_data = inject_new_logger_data(return_only=True)

        all_data = sorted(weather_data + quality_data + logger_data, key=lambda x: x.recorded_at)

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
