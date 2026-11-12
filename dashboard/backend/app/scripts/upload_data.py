# This script exports one month of WELL sensor data to CSV and uploads it to Borealis Dataverse, as the off-VM
# copy that anyone can cite. The CSV has the dashboard's export layout (one row per timestamp: Weather, Quality and
# one block per logger). The scheduler runs it for each month that has ended (scripts/scheduler_temp.py);
# scripts/sharepoint_upload.py sends the same file to SharePoint.
#   python scripts/upload_data.py --year 2026 --month 10             that month
#   python scripts/upload_data.py                                    last month
#   python scripts/upload_data.py --year 2026 --month 10 --dry-run   build the CSV and print its size only
# Every month goes into the one dataset BOREALIS_UPLOAD_PERSISTENT_ID as WELLWestCampus_<Mon><YYYY>.csv, in a folder
# per year, and the dataset is then published as a new major version (utils/borealis.py has the details). Running it
# again for a month is safe: an identical file isn't sent twice, and a changed one replaces the old copy.
# It prints "Successfully uploaded <file> to Borealis" only once the file is in the dataset and published (or left
# as a draft on purpose, BOREALIS_PUBLISH=0); the scheduler records the month as done only then.

import sys
import pathlib
import io
import argparse
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from config import Config
import pandas as pd
import csv
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from utils.borealis import Dataverse, DataverseError, base_url, is_demo, upload_file
from utils.timezone import site_to_utc, site_wall_time

load_dotenv()


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
    # Months are site (Toronto) calendar months, so "last month" is measured on that clock, not on the
    # container's UTC clock, which turns to the next month at 19:00 or 20:00 Toronto time on the last day.
    now = datetime.now(ZoneInfo("America/Toronto")).replace(tzinfo=None)
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this_month
    # Go to the first day of last month
    if first_of_this_month.month == 1:
        last_month_start = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
    else:
        last_month_start = first_of_this_month.replace(month=first_of_this_month.month - 1)
    return last_month_start, last_month_end


def build_csv_frontend_style(data_list, file_obj):
    """Write the dashboard's CSV layout for `data_list` (dicts with station_id, group_type, measurement_type, value,
    unit and recorded_at as an ISO string) to `file_obj`.

    recorded_at is the instant (UTC, from the database), or naive site time; Timestamp shows site wall time.
    The layout: ID, Timestamp, then a Weather block (Group, Latitude, Longitude, one column per metric), a Quality
    block like it, and a Logger block (Group, then for each logger Sensor, Latitude, Longitude and its metrics),
    with an empty column between blocks. A cell is the first reading for its timestamp, group (and logger) and
    metric, or empty. Values are looked up in one dictionary, so a month (about 4,500 timestamps) takes seconds;
    it used to filter the whole month once per cell, and print every cell, which took most of an hour.
    """
    if not data_list:
        print("No data to export")
        return

    df = pd.DataFrame(data_list)
    df = df[df["group_type"].isin(["Weather", "Quality", "Logger"])]
    print(f"Building the CSV from {len(df)} readings: {df['group_type'].value_counts().to_dict()}")

    timestamps = sorted(df["recorded_at"].unique())

    def metrics(group):
        return sorted(df[df["group_type"] == group]["measurement_type"].unique())

    weather_keys, quality_keys, logger_keys = metrics("Weather"), metrics("Quality"), metrics("Logger")
    selected_logger_ids = sorted(df[df["group_type"] == "Logger"]["station_id"].astype(str).unique())

    # Column label per metric, with the unit of its last reading
    metric_label_map = {}
    for key, unit in zip(df["measurement_type"], df["unit"]):
        metric_label_map[key] = f"{key}: {unit}" if unit else key

    # The first value for each (timestamp, group, metric) and, for loggers, each (timestamp, group, logger, metric)
    first_value = {}
    for ts, group, station, metric, value in zip(df["recorded_at"], df["group_type"], df["station_id"].astype(str),
                                                 df["measurement_type"], df["value"].tolist()):
        if group == "Logger":
            first_value.setdefault((ts, group, station, metric), value)
        else:
            first_value.setdefault((ts, group, metric), value)

    sections = [(label, keys) for label, keys in
                (("Weather", weather_keys), ("Quality", quality_keys), ("Logger", logger_keys)) if keys]

    headers = ["ID", "Timestamp"]
    for section_idx, (label, keys) in enumerate(sections):
        if section_idx != 0:
            headers.append("")  # blank separator between sections
        headers.append("Group")
        if label in ("Weather", "Quality"):
            headers += ["Latitude", "Longitude"]
            headers += [metric_label_map.get(m, m) for m in keys]
        else:
            for _ in selected_logger_ids:
                headers += ["Sensor", "Latitude", "Longitude"]
                headers += [metric_label_map.get(m, m) for m in keys]

    station_coords = {"Weather": get_weather_station_coords(), "Quality": get_quality_station_coords()}
    rows = []
    for idx, timestamp in enumerate(timestamps, 1):
        # Rows are keyed by the instant (UTC ISO), so both copies of the repeated fall-back hour stay; the file shows
        # site wall time, as it always has.
        csv_row = [idx, site_wall_time(datetime.fromisoformat(timestamp)).isoformat()]
        for section_idx, (label, keys) in enumerate(sections):
            if section_idx != 0:
                csv_row.append("")
            csv_row.append(label)
            if label in ("Weather", "Quality"):
                csv_row += list(station_coords[label])
                csv_row += [first_value.get((timestamp, label, m), "") for m in keys]
            else:
                for site_id in selected_logger_ids:
                    lat, lng = get_station_coords(site_id)
                    csv_row += [get_logger_label(site_id), lat, lng]
                    csv_row += [first_value.get((timestamp, label, site_id, m), "") for m in keys]
        rows.append(csv_row)

    writer = csv.writer(file_obj)
    writer.writerow(headers)
    writer.writerows(rows)
    print(f"Built the CSV: {len(rows)} rows, {len(headers)} columns")


