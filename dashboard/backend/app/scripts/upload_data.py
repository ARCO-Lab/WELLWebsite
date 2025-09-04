# This script exports WELL sensor data for a given month to CSV and uploads it to Borealis Dataverse.
# It replicates frontend CSV formatting and supports both manual and automatic (last month) export.

import os
import sys
import pathlib
import json
import io
import argparse
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd
import csv
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from db.database import db
from db.models import SensorMeasurement
from server import create_app

load_dotenv()
#temporarily demo
BOREALIS_URL = os.getenv("DEMO_BOREALIS_URL")
BOREALIS_API_TOKEN = os.getenv("BOREALIS_API_TOKEN")
BOREALIS_WC_PERSISTENT_ID = os.getenv("DEMO_BOREALIS_WC_PERSISTENT_ID")
SHAREPOINT_URL = os.getenv("SHAREPOINT_URL")
SHAREPOINT_USER = os.getenv("SHAREPOINT_USER")
SHAREPOINT_PASS = os.getenv("SHAREPOINT_PASS")

# Frontend config replica
SENSOR_FILTER_CONFIG = {
    "gauges": {
        "sites": {
            "2577531": "Logger 1",
            "2577532": "Logger 2", 
            "2577533": "Logger 3",
            "2577534": "Logger 4",
            "2577535": "Logger 5",
        }
    }
}

SENSOR_STATION_COORDINATES = [
    {"id": "2577531", "lat": 43.267100, "lng": -79.928830, "label": "Water Logger 1", "group": "gauges"},
    {"id": "2577532", "lat": 43.266390, "lng": -79.929400, "label": "Water Logger 2", "group": "gauges"},
    {"id": "2577533", "lat": 43.264720, "lng": -79.928440, "label": "Water Logger 3", "group": "gauges"},
    {"id": "2577534", "lat": 43.264140, "lng": -79.928310, "label": "Water Logger 4", "group": "gauges"},
    {"id": "2577535", "lat": 43.263850, "lng": -79.929850, "label": "Water Logger 5", "group": "gauges"},
    {"id": "Water Quality Station", "lat": 43.264700, "lng": -79.928400, "label": "Water Quality Sensor", "group": "quality"},
    {"id": "Weather Station", "lat": 43.266110, "lng": -79.928660, "label": "Weather Station", "group": "weather"},
]

def get_station_coords(station_id):
    for s in SENSOR_STATION_COORDINATES:
        if str(s["id"]) == str(station_id):
            return s["lat"], s["lng"]
    return "", ""

def get_weather_station_coords():
    """Get coordinates for the weather station"""
    for s in SENSOR_STATION_COORDINATES:
        if s["group"] == "weather":
            return s["lat"], s["lng"]
    return "", ""

def get_quality_station_coords():
    """Get coordinates for the quality station"""
    for s in SENSOR_STATION_COORDINATES:
        if s["group"] == "quality":
            return s["lat"], s["lng"]
    return "", ""

def get_logger_label(station_id):
    """Replicate frontend getLoggerLabel function"""
    return SENSOR_FILTER_CONFIG["gauges"]["sites"].get(str(station_id), f"Logger {station_id}")

def get_last_month_range():
    now = datetime.now()
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this_month
    # Go to the first day of last month
    if first_of_this_month.month == 1:
        last_month_start = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
    else:
        last_month_start = first_of_this_month.replace(month=first_of_this_month.month - 1)
    return last_month_start, last_month_end

#for demo
def get_first_10_hours_of_last_month():
    now = datetime.now()
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Go to the first day of last month
    if first_of_this_month.month == 1:
        first_of_last_month = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
    else:
        first_of_last_month = first_of_this_month.replace(month=first_of_this_month.month - 1)
    start = first_of_last_month
    end = start + timedelta(hours=10)
    return start, end


