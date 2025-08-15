import os, sys, pathlib
from datetime import datetime
from sqlalchemy.exc import IntegrityError

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

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

# 🔹 Convert parsed JSON entry into SQLAlchemy model instance
def parse_sampling_entry(entry):
    return SamplingMeasurement(
        site_id=resolve_site_id(entry["site_id"]),
        creek_id=resolve_creek_id(entry["creek_id"]),
        measurement_type=entry["measurement_type"],
        value=entry["value"],
        unit=entry["unit"],
        recorded_at=datetime.fromisoformat(entry["recorded_at"])
    )

# 🔹 Load and inject all sampling data from Excel or future API
def inject_all_sampling_history():
    sampling_service = SamplingService()
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

if __name__ == "__main__":
    inject_all_sampling_history()
    print("[DONE] Sampling data injection complete.")
