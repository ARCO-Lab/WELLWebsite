from flask import request, jsonify
import json

def register_analysis_alltime_route(app, latest_summaries, client):
    @app.route("/api/analysis/alltime", methods=["GET"])
    def analyze_data():
        analysis_type = request.args.get("type")
        subtypes = request.args.getlist("subtypes")  # Supports ?subtypes=A&subtypes=B

        if analysis_type not in ["weather", "logger", "quality"]:
            return jsonify({"error": "Invalid or missing type. Must be one of: weather, logger, quality."}), 400

        summary = latest_summaries["data"].get(analysis_type)
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