def build_csv_frontend_style(data_list, file_obj):
    """
    Replicate EXACT frontend CSV building logic with coordinates for all groups
    """
    print(f"DEBUG: Starting CSV build with {len(data_list)} measurements")
    
    if not data_list:
        print("DEBUG: No data to export")
        return
    
    # Convert to DataFrame like frontend
    df = pd.DataFrame(data_list)
    print(f"DEBUG: DataFrame created with shape: {df.shape}")
    print("DEBUG: DataFrame columns:", df.columns.tolist())
    print("DEBUG: Group types in data:", df["group_type"].value_counts().to_dict())
    print("DEBUG: Station IDs in data:", sorted(df["station_id"].astype(str).unique()))
    
    # Simulate frontend activeGroups = {weather: true, quality: true, gauges: true}
    # and subFilters with all available metrics
    
    # 1. Filter data (simulate frontend filter logic)
    filtered = []
    for _, row in df.iterrows():
        include_row = False
        if row["group_type"] == "Weather":
            include_row = True
        elif row["group_type"] == "Quality":
            include_row = True
        elif row["group_type"] == "Logger":
            include_row = True
        
        if include_row:
            filtered.append(row.to_dict())
    
    print(f"DEBUG: After filtering: {len(filtered)} measurements")
    filtered_df = pd.DataFrame(filtered)
    
    # 2. Get unique timestamps (like frontend)
    timestamps = sorted(filtered_df["recorded_at"].unique())
    print(f"DEBUG: Found {len(timestamps)} unique timestamps")
    
    # 3. Identify metrics by group (like frontend)
    weather_keys = sorted(filtered_df[filtered_df["group_type"] == "Weather"]["measurement_type"].unique()) if not filtered_df[filtered_df["group_type"] == "Weather"].empty else []
    quality_keys = sorted(filtered_df[filtered_df["group_type"] == "Quality"]["measurement_type"].unique()) if not filtered_df[filtered_df["group_type"] == "Quality"].empty else []
    logger_keys = sorted(filtered_df[filtered_df["group_type"] == "Logger"]["measurement_type"].unique()) if not filtered_df[filtered_df["group_type"] == "Logger"].empty else []
    
    print(f"DEBUG: Weather metrics: {weather_keys}")
    print(f"DEBUG: Quality metrics: {quality_keys}")
    print(f"DEBUG: Logger metrics: {logger_keys}")
    
    # Get selected logger IDs (all available loggers)
    selected_logger_ids = sorted(filtered_df[filtered_df["group_type"] == "Logger"]["station_id"].astype(str).unique()) if not filtered_df[filtered_df["group_type"] == "Logger"].empty else []
    print(f"DEBUG: Selected logger IDs: {selected_logger_ids}")
    
    # 4. Build metric labels with units
    metric_label_map = {}
    for _, row in filtered_df.iterrows():
        key = row["measurement_type"]
        unit = row.get("unit", "")
        metric_label_map[key] = f"{key}: {unit}" if unit else key
    
    print("DEBUG: Metric labels:", metric_label_map)
    
    # 5. Build section keys (like frontend)
    section_keys = []
    if weather_keys:
        section_keys.append({"active": True, "label": "Weather", "keys": weather_keys})
    if quality_keys:
        section_keys.append({"active": True, "label": "Quality", "keys": quality_keys})
    if logger_keys:
        section_keys.append({"active": True, "label": "Logger", "keys": logger_keys})
    
    print(f"DEBUG: Section keys: {[s['label'] for s in section_keys]}")
    
    # 6. Build headers with coordinates for ALL groups
    headers = ["ID", "Timestamp"]
    
    active_sections = section_keys
    
    for section_idx, section in enumerate(active_sections):
        if section_idx != 0:
            headers.append("")  # Blank separator between sections
        
        headers.append("Group")  # Group header
        
        if section["label"] == "Weather":
            headers.append("Latitude") 
            headers.append("Longitude")
            for metric in section["keys"]:
                headers.append(metric_label_map.get(metric, metric))
                
        elif section["label"] == "Quality":
            headers.append("Latitude")
            headers.append("Longitude")
            for metric in section["keys"]:
                headers.append(metric_label_map.get(metric, metric))
                
        elif section["label"] == "Logger":
            headers.append("Sensor")
            headers.append("Latitude")
            headers.append("Longitude")

            for site_idx, site_id in enumerate(selected_logger_ids):
                for metric in section["keys"]:
                    headers.append(metric_label_map.get(metric, metric))
                if site_idx < len(selected_logger_ids) - 1:
                    headers.append("Sensor")
                    headers.append("Latitude")
                    headers.append("Longitude")
    
    print(f"DEBUG: Headers built: {len(headers)} columns")
    print("DEBUG: First 10 headers:", headers[:10])
    print("DEBUG: Last 10 headers:", headers[-10:])
    
    # 7. Build rows with coordinates for ALL groups
    rows = []
    for idx, timestamp in enumerate(timestamps, 1):
        print(f"DEBUG: Processing row {idx} for timestamp {timestamp}")
        
        # Create row data structure like frontend
        row_data = {"id": idx, "timestamp": timestamp}
        
        # Build row data for each section
        for section in active_sections:
            if section["label"] == "Logger":
                # For each selected logger, add its metrics
                for site_id in selected_logger_ids:
                    site_label = get_logger_label(site_id)
                    for metric in section["keys"]:
                        # Find matching data (like frontend match logic)
                        match = filtered_df[
                            (filtered_df["recorded_at"] == timestamp) &
                            (filtered_df["group_type"] == "Logger") &
                            (filtered_df["station_id"].astype(str) == str(site_id)) &
                            (filtered_df["measurement_type"] == metric)
                        ]
                        value = match["value"].iloc[0] if not match.empty else ""
                        key = f"{section['label']}_{site_label}_{metric}"
                        row_data[key] = value
                        if value != "":
                            print(f"DEBUG:   {key}: {value}")
            else:
                # Weather/Quality - single site (like frontend)
                site_label = "West Campus"
                for metric in section["keys"]:
                    match = filtered_df[
                        (filtered_df["recorded_at"] == timestamp) &
                        (filtered_df["group_type"] == section["label"]) &
                        (filtered_df["measurement_type"] == metric)
                    ]
                    value = match["value"].iloc[0] if not match.empty else ""
                    key = f"{section['label']}_{site_label}_{metric}"
                    row_data[key] = value
                    if value != "":
                        print(f"DEBUG:   {key}: {value}")
        
        # 8. Build CSV row with coordinates for ALL groups
        csv_row = [row_data["id"], row_data["timestamp"]]
        
        for section_idx, section in enumerate(active_sections):
            if section_idx != 0:
                csv_row.append("")  # Blank separator between sections
            
            csv_row.append(section["label"])  # Group name (Weather/Quality/Logger)
            
            if section["label"] == "Weather":
                # Add weather station coordinates (no sensor name)
                weather_lat, weather_lng = get_weather_station_coords()
                csv_row.append(weather_lat)
                csv_row.append(weather_lng)
                # Add metric values
                for metric in section["keys"]:
                    key = f"{section['label']}_West Campus_{metric}"
                    csv_row.append(row_data.get(key, ""))
                    
            elif section["label"] == "Quality":
                # Add quality station coordinates (no sensor name)
                quality_lat, quality_lng = get_quality_station_coords()
                csv_row.append(quality_lat)
                csv_row.append(quality_lng)
                # Add metric values
                for metric in section["keys"]:
                    key = f"{section['label']}_West Campus_{metric}"
                    csv_row.append(row_data.get(key, ""))
                    
            elif section["label"] == "Logger":
                # Add first logger name and coordinates
                if selected_logger_ids:
                    first_site_label = get_logger_label(selected_logger_ids[0])
                    csv_row.append(first_site_label)
                    lat, lng = get_station_coords(selected_logger_ids[0])
                    csv_row.append(lat)
                    csv_row.append(lng)

                for site_idx, site_id in enumerate(selected_logger_ids):
                    site_label = get_logger_label(site_id)
                    # Add metric values for this logger
                    for metric in section["keys"]:
                        key = f"{section['label']}_{site_label}_{metric}"
                        csv_row.append(row_data.get(key, ""))
                    # Add next logger name and coords (if there is one)
                    if site_idx < len(selected_logger_ids) - 1:
                        next_site_label = get_logger_label(selected_logger_ids[site_idx + 1])
                        csv_row.append(next_site_label)
                        lat, lng = get_station_coords(selected_logger_ids[site_idx + 1])
                        csv_row.append(lat)
                        csv_row.append(lng)
        
        rows.append(csv_row)
        print(f"DEBUG:   Row {idx} complete with {len(csv_row)} columns (expected {len(headers)})")
        
        if len(csv_row) != len(headers):
            print(f"DEBUG:   WARNING: Row length mismatch! Row: {len(csv_row)}, Headers: {len(headers)}")
    
    # Write to file-like object (in-memory or file)
    writer = csv.writer(file_obj)
    writer.writerow(headers)
    writer.writerows(rows)
    
    print(f"DEBUG: CSV written to file-like object")
    print(f"DEBUG: Written {len(rows)} data rows and {len(headers)} header columns")

