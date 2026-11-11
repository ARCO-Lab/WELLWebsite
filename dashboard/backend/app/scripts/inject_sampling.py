# Loads a creek sampling file into the database: a standard sampling CSV (docs/sampling-csv-format.md) or an Excel
# sheet in the older one-row-per-visit layout.
#   python scripts/inject_sampling.py <file>                 add every reading that isn't stored yet
#   python scripts/inject_sampling.py <file> --full-reload   replace all sampling data (needs ALLOW_WIPE=1)
# The file is checked first (utils/sampling_csv.py) and nothing is stored unless all of it is valid; the problems
# are listed with their row numbers and the exit code is 1. To only check a file: scripts/check_sampling_csv.py.

import sys
import pathlib
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from server import create_app
from db.database import db
from db.models import SamplingMeasurement
from utils.sampling_csv import validate_file
from utils.sampling_rows import KEY, check_skipped, import_warnings

app = create_app()


class InvalidFile(Exception):
    """The file has problems; nothing was stored."""


def load_valid_rows(file_path):
    """The file's rows, or InvalidFile after printing every problem."""
    print(f"[INFO] Loading file: {file_path}")
    result = validate_file(file_path)
    for note in result.notes:
        print(f"[INFO] {note}")
    if not result.ok:
        for issue in result.errors:
            print(f"[ERROR] {issue}")
        raise InvalidFile(f"{len(result.errors)} problems in {file_path}; nothing was imported. Fix them and "
                          f"upload the file again.")
    print(f"[INFO] Valid file: {result.summary()}")
    return result.records


def store_rows(session, rows):
    """Insert the rows whose key isn't stored yet; returns the keys inserted. The caller commits."""
    key_cols = [SamplingMeasurement.__table__.c[k] for k in KEY]
    inserted_keys = set()
    for i in range(0, len(rows), 1000):
        # RETURNING tells which keys were new; the rest were already stored
        stmt = (insert(SamplingMeasurement).values(rows[i:i + 1000])
                .on_conflict_do_nothing(index_elements=list(KEY)).returning(*key_cols))
        inserted_keys.update(tuple(r) for r in session.execute(stmt))
    return inserted_keys


def inject_new_sampling_data(file_path, return_only=False):
    """
    Add every reading of a sampling file that isn't in the database yet.

    Rows are matched on the table's unique key (site, measurement, sampling date and time), so re-importing a file
    adds nothing, and a file with older dates (a backfill, or a creek reported late) adds exactly the missing rows.

    Args:
        file_path: Path to the file on disk
        return_only: If True, return the parsed rows without inserting them
    """
    rows = load_valid_rows(file_path)
    if return_only:
        return rows
    try:
        inserted_keys = store_rows(db.session, rows)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    # download_data.py reads this exact line to decide whether a file counts as processed, so it is printed as soon
    # as the rows are committed, before the diagnostics below
    print(f"[INFO] Inserted {len(inserted_keys)} new sampling records.")
    print(f"[INFO] {len(rows) - len(inserted_keys)} were already stored.")

    key_cols = [SamplingMeasurement.__table__.c[k] for k in KEY]

    def fetch_stored(keys):
        """Stored values of these keys, to spot corrected readings."""
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

    for line in import_warnings(check_skipped(rows, inserted_keys, fetch_stored)):
        print(line)
    return rows


def inject_all_sampling_history(file_path):
    """Replace every stored sampling row with the file's, in one transaction (for a full refresh only)."""
    from utils.guards import require_wipe_permission  # local: keeps this change apart from the import block
    require_wipe_permission("all sampling data (--full-reload)")
    rows = load_valid_rows(file_path)  # checked before anything is deleted
    try:
        print("[INFO] Clearing existing SamplingMeasurement records ...")
        SamplingMeasurement.query.delete()
        inserted = store_rows(db.session, rows)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    print(f"[DONE] Inserted {len(inserted)} total sampling records.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python inject_sampling.py <file_path> [--full-reload]")
        print("  --full-reload: Replace all existing data (default: incremental)")
        sys.exit(1)

    file_path = sys.argv[1]
    full_reload = "--full-reload" in sys.argv

    with app.app_context():
        try:
            if full_reload:
                print("[INFO] Full reload mode - replacing all existing data...")
                inject_all_sampling_history(file_path)
            else:
                print("[INFO] Incremental mode - adding only new records...")
                inject_new_sampling_data(file_path)
        except InvalidFile as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    print("[DONE] Sampling data injection complete.")
