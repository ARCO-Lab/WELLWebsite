# This file defines the /api/analysis/recent route for generating concise, actionable summaries of the most recent environmental sensor readings.
# It filters and formats logger, weather, and quality data, then uses an LLM to produce a structured analysis for frontend display.

from flask import request, jsonify
import json

# Embedded config for loggers
LOGGER_CONFIG = {
    'sites': {
        "2577531": "Logger 1",
        "2577532": "Logger 2",
        "2577533": "Logger 3",
        "2577534": "Logger 4",
        "2577535": "Logger 5",
    },
    'metrics': ["Water Surface Elevation", "Water Temperature"],
}

def register_analysis_recent_route(app, latest_metrics_cache, client):
    @app.route("/api/analysis/recent", methods=["GET"])
    def analyze_recent():
        # Get analysis type and subtypes from query parameters
        analysis_type = request.args.get("type")
        subtypes = request.args.getlist("subtypes")

        # Validate analysis type
        if analysis_type not in ["weather", "logger", "quality"]:
            return jsonify({"error": "Invalid or missing type. Must be one of: weather, logger, quality."}), 400

        # Use cached latest metrics as the data source
        results = [
            r for r in latest_metrics_cache["data"]
            if r["group_type"].lower() == analysis_type.lower()
        ]

        station_context = ""
        if analysis_type == "logger":
            # Prepare logger IDs and metrics
            all_logger_ids = list(LOGGER_CONFIG['sites'].keys())
            all_logger_metrics = LOGGER_CONFIG['metrics']
            
            # 1. Determine which station IDs to analyze
            selected_stations = [s for s in subtypes if s in all_logger_ids]
            if "All Loggers" in subtypes or not selected_stations:
                selected_stations = all_logger_ids

            # 2. Determine which metrics to analyze
            selected_metrics = [s for s in subtypes if s in all_logger_metrics]
            if not selected_metrics:
                selected_metrics = all_logger_metrics

            # 3. Filter the results based on selected stations and metrics
            results = [
                r for r in results 
                if str(r['station_id']) in selected_stations and r['measurement_type'] in selected_metrics
            ]
            
            # 4. Create context with friendly names
            station_names = [LOGGER_CONFIG['sites'].get(sid, sid) for sid in selected_stations]
            station_context = f"The following data is for Water Logger(s): {', '.join(station_names)}."
        
        elif subtypes:
            # Filter results for weather and quality types based on subtypes
            results = [
                r for r in results
                if r["measurement_type"].lower().replace(" ", "") in [s.lower().replace(" ", "") for s in subtypes]
            ]

        # If no data after filtering, return a message
        if not results:
            return jsonify({"analysis": "No data available for the selected filters."})

        # Prepare data for prompt (truncate if too long)
        raw_data = json.dumps(results)
        if len(raw_data) > 4000:
            raw_data = raw_data[:4000]

        # Build prompt for LLM analysis
        prompt = f"""
            You are an environmental data analyst. Analyze monitoring station data and provide a concise report focusing on anomalies and key insights.

            Data Format
            JSON records with: group_type, measurement_type, recorded_at, station_id, unit, value

            Analysis Priorities by Group Type
            CRITICAL ALERTS (mention first):
            Water Quality:

            Dissolved oxygen <5 mg/L (fish kill risk)
            Extreme water temperature deviations (>25°C or <5°C)
            High turbidity spikes (>50 NTU)
            Conductivity anomalies indicating pollution events
            Total suspended solids exceeding normal ranges
            Weather Station:

            Severe weather: wind speed >15 m/s, gust speed >20 m/s
            Barometric pressure drops >10 mbar/hr (storm systems)
            Heavy precipitation events (>25 mm/hr)
            Extreme air temperature deviations (>35°C or <-20°C)
            Solar radiation anomalies during daylight hours
            Water Loggers:

            Rapid water surface elevation changes (>0.5m/hr)
            Water temperature spikes or drops (>5°C change/hr)
            Equipment malfunction indicators (data gaps, sensor drift)
            KEY PARAMETERS TO MONITOR:
            Water Quality Group:

            Dissolved Oxygen (ODO) & Saturation (ODOSat): Fish habitat viability
            Water Temperature: Ecosystem health indicator
            Turbidity & Total Suspended Solids: Water clarity and sediment load
            Conductivity & Salinity: Chemical composition changes
            Total Dissolved Solids: Overall water quality
            Weather Station Group:

            Air Temperature & Dew Point: Atmospheric conditions
            Barometric Pressure: Weather system tracking
            Wind Speed, Gust Speed & Direction: Storm monitoring
            Rainfall: Precipitation patterns and flood risk
            Relative Humidity & Vapor Pressure: Moisture conditions
            Solar Radiation: Energy input and weather patterns
            Water Loggers Group:

            Water Surface Elevation: Water level trends and flood risk
            Water Temperature: Thermal conditions in water bodies
            Output Format (250 tokens max)
            ALERTS: List any critical issues first by group type KEY FINDINGS: 2-3 most significant observations across all groups CORRELATIONS: Notable relationships between parameters (e.g., rainfall vs water elevation) SUMMARY: 1-2 brief jot notes on overall environmental conditions

            Style Guidelines
            Bullet points for efficiency
            Numbers with context (e.g., "16°C water temp, normal for season")
            Flag unusual values clearly with group context
            Be concise but actionable
            Prioritize immediate safety/environmental concerns

            **STRICT FORMATTING REQUIREMENTS:**
                - Use exactly this structure: **SECTION NAME:** followed by content
                - For bullet points, use format: - **Subsection name:** description
                - Always use double asterisks (**) for all headings and subheadings
                - Use single line breaks (\n) between bullet points
                - Use double line breaks (\n\n) between major sections
                - Do not use extra spacing or special characters
                - End each bullet point description on the same line (no line breaks within descriptions)
                - Ensure consistent capitalization: **SECTION NAME:** (all caps for main sections)

            Data:
            {raw_data}
        """

        # Call the LLM client to get analysis
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3
        )

        return jsonify({"analysis": response.choices[0].message.content})