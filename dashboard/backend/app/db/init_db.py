# backend/app/database/init_db.py
import sys
import pathlib

# Add backend/app/ to sys.path so we can import main and db
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from server import create_app
from db.database import db
from db.models import SensorMeasurement, SamplingMeasurement

app = create_app()

with app.app_context():
    db.create_all()
    print("[✔] Tables created successfully.")