def borealis_settings():
    """(server URL, token, dataset id) for the upload. Exits 1 saying what is missing or wrong."""
    url, token, pid = Config.BOREALIS_URL, Config.BOREALIS_API_TOKEN, Config.BOREALIS_UPLOAD_PERSISTENT_ID
    missing = [name for name, value in (("BOREALIS_URL", url), ("BOREALIS_API_TOKEN", token),
                                        ("BOREALIS_UPLOAD_PERSISTENT_ID", pid)) if not value]
    if missing:
        print(f"ERROR: Not uploading to Borealis: {', '.join(missing)} not set (see utils/borealis.py)")
        sys.exit(1)
    try:
        server = base_url(url)
    except ValueError as e:
        print(f"ERROR: Not uploading to Borealis: {e}")
        sys.exit(1)
    if is_demo(server) != is_demo(persistent_id=pid):
        print(f"ERROR: Not uploading to Borealis: BOREALIS_URL is {server} but the dataset {pid} is on the "
              f"{'production' if is_demo(server) else 'demo'} server. Set BOREALIS_UPLOAD_PERSISTENT_ID to the "
              f"dataset's id on {server}.")
        sys.exit(1)
    if is_demo(server):
        print(f"WARNING: uploading to the demo server {server}: it is for testing and is reset from time to time, "
              f"so this is not a backup")
    return server, token, pid


def upload_to_borealis(csv_content, csv_name, year, client=None):
    """Upload the CSV to the Borealis dataset and publish it (utils/borealis.upload_file). Exits 1 on failure."""
    server, token, pid = borealis_settings()
    client = client or Dataverse(server, token)
    month = csv_name[len("WELLWestCampus_"):-len(".csv")]
    try:
        outcome, version = upload_file(client, pid, csv_name, csv_content,
                                       description=f"WELL West Campus sensor data, {month} (automated monthly export)",
                                       directory=str(year), publish=Config.BOREALIS_PUBLISH)
    except DataverseError as e:
        print(f"ERROR: Uploading {csv_name} to Borealis: {e}")
        sys.exit(1)
    state = f"published as version {version}" if version else "no new version published by this run"
    print(f"Successfully uploaded {csv_name} to Borealis ({outcome}, {state})")


def export_month_csv(start, end):
    """(file name, CSV text) for the readings from `start` up to, not including, `end`, or None if there are none.
    Needs the app context (the database)."""
    from db.database import db
    from db.models import SensorMeasurement

    query = db.session.query(SensorMeasurement).filter(
        SensorMeasurement.group_type.in_(["Weather", "Quality", "Logger"]),
        # The local calendar month as instants. Half-open, so the reading at midnight on the 1st goes in the new
        # month's file only.
        SensorMeasurement.recorded_at >= site_to_utc(start),
        SensorMeasurement.recorded_at < site_to_utc(end),
    ).order_by(SensorMeasurement.recorded_at)
    data = [
        {
            "station_id": r.station_id,
            "group_type": r.group_type,
            "measurement_type": r.measurement_type,
            "value": r.value,
            "unit": r.unit,
            "recorded_at": r.recorded_at.isoformat(),   # the UTC instant; shown as site time in the file
        }
        for r in query
    ]
    print(f"Found {len(data)} readings from {start} up to {end}")
    if not data:
        return None
    csv_buffer = io.StringIO()
    build_csv_frontend_style(data, csv_buffer)
    return month_file_name(start), csv_buffer.getvalue()


def month_file_name(start):
    """WELLWestCampus_Oct2026.csv for October 2026 (English month names, whatever the locale)."""
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"WELLWestCampus_{months[start.month - 1]}{start.year}.csv"


def get_month_range(year: int, month: int):
    """The start of the month and the start of the next one (readings from start up to, not including, end)."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def parse_args(argv=None, description="Export one month of WELL sensor data and upload it to Borealis."):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--year", type=int, help="Year (e.g. 2026)")
    parser.add_argument("--month", type=int, help="Month (1-12)")
    parser.add_argument("--dry-run", action="store_true", help="Build the CSV and print its size; upload nothing")
    args = parser.parse_args(argv)
    if bool(args.year) != bool(args.month):
        parser.error("give both --year and --month, or neither (last month)")
    return args


def exported_month(args):
    """(file name, CSV text, year) for the month the arguments name. Exits 2 when it has no data. Needs the app."""
    if args.year and args.month:
        start, end = get_month_range(args.year, args.month)
    else:
        start, end = get_last_month_range()
    print(f"Exporting sensor data from {start} up to {end}")
    exported = export_month_csv(start, end)
    if exported is None:
        # Exit non-zero: nothing was sent, so the scheduler must not record this month as uploaded
        # (it tries again the next day, e.g. once a backfill has filled the month in).
        print(f"ERROR: No sensor data found from {start} to {end}; nothing uploaded.")
        sys.exit(2)
    csv_name, csv_content = exported
    print(f"{csv_name}: {len(csv_content.encode('utf-8')):,} bytes")
    return csv_name, csv_content, start.year


def main():
    args = parse_args()
    from server import create_app
    with create_app().app_context():
        csv_name, csv_content, year = exported_month(args)
    if args.dry_run:
        print("Dry run: not uploading")
        return
    upload_to_borealis(csv_content, csv_name, year)


if __name__ == "__main__":
    main()
