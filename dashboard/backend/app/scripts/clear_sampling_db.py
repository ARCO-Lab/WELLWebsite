"""
Use this script to CLEAR ALL sampling data (the sampling_measurements table) from the database.
It asks for confirmation, and refuses unless ALLOW_WIPE=1 is set for the run (utils/guards.py). Take a backup first.
"""

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from server import create_app
from db.database import db
from db.models import SamplingMeasurement
from utils.guards import require_wipe_permission

app = create_app()

def clear_sampling_db():
    require_wipe_permission("all sampling data")
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