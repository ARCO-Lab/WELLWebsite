# This file defines the /api/data route for retrieving and filtering raw sensor measurement data from the database.
# It also triggers background summarization for weather, logger, and quality data.

from flask import request, jsonify
import pandas as pd
from db.database import db
from db.models import SensorMeasurement
from datetime import datetime
from scripts.downsample import downsample
import threading

def register_data_route(app, latest_summaries):
    @app.route("/api/data", methods=["GET"])
    def get_filtered_data():
        # Parse query parameters
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

        # Query the database for matching sensor measurements
        query = db.session.query(SensorMeasurement).filter(
            SensorMeasurement.group_type.in_(group_types),
            SensorMeasurement.recorded_at.between(start_dt, end_dt)
        )

        # Format query results as a list of dicts
        data = [
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

        df = pd.DataFrame(data)

        def background_summarize(df):
            # Split data by group type
            weather_df = df[df["group_type"] == "Weather"]
            logger_df = df[df["group_type"] == "Logger"]
            quality_df = df[df["group_type"] == "Quality"]

            # Downsample and summarize each group
            weather_summary, logger_summary, quality_summary = downsample(weather_df, logger_df, quality_df)

            # Store summaries in shared state
            latest_summaries["data"] = {
                "weather": weather_summary,
                "logger": logger_summary,
                "quality": quality_summary
            }

        # Start background thread for summarization
        threading.Thread(target=background_summarize, args=(df,)).start()

        # Return the raw data immediately
        return jsonify(data)