def upload_to_borealis(csv_content, csv_name):
    """Upload CSV to Borealis Dataverse"""
    try:
        headers = {"X-Dataverse-key": BOREALIS_API_TOKEN}
        files = {'file': (csv_name, csv_content)}
        params = dict(description='Automated upload', categories=['Data'])
        payload = dict(jsonData=json.dumps(params))
        resp = requests.post(
            f"{BOREALIS_URL}/api/datasets/:persistentId/add?persistentId={BOREALIS_WC_PERSISTENT_ID}&key={BOREALIS_API_TOKEN}",
            data=payload,
            files=files
        )
        resp.raise_for_status()
        print(f"Successfully uploaded {csv_name} to Borealis")
    except Exception as e:
        print(f"Error uploading to Borealis: {e}")

def upload_to_sharepoint(csv_content, csv_name):
    """Upload CSV to SharePoint"""
    print(f"Would upload {csv_name} to SharePoint")
    # Implement actual upload logic as needed

def get_month_range(year: int, month: int):
    """Return the start and end datetime for a given month."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end
#python upload_data.py --year 2023 --month 7

def main():
    parser = argparse.ArgumentParser(description="Export WELL data for a specific month.")
    parser.add_argument("--year", type=int, help="Year (e.g. 2024)")
    parser.add_argument("--month", type=int, help="Month (1-12)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Use manual month/year if provided, else default to last month
        if args.year and args.month:
            start, end = get_month_range(args.year, args.month)
            print(f"DEBUG: Exporting data from {start} to {end} (manual selection)")
        else:
            start, end = get_last_month_range()
            print(f"DEBUG: Exporting data from {start} to {end} (last month by default)")
        
        # Use EXACT same query pattern as data.py that works
        group_types = ["Weather", "Quality", "Logger"]  # All groups active
        
        print(f"DEBUG: Querying for group_types: {group_types}")
        
        # EXACT same query as working data.py
        query = db.session.query(SensorMeasurement).filter(
            SensorMeasurement.group_type.in_(group_types),
            SensorMeasurement.recorded_at.between(start, end)
        )
        
        print(f"DEBUG: Query built, executing...")
        
        # Get data in EXACT same format as data.py
        raw_data = query.order_by(SensorMeasurement.recorded_at).all()
        print(f"DEBUG: Found {len(raw_data)} raw measurements from database")
        
        # Convert to EXACT same format as data.py
        data = [
            {
                "station_id": r.station_id,
                "group_type": r.group_type,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }            
            for r in raw_data
        ]
        
        print(f"DEBUG: Converted to data list with {len(data)} entries")
        
        # Debug: Show what we found
        if data:
            df_debug = pd.DataFrame(data)
            print("DEBUG: Station IDs found:", sorted(df_debug["station_id"].astype(str).unique()))
            print("DEBUG: Group types found:", sorted(df_debug["group_type"].unique()))
            print("DEBUG: Measurement types found:", sorted(df_debug["measurement_type"].unique()))
            
            # Show counts by group
            for group_type in df_debug["group_type"].unique():
                group_data = df_debug[df_debug["group_type"] == group_type]
                print(f"DEBUG: {group_type} - {len(group_data)} measurements")
                if group_type == "Logger":
                    station_counts = group_data["station_id"].value_counts()
                    print(f"DEBUG:   Logger stations: {dict(station_counts)}")
        
        if not data:
            print("DEBUG: No sensor data found for last month.")
            return
        
        # Build CSV in memory - CHANGED to use io.StringIO instead of file path
        csv_name = f"WELLWestCampus_{start.strftime('%b%Y')}.csv"
        csv_buffer = io.StringIO()
        
        print(f"DEBUG: Building CSV in memory: {csv_name}")
        
        # Use frontend-style CSV building with in-memory buffer
        build_csv_frontend_style(data, csv_buffer)
        
        # Get CSV content from buffer
        csv_buffer.seek(0)
        csv_content = csv_buffer.getvalue()
        
        # Upload to external services - CHANGED to use csv_content instead of csv_path
        print("DEBUG: Starting uploads...")
        # upload_to_sharepoint(csv_content, csv_name)
        upload_to_borealis(csv_content, csv_name)

        print("DEBUG: Export process completed!")

if __name__ == "__main__":
    main()