# This script loads creek/point sampling data from an Excel file into the database.
# Incremental mode (the default) adds every row that isn't stored yet; --full-reload replaces everything.

import os
import sys
import pathlib
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from server import create_app
from db.database import db
from db.models import SamplingMeasurement
from api.services.sampling import SamplingService
from utils.sampling_rows import KEY, check_skipped, entry_to_row, import_warnings, rows_from_entries

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

        # RETURNING tells which keys were new; the rest were already stored
        key_cols = [SamplingMeasurement.__table__.c[k] for k in KEY]
        inserted_keys = set()
        for i in range(0, len(rows), 1000):
            stmt = (insert(SamplingMeasurement).values(rows[i:i + 1000])
                    .on_conflict_do_nothing(index_elements=list(KEY)).returning(*key_cols))
            inserted_keys.update(tuple(r) for r in db.session.execute(stmt))
        db.session.commit()
        # download_data.py reads this exact line to decide whether a file counts as processed, so it is
        # printed as soon as the rows are committed, before the diagnostics below
        print(f"[INFO] Inserted {len(inserted_keys)} new sampling records.")
        print(f"[INFO] {len(rows) - len(inserted_keys)} were already stored; {stats['duplicates']} rows repeated "
              f"another row of the file; {stats['failed']} entries could not be parsed.")

        def fetch_stored(keys):
            """Stored values of these keys, to spot corrected readings and clashes on site 7."""
            stored_values = {}
            try:
                for i in range(0, len(keys), 1000):
                    query = (select(*key_cols, SamplingMeasurement.value)
                             .where(tuple_(*key_cols).in_(keys[i:i + 1000])))
                    stored_values.update({tuple(r[:3]): r[3] for r in db.session.execute(query)})
            except Exception:
                db.session.rollback()  # leave the session usable; check_skipped() reports the error
                raise
            return stored_values

        changed, unknown_skipped = check_skipped(rows, inserted_keys, fetch_stored)
        for line in import_warnings(stats, changed, unknown_skipped):
            print(line)
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
    from utils.guards import require_wipe_permission  # local: keeps this change apart from the import block
    require_wipe_permission("all sampling data (--full-reload)")
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