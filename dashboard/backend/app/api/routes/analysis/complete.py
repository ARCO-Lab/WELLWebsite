# This file defines the /api/analysis/complete route for comprehensive analysis of environmental sensor and sampling data.
# It dynamically selects and filters data from multiple monitoring systems (loggers, weather, quality, and creek sampling),
# builds a summary, and generates a structured analysis using an LLM.

from flask import request, jsonify
import json

# Centralized configuration for all sensor types
SENSOR_CONFIG = {
    'logger': {
        'sites': {
            "2577531": "Logger 1", "2577532": "Logger 2", "2577533": "Logger 3",
            "2577534": "Logger 4", "2577535": "Logger 5",
        },
        'metrics': ["Water Surface Elevation", "Water Temperature"],
        'all_label': "All Loggers"
    },
    'weather': {
        'metrics': [
            "Air Temperature", "Pressure", "Dew Point", 
            "Relative Humidity", "Solar Radiation", "Soil Temperature", "Wind Direction", 
            "Wind Speed", "Rainfall"
        ],
        'all_label': "All Weather"
    },
    'quality': {
        'metrics': [
            "Water Temperature", "pH", "Specific Conductivity", "Conductivity", 
            "Total Dissolved Solids (TDS)", "Dissolved Oxygen (ODO)", 
            "Dissolved Oxygen Saturation (ODOSat)", "Turbidity", "Total Suspended Solids (TSS)"
        ],
        'all_label': "All Quality"
    }
}

CREEK_ID_MAP = {
    "ancaster": "19431905",
    "tiffany": "20962187",
    "sulphur": "3212839",
    "coldwater": "336415129",
    "spencer": "19755185"
}

SENSORS_PROMPT_TEMPLATE = """
        You are an expert environmental data analyst conducting a comprehensive analysis across all monitoring systems. Analyze the provided multi-group sensor data covering Water Quality, Weather Station, and Water Logger systems and identify:
        
        CRITICAL ALERTS (1-3 bullet points)
        Immediate safety or environmental concerns requiring attention across any monitoring group

        LONG-TERM TRENDS (2-4 bullet points)
        Key patterns over time within and across monitoring groups (seasonal changes, gradual shifts, cyclical patterns)
        
        CROSS-GROUP CORRELATIONS (2-4 bullet points)
        Relationships between parameters from different monitoring systems (weather impacts on water quality, precipitation effects on water levels, temperature correlations across air/water, etc.)
        
        SYSTEM-SPECIFIC PATTERNS (2-3 bullet points)
        Notable trends within individual monitoring groups (water quality evolution, weather patterns, logger performance)
        
        ANOMALIES AND OUTLIERS (1-3 bullet points)
        Unusual readings, sudden changes, or data quality issues that deviate from normal patterns across all systems
        
        ENVIRONMENTAL INSIGHTS (2-3 bullet points)
        Broader ecological implications and system interactions based on multi-parameter analysis
        
        SUMMARY (2-3 sentences)
        Overall environmental health assessment, data quality evaluation, and key actionable recommendations
        Format as bullet points. Keep total response under 500 words. Focus on actionable insights that leverage the comprehensive nature of multi-group environmental monitoring data.

"""

SAMPLING_PROMPT_TEMPLATE = """
        You are an expert watershed environmental analyst conducting a comprehensive analysis of creek point sampling data across the Hamilton watershed area. Analyze the provided multi-creek sampling data covering bacterial indicators, nutrients, physical parameters, and chemical composition across multiple creek systems and identify:

        CRITICAL ALERTS (1-3 bullet points)
        Immediate water safety or ecological concerns requiring attention across any creek system (E. coli >400 CFU/100mL, extreme pH <6.5 or >8.5, severe turbidity spikes, nutrient pollution events)

        LONG-TERM TRENDS (2-4 bullet points)
        Key patterns over time within and across creek systems (seasonal nutrient cycles, bacterial contamination trends, gradual water quality deterioration or improvement, chronic pollution sources)

        CROSS-CREEK CORRELATIONS (2-4 bullet points)
        Relationships between parameters across different creek systems (upstream-downstream impacts, shared pollution sources, watershed-wide contamination events, similar seasonal patterns indicating regional influences)

        SITE-SPECIFIC PATTERNS (2-3 bullet points)
        Notable trends within individual sampling sites (localized contamination sources, site-specific improvements/degradation, unique chemical signatures, point source pollution indicators)

        ANOMALIES & OUTLIERS (1-3 bullet points)
        Unusual readings, sudden changes, or data quality issues that deviate from normal creek patterns (contamination spikes, unusual nutrient ratios, equipment malfunction indicators)

        WATERSHED INSIGHTS (2-3 bullet points)
        Broader ecological and public health implications based on multi-creek analysis (overall watershed health, pollution source identification, ecosystem impact assessment, recreational water safety)

        SUMMARY (2-3 sentences)
        Overall Hamilton watershed health assessment, priority contamination concerns, and key actionable recommendations for water management and public safety

        **Parameter Context:**
        - Bacterial Indicators: E. coli and Total coliform for fecal contamination assessment
        - Nutrients: Total/soluble phosphorus, total/nitrate/ammonia nitrogen for eutrophication risk
        - Physical Parameters: Turbidity for sediment load and water clarity
        - Chemical Composition: pH for acidity/alkalinity, conductivity and chloride for salinity/road salt impacts

        Format as bullet points. Keep total response under 500 words. Focus on actionable insights that leverage comprehensive watershed monitoring for public health protection and ecosystem management.

"""

