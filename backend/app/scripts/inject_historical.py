import os, sys, pathlib
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services import WeatherService
from config import Config

app = create_app()

weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)   

START_DATE = "2025-05-09 15:20:00"
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
    with app.app_context():
        logger_id = Config.HOBO_LOGGERS.split(",")[0]
        print("[INFO] Clearing existing records ...")
        SensorMeasurement.query.delete()
        db.session.commit()

        print(f"[INFO] Fetching weather data from {START_DATE} to {END_DATE}")
        entries = weather_service.get_weather_data(START_DATE, END_DATE)

        if not entries:
            print ("[WARN] No data found.")
            return
        
        total_inserted = 0
        for entry in entries:
            obj = parse_weather_entry(entry, logger_id)
            try:
                db.session.add(obj)
                db.session.commit()
                total_inserted += 1
            except IntegrityError:
                db.session.rollback()
            except Exception as e:
                print(f"[ERROR] Failed to insert record: {e}")
                db.session.rollback()
        
        print(f"[DONE] Inserted {total_inserted} historical records.")

if __name__ == "__main__":
    inject_all_weather_history()