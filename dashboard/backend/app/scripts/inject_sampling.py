import os
import sys
import pathlib
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import pandas as pd

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from server import create_app
from db.database import db
from db.models import SamplingMeasurement
from api.services.sampling import SamplingService

app = create_app()

# 🔹 Static creek keyword-to-ID map
CREEK_ID_MAP = {
    "ancaster": "19431905",
    "tiffany": "20962187",
    "sulphur": "3212839",
    "coldwater": "336415129",
    "spencer": "19755185"
}

# 🔹 Site-to-ID Mapping (based on keyword in site name)
SITE_ID_MAP = {
    "Falkirk": 1,
    "Maple": 2,
    "Jerseyville": 3,
    "Sulphur": 4,
    "Sherman": 5,
    "Tiffany": 6,
    "Unknown": 7,  # Placeholder for unlisted sites
    "Osler": 8,
    "McMaster": 9,
    "Cootes": 10
}

# 🔹 Resolve creek ID using keyword match
def resolve_creek_id(creek_name):
    creek_name_lower = creek_name.lower()
    for keyword, creek_id in CREEK_ID_MAP.items():
        if keyword in creek_name_lower:
            return creek_id
    return "00000000"  # Default if unknown

# 🔹 Resolve site ID based on keyword in site name
def resolve_site_id(site_name):
    for keyword, sid in SITE_ID_MAP.items():
        if keyword in site_name:
            return sid
    return SITE_ID_MAP["Unknown"]

