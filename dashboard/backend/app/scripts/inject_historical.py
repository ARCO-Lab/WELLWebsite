# This script fetches and injects all historical weather, logger, and water quality data into the database.
# It clears existing SensorMeasurement records, retrieves data in chunks, parses, and inserts them in timestamp order.

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

START_DATE = "2025-05-08 11:00:00" #START_DATE = "2025-05-08 11:00:00"
END_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") # datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def parse_weather_entry(entry, logger_id):
    # Parse a single weather data entry into a SensorMeasurement object
    sensor_sn = entry.get("sensor_sn")
    
    # Skip battery sensors
    if sensor_sn and sensor_sn.endswith("-B"):
        return None
    
    measurement_type = entry.get("sensor_measurement_type")
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

def fetch_weather_chunk(start_str, end_str):
    # Fetch and parse weather data for a specific date range
    logger_id = Config.HOBO_LOGGERS.split(",")[0]
    entries = weather_service.get_weather_data(start_str, end_str)
    all_weather = []
    skipped = 0
    for entry in entries:
        try:
            obj = parse_weather_entry(entry, logger_id)
            if obj:  # Only append if not filtered (battery)
                all_weather.append(obj)
            else:
                skipped += 1
        except Exception as e:
            print(f"[ERROR] Failed to parse weather entry: {e}")
    return all_weather, skipped


# 4. Add a new function to parse logger entries
def parse_logger_entry(entry):
    # Parse a single logger data entry into a SensorMeasurement object
    sensor_sn = entry.get("sensor_sn", "")
    
    # Skip battery sensors
    if sensor_sn.endswith("-B"):
        return None
    
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

# 5. Add a new function to fetch and process logger data for a specific date range
def fetch_logger_chunk(start_str, end_str):
    # Fetch and parse logger data for a specific date range
    entries = logger_service.get_logger_data(start_str, end_str)
    all_logger_data = []
    skipped = 0
    for entry in entries:
        try:
            obj = parse_logger_entry(entry)
            if obj:
                all_logger_data.append(obj)
            else:
                skipped += 1
        except Exception as e:
            print(f"[ERROR] Failed to parse logger entry: {e}")
    return all_logger_data, skipped



def parse_quality_entry(entry, station_id):
    # Parse a single quality data entry into a list of SensorMeasurement objects
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

def fetch_quality_chunk(start_str, end_str):
    # Fetch and parse quality data for a specific date range (simplified to 30 days)
    station_id = Config.WQ_DEVICE_ID
    all_quality = []
    
    # Directly fetch quality data for this range (no sub-chunking)
    entries = quality_service.get_quality_data(start_str, end_str)
    
    for entry in entries:
        try:
            objs = parse_quality_entry(entry, station_id)
            all_quality.extend(objs)
        except Exception as e:
            print(f"[ERROR] Failed to parse quality entry: {e}")
    
    return all_quality

def inject_all_history():
    # Main function: clears DB, fetches and inserts data in chunks to avoid API truncation
    with app.app_context():
        print("[INFO] Clearing existing SensorMeasurement records ...")
        SensorMeasurement.query.delete()
        db.session.commit()
        
        # Reset the ID sequence to start from 1
        print("[INFO] Resetting ID sequence to 1...")
        db.session.execute(db.text("ALTER SEQUENCE sensor_measurements_id_seq RESTART WITH 1;"))
        db.session.commit()

        date_format = "%Y-%m-%d %H:%M:%S"
        current_start_dt = datetime.strptime(START_DATE, date_format)
        final_end_dt = datetime.strptime(END_DATE, date_format)
        
        # Ensure datetimes are timezone-aware
        if current_start_dt.tzinfo is None:
            current_start_dt = current_start_dt.replace(tzinfo=timezone.utc)
        if final_end_dt.tzinfo is None:
            final_end_dt = final_end_dt.replace(tzinfo=timezone.utc)

        # Calculate total chunks for progress tracking
        total_days = (final_end_dt - current_start_dt).days
        total_chunks = (total_days // 30) + (1 if total_days % 30 > 0 else 0)
        chunk_num = 0
        
        total_inserted = 0
        total_duplicates = 0
        
        print(f"[INFO] Processing {total_chunks} 30-day chunks...")
        
        while current_start_dt < final_end_dt:
            chunk_num += 1
            # Calculate chunk end (30 days)
            chunk_end_dt = current_start_dt + timedelta(days=30)
            if chunk_end_dt > final_end_dt:
                chunk_end_dt = final_end_dt

            start_str = current_start_dt.strftime(date_format)
            end_str = chunk_end_dt.strftime(date_format)
            
            print(f"\n[CHUNK {chunk_num}/{total_chunks}] Processing {start_str} to {end_str}")
            
            # Fetch data for this chunk
            print(f"  - Fetching weather data...")
            weather_data, weather_skipped = fetch_weather_chunk(start_str, end_str)
            print(f"    Fetched {len(weather_data)} weather records (skipped {weather_skipped} battery)")
            
            print(f"  - Fetching logger data...")
            logger_data, logger_skipped = fetch_logger_chunk(start_str, end_str)
            print(f"    Fetched {len(logger_data)} logger records (skipped {logger_skipped} battery)")
            
            print(f"  - Fetching quality data...")
            quality_data = fetch_quality_chunk(start_str, end_str)
            print(f"    Fetched {len(quality_data)} quality records")
            
            # Combine and sort chunk data
            chunk_data = sorted(weather_data + logger_data + quality_data, key=lambda x: x.recorded_at)
            print(f"  - Inserting {len(chunk_data)} records...")
            
            # Insert chunk data
            inserted = 0
            duplicates = 0
            for obj in chunk_data:
                try:
                    db.session.add(obj)
                    db.session.commit()
                    inserted += 1
                except IntegrityError:
                    db.session.rollback()
                    duplicates += 1
                except Exception as e:
                    print(f"[ERROR] Failed to insert record: {e}")
                    db.session.rollback()
            
            total_inserted += inserted
            total_duplicates += duplicates
            print(f"  - Inserted {inserted} records ({duplicates} duplicates skipped)")
            
            # Move to next chunk (no +1 second to prevent gaps/overlaps)
            current_start_dt = chunk_end_dt

        print(f"\n[DONE] Inserted {total_inserted} total records ({total_duplicates} duplicates skipped).")

if __name__ == "__main__":
    inject_all_history()
    print("[DONE] Historical data injection complete.")
