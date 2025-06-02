from flask import request, jsonify
import json
import pandas as pd
from config import Config
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.quality import QualityService
from datetime import datetime
from analysis.downsample import downsample
import threading
from openai import OpenAI 

# Keep existing weather service endpoint (optional)
weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
latest_summaries = {}

def register_routes(app):
    # Existing HOBO API passthrough
    app.add_url_rule("/api/weather", "get_weather", lambda: jsonify(weather_service.get_weather_data()))

    @app.route("/api/data", methods=["GET"])
    def get_filtered_data():
        global latest_summaries

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
            weather_df = df[df["group_type"] == "Weather"]
            logger_df = df[df["group_type"] == "Logger"]
            quality_df = df[df["group_type"] == "Quality"]

            weather_summary, logger_summary, quality_summary = downsample(weather_df, logger_df, quality_df)

            # Store latest summaries globally
            global latest_summaries
            latest_summaries = {
                "weather": weather_summary,
                "logger": logger_summary,
                "quality": quality_summary
            }

        # Start background thread for summarization
        threading.Thread(target=background_summarize, args=(df,)).start()

        # Return the raw data immediately
        return jsonify(data)
    
    @app.route("/api/latest", methods=["GET"])
    def get_latest_metrics():
        subquery = db.session.query(
            SensorMeasurement.measurement_type,
            db.func.max(SensorMeasurement.recorded_at).label("max_time")
        ).group_by(SensorMeasurement.measurement_type).subquery()

        query = db.session.query(SensorMeasurement).join(
            subquery,
            db.and_(
                SensorMeasurement.measurement_type == subquery.c.measurement_type,
                SensorMeasurement.recorded_at == subquery.c.max_time
            )
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
            for r in query.all()
        ]
        return jsonify(results)

    client = OpenAI()

    @app.route("/api/analysis", methods=["GET"])
    def analyze_data():
        analysis_type = request.args.get("type")
        subtypes = request.args.getlist("subtypes")  # Supports ?subtypes=A&subtypes=B

        if analysis_type not in ["weather", "logger", "quality"]:
            return jsonify({"error": "Invalid or missing type. Must be one of: weather, logger, quality."}), 400

        summary = latest_summaries.get(analysis_type)
        if not summary:
            return jsonify({"error": f"No summary data available for {analysis_type}"}), 404

        # Filter by subtypes if needed
        if subtypes:
            summary = {
                k: v for k, v in summary.items()
                if k.lower().replace(" ", "") in [s.lower().replace(" ", "") for s in subtypes]
            }

        # Prepare JSON summary, truncate to ~1000 tokens
        raw_data = json.dumps(summary)
        if len(raw_data) > 4000:  # approx 4 chars per token
            raw_data = raw_data[:4000]

        # Construct prompt
        prompt = f"""
    You are an expert environmental data analyst. Analyze the provided sensor data and identify:

    TRENDS (1-3 bullet points)
    Key patterns over time (increasing/decreasing values, seasonal changes, etc.)

    CORRELATIONS (1-3 bullet points)
    Relationships between different parameters (temperature vs humidity, etc.)

    ANOMALIES (1-3 bullet points)
    Unusual readings or sudden changes that deviate from normal patterns

    SUMMARY (1-2 sentences)
    Overall data health and key insights

    Format as bullet points. Keep total response under 200 words. Focus on actionable insights relevant to environmental monitoring.

    Data:
    {raw_data}
    """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.3
        )

        return jsonify({"analysis": response.choices[0].message.content})