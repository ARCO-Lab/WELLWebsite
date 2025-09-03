"""
Use this script to CLEAR ALL sampling data from the database.
Recommended: Only use this when real sampling data starts to be uploaded.
"""

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SamplingMeasurement

app = create_app()

def clear_sampling_db():
    with app.app_context():
        print("[INFO] Clearing ALL SamplingMeasurement records from the database ...")
        SamplingMeasurement.query.delete()
        db.session.commit()
        print("[DONE] All sampling data has been cleared.")

if __name__ == "__main__":
    print("WARNING: This will DELETE ALL sampling data from the database!")
    confirm = input("Are you sure you want to clear the database? (Y/N): ").strip().lower()
    if confirm == "y":
        clear_sampling_db()
    else:
        print("Aborted. No data was deleted.")