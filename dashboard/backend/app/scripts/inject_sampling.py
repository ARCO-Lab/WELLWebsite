# This script loads creek/point sampling data from an Excel file into the database.
# Incremental mode (the default) adds every row that isn't stored yet; --full-reload replaces everything.

import os
import sys
import pathlib
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from server import create_app
from db.database import db
from db.models import SamplingMeasurement
from api.services.sampling import SamplingService
from utils.sampling_rows import KEY, entry_to_row, rows_from_entries

app = create_app()

# 🔹 Convert parsed JSON entry into SQLAlchemy model instance
def parse_sampling_entry(entry):
    try:
        return SamplingMeasurement(**entry_to_row(entry))
    except Exception as e:
        print(f"[ERROR] Failed to parse sampling entry: {e}")
        print(f"[ERROR] Entry data: {entry}")
        raise

# 🔹 Inject new sampling data: every row of the file that isn't stored yet
def inject_new_sampling_data(file_path, return_only=False):
    """
    Add every row of a sampling file that isn't in the database yet.

    Rows are matched on the table's unique key (site, measurement, sampling date), so re-importing a
    file adds nothing, and a file with older dates (a backfill, or a creek reported late) adds exactly
    the missing rows. (This used to keep only rows newer than the newest sampling row of any creek,
    which silently dropped those.)

    Args:
        file_path: Path to the Excel file on disk
        return_only: If True, return the parsed rows without inserting them
    """
    try:
        print(f"[INFO] Loading file: {file_path}")
        entries = SamplingService(file_path).get_sampling_data()
        print(f"[INFO] Found {len(entries)} total entries in file")

        rows, stats = rows_from_entries(entries)
        if return_only:
            return rows

        inserted = 0
        for i in range(0, len(rows), 1000):
            stmt = insert(SamplingMeasurement).values(rows[i:i + 1000]).on_conflict_do_nothing(index_elements=list(KEY))
            inserted += db.session.execute(stmt).rowcount
        db.session.commit()

        # download_data.py reads this exact line to decide whether a file counts as processed
        print(f"[INFO] Inserted {inserted} new sampling records.")
        print(f"[INFO] {len(rows) - inserted} were already stored; {stats['duplicates']} rows repeated "
              f"another row of the file; {stats['failed']} entries could not be parsed.")
        if stats["unknown_sites"]:
            print(f"[WARN] Site names matching no known site were stored as site 7 (Unknown): "
                  f"{sorted(stats['unknown_sites'])}")
        if stats["collisions"]:
            print(f"[WARN] {len(stats['collisions'])} rows were not imported because a different site name maps to "
                  f"the same site (add the names to SITE_ID_MAP in utils/sampling_rows.py), e.g.:")
            for kept, dropped, measurement, when in stats["collisions"][:5]:
                print(f"[WARN]   kept {kept!r}, dropped {dropped!r}: {measurement} on {when:%Y-%m-%d}")
        return rows

    except Exception as e:
        db.session.rollback()
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
    # Main entry point for sampling data injection
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