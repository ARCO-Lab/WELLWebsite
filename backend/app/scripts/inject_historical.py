import os, sys, pathlib
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.quality import QualityService
from config import Config

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
    entries = quality_service.get_quality_data(START_DATE, END_DATE)
    all_quality = []
    for entry in entries:
        try:
            objs = parse_quality_entry(entry, station_id)
            all_quality.extend(objs)
        except Exception as e:
            print(f"[ERROR] Failed to parse quality entry: {e}")
    return all_quality

def inject_all_history():
    with app.app_context():
        print("[INFO] Clearing existing SensorMeasurement records ...")
        SensorMeasurement.query.delete()
        db.session.commit()

        print("[INFO] Fetching historical weather and quality data...")
        weather_data = inject_all_weather_history()
        quality_data = inject_all_quality_history()

        all_data = sorted(weather_data + quality_data, key=lambda x: x.recorded_at)
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
