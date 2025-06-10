from flask import request, jsonify
import json
from analysis.downsample import METRIC_NAME_MAP

def register_analysis_recent_route(app, latest_metrics_cache, client):
    @app.route("/api/analysis/recent", methods=["GET"])
    def analyze_recent():
        analysis_type = request.args.get("type")
        subtypes = request.args.getlist("subtypes")

        if analysis_type not in ["weather", "logger", "quality"]:
            return jsonify({"error": "Invalid or missing type. Must be one of: weather, logger, quality."}), 400

        # Use cached latest metrics
        results = [
            r for r in latest_metrics_cache["data"]
            if r["group_type"].lower() == analysis_type.lower()
        ]

        # Filter by subtypes if needed
        if subtypes:
            results = [
                r for r in results
                if r["measurement_type"].lower().replace(" ", "") in [s.lower().replace(" ", "") for s in subtypes]
            ]
        for r in results:
            r["measurement_type"] = METRIC_NAME_MAP.get(r["measurement_type"], r["measurement_type"])

        raw_data = json.dumps(results)
        if len(raw_data) > 4000:
            raw_data = raw_data[:4000]

        prompt = f"""
            You are an environmental data analyst. Analyze monitoring station data and provide a concise report focusing on anomalies and key insights.
            Data Format
            JSON records with: group_type, measurement_type, recorded_at, station_id, unit, value
            Analysis Priorities
            CRITICAL ALERTS (mention first):

            Dissolved oxygen <5 mg/L (fish kill risk)
            Extreme temperature deviations (air/water)
            High turbidity spikes (>50 NTU)
            Severe weather: wind >15 m/s, pressure drops >10 mbar/hr
            Heavy precipitation events (>25 mm/hr)

            KEY PARAMETERS:

            Water Quality: Temperature, DO, conductivity, turbidity, salinity
            Weather: Air temp, humidity, pressure, wind, precipitation
            Equipment: Battery levels, data gaps, sensor issues

            Output Format (250 tokens max)
            ALERTS: List any critical issues first
            KEY FINDINGS: 2-3 most significant observations
            CORRELATIONS: Notable relationships between parameters
            SUMMARY: 1-2 brief jot notes on overall conditions
            Style

            Bullet points for efficiency
            Numbers with context (e.g., "16°C water temp, normal for season")
            Flag unusual values clearly
            Be concise but actionable

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