# 🔹 Enhanced date parsing function
def parse_date_flexible(date_string):
    """
    Parse date string with flexible format handling.
    Supports:
    - "2026-03-15" (date only, defaults to 00:00:00)
    - "2026-03-15 14:30:00" (date with time)
    - ISO format strings
    """
    try:
        # First try parsing as ISO format (from recorded_at field)
        if 'T' in str(date_string):
            return datetime.fromisoformat(str(date_string).replace('T', ' ').replace('Z', ''))
        
        # Handle date-only format (default to midnight)
        date_str = str(date_string).strip()
        
        # Try various date formats
        date_formats = [
            "%Y-%m-%d %H:%M:%S",  # Full datetime
            "%Y-%m-%d %H:%M",     # Date with hour:minute
            "%Y-%m-%d",           # Date only
            "%m/%d/%Y",           # US format
            "%d/%m/%Y",           # EU format
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Fallback: use pandas to_datetime which is very flexible
        parsed_date = pd.to_datetime(date_str)
        if pd.isna(parsed_date):
            raise ValueError(f"Could not parse date: {date_string}")
        
        # Convert to datetime and remove timezone if present
        if hasattr(parsed_date, 'tz_localize'):
            parsed_date = parsed_date.tz_localize(None)
        
        return parsed_date.to_pydatetime()
        
    except Exception as e:
        print(f"[ERROR] Failed to parse date '{date_string}': {e}")
        raise ValueError(f"Invalid date format: {date_string}")

# 🔹 Convert parsed JSON entry into SQLAlchemy model instance
def parse_sampling_entry(entry):
    try:
        # Parse the date with flexible handling
        recorded_at = parse_date_flexible(entry["recorded_at"])
        
        return SamplingMeasurement(
            site_id=resolve_site_id(entry["site_id"]),
            creek_id=resolve_creek_id(entry["creek_id"]),
            measurement_type=entry["measurement_type"],
            value=entry["value"],
            unit=entry["unit"],
            recorded_at=recorded_at
        )
    except Exception as e:
        print(f"[ERROR] Failed to parse sampling entry: {e}")
        print(f"[ERROR] Entry data: {entry}")
        raise

# 🔹 Inject new sampling data (only records newer than latest in DB)
def inject_new_sampling_data(file_path, return_only=False):
    """
    Inject new sampling data using incremental logic similar to inject_from_api.py
    
    Args:
        file_path: Path to the Excel file on disk
        return_only: If True, return parsed objects without inserting to DB
    """
    try:
        # Load file content
        print(f"[INFO] Loading file: {file_path}")
        # Get sampling data from file
        sampling_service = SamplingService(file_path)
        entries = sampling_service.get_sampling_data()
        print(f"[INFO] Found {len(entries)} total entries in file")

        # Get the most recent timestamp for sampling data
        latest = db.session.query(SamplingMeasurement.recorded_at).order_by(
            SamplingMeasurement.recorded_at.desc()
        ).first()

        latest_timestamp = latest[0] if latest else None
        print(f"[INFO] Latest sampling record in DB: {latest_timestamp}")

        # Parse all entries
        all_records = []
        for entry in entries:
            try:
                obj = parse_sampling_entry(entry)
                all_records.append(obj)
            except Exception as e:
                print(f"[ERROR] Failed to parse sampling entry: {e}")
                print(f"[ERROR] Problematic entry: {entry}")

        # Filter for new records only (records newer than latest in DB)
        new_records = []
        if latest_timestamp:
            for obj in all_records:
                if obj.recorded_at > latest_timestamp:
                    new_records.append(obj)
        else:
            # If no existing records, all are new
            new_records = all_records

        print(f"[INFO] Found {len(new_records)} new sampling records to insert")

        if return_only:
            return new_records

        # Insert new records
        inserted = 0
        for obj in sorted(new_records, key=lambda x: x.recorded_at):
            try:
                db.session.add(obj)
                db.session.commit()
                inserted += 1
                print(f"[NEW] Inserted: {obj.measurement_type} from site {obj.site_id} at {obj.recorded_at} with value {obj.value} {obj.unit}")
            except IntegrityError:
                db.session.rollback()
                print(f"[SKIPPED - DUPLICATE] {obj.measurement_type} {obj.site_id} {obj.recorded_at}")
            except Exception as e:
                print(f"[ERROR] Failed to insert sampling record: {e}")
                db.session.rollback()

        print(f"[INFO] Inserted {inserted} new sampling records.")
        return new_records

    except Exception as e:
        print(f"[ERROR] Failed to process sampling data: {e}")
        raise

# 🔹 Load and inject all sampling data from the provided file (original full load function)
def inject_all_sampling_history(file_path):
    """
    Original function - loads all data and replaces existing records
    Keep this for initial setup or full refresh scenarios
    """
    try:
        print(f"[INFO] Loading file: {file_path}")
        sampling_service = SamplingService(file_path)
        entries = sampling_service.get_sampling_data()
        all_records = []

        for entry in entries:
            try:
                obj = parse_sampling_entry(entry)
                all_records.append(obj)
            except Exception as e:
                print(f"[ERROR] Failed to parse sampling entry: {e}")

        with app.app_context():
            print("[INFO] Clearing existing SamplingMeasurement records ...")
            SamplingMeasurement.query.delete()
            db.session.commit()

            print(f"[INFO] Inserting {len(all_records)} sampling records...")
            inserted = 0
            for obj in all_records:
                try:
                    db.session.add(obj)
                    db.session.commit()
                    inserted += 1
                except IntegrityError:
                    db.session.rollback()
                except Exception as e:
                    print(f"[ERROR] Failed to insert sampling record: {e}")
                    db.session.rollback()

            print(f"[DONE] Inserted {inserted} total sampling records.")
    except Exception as e:
        print(f"[ERROR] Failed to process file {file_path}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python inject_sampling.py <file_path> [--full-reload]")
        print("  --full-reload: Replace all existing data (default: incremental)")
        sys.exit(1)
    
    file_path = sys.argv[1]
    full_reload = "--full-reload" in sys.argv

    with app.app_context():
        if full_reload:
            print("[INFO] Full reload mode - replacing all existing data...")
            inject_all_sampling_history(file_path)
        else:
            print("[INFO] Incremental mode - adding only new records...")
            inject_new_sampling_data(file_path)
    
    print("[DONE] Sampling data injection complete.")