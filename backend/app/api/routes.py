from flask import request, jsonify
from config import Config
from db.database import db
from db.models import SensorMeasurement
from api.services import WeatherService
from datetime import datetime

# Keep existing weather service endpoint (optional)
weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)

def register_routes(app):
    # Existing HOBO API passthrough
    app.add_url_rule("/api/weather", "get_weather", lambda: jsonify(weather_service.get_weather_data()))

    # ✅ New endpoint to query historical/filtered database data
    @app.route("/api/data", methods=["GET"])
    def get_filtered_data():
        start = request.args.get("start")
        end = request.args.get("end")
        group_types = request.args.getlist("group_type")

        if not start or not end or not group_types:
            return jsonify({"error": "Missing required parameters"}), 400

        try:
            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400

        query = db.session.query(SensorMeasurement).filter(
            SensorMeasurement.group_type.in_(group_types),
            SensorMeasurement.recorded_at.between(start_dt, end_dt)
        )

        results = [
            {
                "station_id": r.station_id,
                "group_type": r.group_type,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }
            for r in query.order_by(SensorMeasurement.recorded_at).all()
        ]

        return jsonify(results)