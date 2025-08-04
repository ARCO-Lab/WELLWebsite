from flask import request, jsonify
import json

# Configuration for loggers, embedded directly in the file.
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

def register_analysis_alltime_route(app, latest_summaries, client):
    @app.route("/api/analysis/alltime", methods=["GET"])
    def analyze_data():
        analysis_type = request.args.get("type")
        subtypes = request.args.getlist("subtypes")

        if analysis_type not in ["weather", "logger", "quality"]:
            return jsonify({"error": "Invalid or missing type. Must be one of: weather, logger, quality."}), 400

        summary = latest_summaries["data"].get(analysis_type)
        if not summary:
            return jsonify({"error": f"No summary data available for {analysis_type}"}), 404

        station_context = ""
        if analysis_type == "logger":
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

            # 3. Build the final summary by filtering both stations and their metrics
            filtered_summary = {}
            for station_id in selected_stations:
                if station_id in summary:
                    station_data = summary[station_id]
                    filtered_metrics = {
                        metric_name: metric_data for metric_name, metric_data in station_data.items()
                        if metric_name in selected_metrics
                    }
                    if filtered_metrics:
                        filtered_summary[station_id] = filtered_metrics
            
            summary = filtered_summary

            # 4. Create context with friendly names
            station_names = [LOGGER_CONFIG['sites'].get(sid, sid) for sid in selected_stations]
            station_context = f"The following data is for Water Logger(s): {', '.join(station_names)}."
        
        elif subtypes:
            # Original logic for weather and quality
            summary = {
                k: v for k, v in summary.items()
                if k.lower().replace(" ", "") in [s.lower().replace(" ", "") for s in subtypes]
            }

        if not summary:
            return jsonify({"analysis": "No data available for the selected filters. Please select at least one logger or metric."})

        raw_data = json.dumps(summary)
        if len(raw_data) > 4000:
            raw_data = raw_data[:4000]

        prompt = f"""
            You are an expert environmental data analyst. {station_context} Analyze the provided sensor data and identify:

            TRENDS (1-3 bullet points)
            Key patterns over time (increasing/decreasing values, seasonal changes, etc.)

            CORRELATIONS (1-3 bullet points)
            Relationships between different parameters (temperature vs humidity, etc.)

            ANOMALIES (1-3 bullet points)
            Unusual readings or sudden changes that deviate from normal patterns

            SUMMARY (1-2 sentences)
            Overall data health and key insights

            Format as bullet points. Keep total response under 200 words. Focus on actionable insights relevant to environmental monitoring.

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

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3
        )

        return jsonify({"analysis": response.choices[0].message.content})