def register_analysis_complete_route(app, latest_summaries, latest_sampling_summaries, client):
    @app.route("/api/analysis/complete", methods=["GET"])
    def analyze_complete_data():
        # Get active groups and dashboard tab from query parameters
        active_groups = request.args.getlist("type")
        dashboard_tab = request.args.get("dashboardTab", "sensors")
        
        final_summary = {}

        # --- DYNAMIC DATA SOURCE AND PROCESSING ---
        if dashboard_tab == "sampling":
            data_source = latest_sampling_summaries.get("data", {})
            # Process sampling data (creeks)
            for group in active_groups: # e.g., 'ancaster'
                creek_id = CREEK_ID_MAP.get(group)
                if creek_id and creek_id in data_source:
                    # For simplicity, we'll add the full data for the selected creek
                    # The AI is capable of parsing this nested structure
                    final_summary[group.title()] = data_source[creek_id]

        else: # Default to 'sensors'
            data_source = latest_summaries.get("data", {})
            # Process sensor data (existing logic)
            for group in active_groups:
                config = SENSOR_CONFIG.get(group)
                summary_data = data_source.get(group, {})
                if not config or not summary_data:
                    continue

                frontend_group_key = 'gauges' if group == 'logger' else group
                subtypes = request.args.getlist(f"{frontend_group_key}_subtypes")

                if group == 'logger':
                    all_ids = list(config['sites'].keys())
                    selected_stations = [s for s in subtypes if s in all_ids]
                    if config['all_label'] in subtypes or not selected_stations:
                        selected_stations = all_ids
                    
                    all_metrics = config['metrics']
                    selected_metrics = [s for s in subtypes if s in all_metrics]
                    if not selected_metrics:
                        selected_metrics = all_metrics

                    station_data = {sid: data for sid, data in summary_data.items() if sid in selected_stations}
                    filtered_data = {}
                    for sid, data in station_data.items():
                        metric_data = {m_name: m_data for m_name, m_data in data.items() if m_name in selected_metrics}
                        if metric_data:
                            filtered_data[sid] = metric_data
                    
                    if filtered_data:
                        final_summary['Water Loggers'] = filtered_data

                else: # Weather and Quality
                    all_metrics = config['metrics']
                    selected_metrics = [s for s in subtypes if s in all_metrics]
                    if config['all_label'] in subtypes or not selected_metrics:
                        selected_metrics = all_metrics
                    
                    filtered_data = {k: v for k, v in summary_data.items() if k in selected_metrics}
                    if filtered_data:
                        final_summary[group.title()] = filtered_data

        # If no data after filtering, return a message
        if not final_summary:
            return jsonify({"analysis": "No data available for the selected filters. Please select at least one group or metric."})

        # Prepare data for prompt (truncate if too long)
        raw_data = json.dumps(final_summary, default=str, indent=2)
        if len(raw_data) > 8000:
            raw_data = raw_data[:8000]

        # --- DYNAMIC PROMPT SELECTION (remains the same) ---
        prompt_template_content = ""
        if dashboard_tab == "sampling":
            prompt_template_content = SAMPLING_PROMPT_TEMPLATE
        else:
            prompt_template_content = SENSORS_PROMPT_TEMPLATE
        
        # Build prompt for LLM analysis
        prompt = f"""
        {prompt_template_content}
        
        **STRICT FORMATTING REQUIREMENTS:**
            - Use exactly this structure: **SECTION NAME:** followed by content
            - For bullet points, use format: - **Subsection name:** description
            - Always use double asterisks (**) for all headings and subheadings
            - Use single line breaks (\\n) between bullet points
            - Use double line breaks (\\n\\n) between major sections
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
            max_tokens=3000,
            temperature=0.4
        )

        return jsonify({"analysis": response.choices[0].message.content})