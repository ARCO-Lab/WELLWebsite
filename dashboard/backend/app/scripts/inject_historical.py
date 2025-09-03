import os, sys, pathlib
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError
import math

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.loggers import LoggerService
from api.services.quality import QualityService
from config import Config

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

LOGGER_CONFIG = {
    # sensor_sn_base: { "logger_num": #, "station_id": #, "z": #, "L": #, "theta": # }
    "22168653": { "logger_num": 1, "station_id": 2577531, "z": 39.701, "L": 1.525, "theta": 57.7 },
    "22168654": { "logger_num": 2, "station_id": 2577532, "z": 39.767, "L": 1.781, "theta": 46.5 },
    "22168655": { "logger_num": 3, "station_id": 2577533, "z": 39.711, "L": 1.685, "theta": 49.1 },
    "22168656": { "logger_num": 4, "station_id": 2577534, "z": 39.736, "L": 1.62, "theta": 55.2 },
    "22168657": { "logger_num": 5, "station_id": 2577535, "z": 39.568, "L": 1.75, "theta": 48.4 },
}

START_DATE = "2025-05-08 11:00:00"
END_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def parse_weather_entry(entry, logger_id):
    measurement_type = entry.get("sensor_measurement_type")
    sensor_sn = entry.get("sensor_sn")
    if measurement_type == "Temperature":
        if sensor_sn == "21948438-1":
            measurement_type = "Soil Temperature"
        elif sensor_sn == "22154270-1":
            measurement_type = "Air Temperature"
    if measurement_type == "RH":
        measurement_type = "Relative Humidity"

    return SensorMeasurement(
        station_id=logger_id,
        group_type="Weather",
        measurement_type=measurement_type,
        value=float(entry.get("value", 0)),
        unit=entry.get("unit"),
        recorded_at=datetime.fromisoformat(entry.get("timestamp"))
    )

def inject_all_weather_history():
    logger_id = Config.HOBO_LOGGERS.split(",")[0]
    entries = weather_service.get_weather_data(START_DATE, END_DATE)
    all_weather = []
    for entry in entries:
        try:
            obj = parse_weather_entry(entry, logger_id)
            all_weather.append(obj)
        except Exception as e:
            print(f"[ERROR] Failed to parse weather entry: {e}")
    return all_weather


# 4. Add a new function to parse logger entries
def parse_logger_entry(entry):
    sensor_sn = entry.get("sensor_sn", "")
    sn_parts = sensor_sn.split('-')
    if len(sn_parts) != 2:
        return None # Ignore entries with unexpected sensor_sn format

    base_sn, metric_suffix = sn_parts
    if base_sn not in LOGGER_CONFIG:
        return None # Ignore entries from unknown loggers

    config = LOGGER_CONFIG[base_sn]
    station_id = config["station_id"]
    h = float(entry.get("value", 0))
    recorded_at = datetime.fromisoformat(entry.get("timestamp"))
    
    measurement = None
    
    # Water Level -> Water Surface Elevation
    if metric_suffix == '1':
        z = config["z"]
        L = config["L"]
        theta = config["theta"]
        # w = z - L*(cos(theta)) + h
        wse = z - L * math.cos(math.radians(theta)) + h
        measurement = SensorMeasurement(
            station_id=station_id,
            group_type="Logger",
            measurement_type="Water Surface Elevation",
            value=wse,
            unit="m asl", # Assuming meters for WSE
            recorded_at=recorded_at
        )
    # Water Temperature
    elif metric_suffix == '3':
        measurement = SensorMeasurement(
            station_id=station_id,
            group_type="Logger",
            measurement_type="Water Temperature",
            value=h, # For temp, value is just the reading
            unit=entry.get("unit"),
            recorded_at=recorded_at
        )
        
    return measurement

# 5. Add a new function to fetch and process all logger history
def inject_all_logger_history():
    entries = logger_service.get_logger_data(START_DATE, END_DATE)
    all_logger_data = []
    for entry in entries:
        try:
            obj = parse_logger_entry(entry)
            if obj:
                all_logger_data.append(obj)
        except Exception as e:
            print(f"[ERROR] Failed to parse logger entry: {e} - {entry}")
    return all_logger_data



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

def inject_all_quality_history():
    station_id = Config.WQ_DEVICE_ID
    all_quality = []
    
    # --- NEW CHUNKING LOGIC ---
    date_format = "%Y-%m-%d %H:%M:%S"
    current_start_dt = datetime.strptime(START_DATE, date_format)
    final_end_dt = datetime.strptime(END_DATE, date_format)

    # Ensure start_dt is timezone-aware
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    print("[INFO] Fetching historical quality data in chunks...")
    while current_start_dt < final_end_dt:
        # Calculate the end of the 90-day chunk
        chunk_end_dt = current_start_dt + timedelta(days=89)
        if chunk_end_dt > final_end_dt:
            chunk_end_dt = final_end_dt

        start_str = current_start_dt.strftime(date_format)
        end_str = chunk_end_dt.strftime(date_format)
        
        print(f"  - Fetching quality data from {start_str} to {end_str}")
        
        # Fetch data for the current chunk
        entries = quality_service.get_quality_data(start_str, end_str)
        
        for entry in entries:
            try:
                objs = parse_quality_entry(entry, station_id)
                all_quality.extend(objs)
            except Exception as e:
                print(f"[ERROR] Failed to parse quality entry: {e}")
        
        # Move to the start of the next chunk
        current_start_dt = chunk_end_dt + timedelta(seconds=1)
    # --- END CHUNKING LOGIC ---
    
    return all_quality

def inject_all_history():
    with app.app_context():
        print("[INFO] Clearing existing SensorMeasurement records ...")
        SensorMeasurement.query.delete()
        db.session.commit()

        print("[INFO] Fetching historical data...")
        weather_data = inject_all_weather_history()
        quality_data = inject_all_quality_history()
        logger_data = inject_all_logger_history()

        all_data = sorted(weather_data + quality_data + logger_data, key=lambda x: x.recorded_at)
        print(f"[INFO] Inserting {len(all_data)} records sorted by timestamp...")

        inserted = 0
        for obj in all_data:
            try:
                db.session.add(obj)
                db.session.commit()
                inserted += 1
            except IntegrityError:
                db.session.rollback()
            except Exception as e:
                print(f"[ERROR] Failed to insert record: {e}")
                db.session.rollback()

        print(f"[DONE] Inserted {inserted} total records.")

if __name__ == "__main__":
    inject_all_history()
    print("[DONE] Historical data injection complete.")
