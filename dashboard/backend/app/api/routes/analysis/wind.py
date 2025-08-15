from flask import request, jsonify
import json

def register_analysis_wind_route(app, latest_summaries, client):
    @app.route("/api/analysis/wind", methods=["GET"])
    def analyze_wind():
        subtypes = request.args.getlist("subtypes")  # e.g. ["wind", "gust"]

        # Validate subtypes
        valid_subtypes = {"wind", "gust"}
        selected = set(s.lower() for s in subtypes if s.lower() in valid_subtypes)
        if not selected:
            return jsonify({"error": "Missing or invalid subtypes. Use subtypes=wind and/or subtypes=gust."}), 400

        # Get the latest wind data summary (replace with your actual data source)
        summary = latest_summaries["data"].get("weather")
        if not summary:
            return jsonify({"error": "No summary data available for weather"}), 404

        # Prepare the data to downsample and send to the model
        metrics = []
        if "wind" in selected:
            metrics.extend(["Wind Speed", "Wind Direction"])
        if "gust" in selected:
            metrics.extend(["Gust Speed", "Wind Direction"])
        # Remove duplicates
        metrics = list(set(metrics))

        # Filter and downsample
        filtered = {k: v for k, v in summary.items() if k in metrics}

        # Compose the prompt for the model
        prompt = f"""
            You are a meteorological analyst specializing in wind climatology. Analyze this wind rose data and provide a concise professional assessment in the following structured format:
            Data Handling Instructions:

            If only wind speed and wind direction are available: Provide analysis under "Wind Speed:" section only
            If only gust speed and gust direction are available: Provide analysis under "Gust Speed:" section only
            If wind speed, wind direction, AND gust speed are available: Provide separate analyses under both "Wind Speed:" and "Gust Speed:" sections, comparing gust factors across directions

            Required Output Format:
            Wind Speed: (if wind speed data available)

            Dominant flow patterns: [prevailing directions, secondary modes, directional persistence]
            Speed-direction relationships: [directional speed signatures, terrain effects, thermal patterns]
            Terrain/microclimate indicators: [channeling effects, topographic influences]
            Energy/environmental applications: [wind energy potential, ventilation, dispersion]

            Gust Speed: (if gust data available)

            Gust factor analysis: [gust/sustained ratios across directions, turbulence sources]
            Convective vs mechanical signatures: [thermal instability vs terrain roughness indicators]
            Extreme event patterns: [storm signatures, frontal passages, convective bursts]
            Turbulence characteristics: [directional turbulence intensity, stability indicators]

            Analysis Framework:
            Focus on prevailing directions, speed-direction correlations, terrain channeling, thermal effects, gust factors (when available), turbulence patterns, energy applications, and weather system signatures.
            Limit total response to 250 tokens maximum. Use bullet points under each section header. Prioritize actionable meteorological insights with precise technical terminology.

            **STRICT FORMATTING REQUIREMENTS:**
                - Use exactly this structure: **SECTION NAME:** followed by content
                - For bullet points, use format: - **Subsection name:** description
                - Always use double asterisks (**) for all headings and subheadings
                - Use single line breaks (\n) between bullet points
                - Use double line breaks (\n\n) between major sections
                - Do not use extra spacing or special characters
                - End each bullet point description on the same line (no line breaks within descriptions)
                - Ensure consistent capitalization: **SECTION NAME:** (all caps for main sections)
            {json.dumps(filtered)}
        """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3
        )

        return jsonify({"analysis": response.choices[0].message.content})