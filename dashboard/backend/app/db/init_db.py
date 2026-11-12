# This script creates the WELL backend's tables that don't exist yet, with SQLAlchemy's create_all() (CI and a new
# database use it). It never changes a table that already exists: changes go in db/migrations/ (scripts/migrate.py).

import sys
import pathlib

# Add backend/app/ to sys.path so server and db can be imported
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from server import create_app
from db.database import db
from db.models import SensorMeasurement, SamplingMeasurement, ExportJob  # noqa: F401 (registers the tables for create_all)

app = create_app()

with app.app_context():
    db.create_all()
    print("[✔] Tables created successfully.")
