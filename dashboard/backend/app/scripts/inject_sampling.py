# Loads a creek sampling file into the database: a standard sampling CSV (docs/sampling-csv-format.md) or an Excel
# sheet in the older one-row-per-visit layout.
#   python scripts/inject_sampling.py <file>                 add every reading that isn't stored yet, and apply the
#                                                            file's corrections to stored ones
#   python scripts/inject_sampling.py <file> --full-reload   replace all sampling data (needs ALLOW_WIPE=1)
#       add --allow-shrink if the file has fewer than half as many readings as are stored now
# The file is checked first (utils/sampling_csv.py) and nothing is stored unless all of it is valid; the problems
# are listed with their row numbers (the first MAX_LISTED, then the total) and the exit code is
# INVALID_FILE_EXIT (3). Any other failure exits 1. To only check a file: scripts/check_sampling_csv.py.
# A stored reading whose value (or unit) the file changes is updated, with one [CORRECTED] line each: the file
# imported last is taken as the lab's latest word (scripts/download_data.py imports the dataset's files oldest
# first). download_data.py passes --newer '<json>', the scopes of the files already imported that are newer than
# this one, and a correction to a reading one of them covers is held back and reported instead ([WARN] lines), so a
# file retried or re-imported out of order never undoes a newer file's value. A successful import prints the file's
# own scope on a [SCOPE] line, which download_data.py records. Stored readings the file covers (same sites, parameters and days) but no longer has are kept and reported
# in [WARN] lines, "N rows present in the DB but not in the latest file", for a person to decide.

import json
import sys
import pathlib
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from server import create_app
from db.database import db
from db.models import SamplingMeasurement
from utils.sampling_csv import INVALID_FILE_EXIT, validate_file
from utils.sampling_rows import (KEY, correction_lines, file_scope, held_lines, hold_back, row_key, scope_from_json,
                                 scope_json, split_rows, withdrawn, withdrawn_lines)

app = create_app()

MAX_LISTED = 50          # problems printed per file; a file with a systematic mistake can have thousands
SHRINK_LIMIT = 0.5       # --full-reload refuses a file with fewer readings than this share of the stored ones


class InvalidFile(Exception):
    """The file has problems; nothing was stored."""


class RefusedReload(Exception):
    """--full-reload was refused before anything was deleted."""


def load_valid_rows(file_path):
    """The file's rows, or InvalidFile after printing its problems."""
    print(f"[INFO] Loading file: {file_path}")
    result = validate_file(file_path)
    for note in result.notes:
        print(f"[INFO] {note}")
    if not result.ok:
        for issue in result.errors[:MAX_LISTED]:
            print(f"[ERROR] {issue}")
        if len(result.errors) > MAX_LISTED:
            print(f"[ERROR] ... and {len(result.errors) - MAX_LISTED} more problems not listed "
                  f"(scripts/check_sampling_csv.py lists them all)")
        # download_data.py reads the count from this line
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


def fetch_stored(session, keys):
    """{key: (value, unit)} of the stored rows with these keys."""
    key_cols = [SamplingMeasurement.__table__.c[k] for k in KEY]
    stored = {}
    for i in range(0, len(keys), 1000):
        query = (select(*key_cols, SamplingMeasurement.value, SamplingMeasurement.unit)
                 .where(tuple_(*key_cols).in_(keys[i:i + 1000])))
        stored.update({tuple(r[:3]): (r[3], r[4]) for r in session.execute(query)})
    return stored


def apply_rows(session, rows, newer=()):
    """Insert the file's new rows and update the stored ones whose value or unit it changes, except those a file in
    `newer` covers (utils/sampling_rows.hold_back). Returns (keys inserted, corrections applied as (row, old value,
    old unit), corrections held back as (row, old value, old unit, newer file)). The caller commits."""
    new_rows, changed = split_rows(rows, fetch_stored(session, [row_key(r) for r in rows]))
    corrections, held = hold_back(changed, newer)
    inserted_keys = store_rows(session, new_rows)
    table = SamplingMeasurement.__table__
    for row, _, _ in corrections:
        session.execute(update(table)
                        .where(*(table.c[k] == row[k] for k in KEY))
                        .values(value=row["value"], unit=row["unit"], creek_id=row["creek_id"]))
    return inserted_keys, corrections, held


def find_withdrawn(session, rows):
    """Stored rows the file covers (its sites, parameters and days, utils/sampling_rows.file_scope) but doesn't
    have, as dicts with the KEY columns and "value", oldest first."""
    scope = file_scope(rows)
    if scope is None:
        return []
    m = SamplingMeasurement
    query = (select(m.site_id, m.measurement_type, m.recorded_at, m.value)
             .where(m.site_id.in_(scope["sites"]), m.measurement_type.in_(scope["measurement_types"]),
                    m.recorded_at >= scope["start"], m.recorded_at < scope["end"])
             .order_by(m.recorded_at, m.site_id, m.measurement_type))
    stored = [dict(zip(("site_id", "measurement_type", "recorded_at", "value"), r)) for r in session.execute(query)]
    return withdrawn(rows, stored)


def parse_newer(text):
    """--newer's JSON, a list of {"file": name, "scope": scope_json or null}, as hold_back()'s (name, scope) pairs."""
    return [(entry["file"], scope_from_json(entry.get("scope"))) for entry in json.loads(text)]


def inject_new_sampling_data(file_path, return_only=False, session=None, newer=()):
    """
    Add every reading of a sampling file that isn't in the database yet, and apply its corrections.

    Rows are matched on the table's unique key (site, measurement, sampling date and time), so re-importing a file
    changes nothing, and a file with older dates (a backfill, or a creek reported late) adds exactly the missing
    rows. A stored reading with a different value in the file is updated (one [CORRECTED] line each). Stored rows
    the file covers but no longer has are kept and reported ([WARN] lines), and so are corrections to readings that
    a file in `newer` ((name, scope) of each newer file already imported) covers: those aren't applied.

    Args:
        file_path: Path to the file on disk
        return_only: If True, return the parsed rows without inserting them
        session: the database session (default: the app's)
        newer: the newer files already imported, as (name, scope) pairs (parse_newer)
    """
    rows = load_valid_rows(file_path)
    if return_only:
        return rows
    session = session or db.session
    try:
        inserted_keys, corrections, held = apply_rows(session, rows, newer)
        gone = find_withdrawn(session, rows)
        session.commit()
    except Exception:
        session.rollback()
        raise
    # download_data.py reads the Inserted, Corrected, "corrections not applied" and "rows present in the DB" lines
    # for its run summary (and Inserted to decide that a file counts as processed), and records the [SCOPE] line
    print(f"[INFO] Inserted {len(inserted_keys)} new sampling records.")
    print(f"[INFO] Corrected {len(corrections)} stored sampling records (the file's value replaced the stored one).")
    for line in correction_lines(corrections):
        print(line)
    for line in held_lines(held):
        print(line)
    print(f"[INFO] {len(rows) - len(inserted_keys) - len(corrections) - len(held)} were already stored with the "
          f"same value.")
    for line in withdrawn_lines(gone):
        print(line)
    print(f"[SCOPE] {json.dumps(scope_json(file_scope(rows)))}")
    return rows


def replace_all(session, file_path, allow_shrink=False):
    """Replace every stored sampling row with the file's, in one transaction. Returns the number stored.

    Refuses (RefusedReload, nothing deleted) when the file is invalid (InvalidFile) or has fewer than SHRINK_LIMIT
    of the readings stored now, unless allow_shrink: a truncated or wrong file mustn't empty the table.
    """
    from utils.guards import require_wipe_permission  # local: keeps this change apart from the import block
    require_wipe_permission("all sampling data (--full-reload)")
    rows = load_valid_rows(file_path)  # checked before anything is deleted
    stored = session.execute(select(func.count()).select_from(SamplingMeasurement)).scalar_one()
    if not allow_shrink and len(rows) < SHRINK_LIMIT * stored:
        raise RefusedReload(f"the file has {len(rows)} readings but {stored} are stored; replacing them would remove "
                            f"{stored - len(rows)}. Nothing was deleted. If that is intended, run again with "
                            f"--allow-shrink.")
    try:
        print(f"[INFO] Clearing the {stored} stored SamplingMeasurement records ...")
        session.query(SamplingMeasurement).delete()
        inserted = store_rows(session, rows)
        session.commit()
    except Exception:
        session.rollback()   # the DELETE is undone too
        raise
    print(f"[DONE] Inserted {len(inserted)} total sampling records.")
    return len(inserted)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python inject_sampling.py <file_path> [--full-reload [--allow-shrink]] "
              "[--newer '<json>']")
        print("  --full-reload: Replace all existing data (default: incremental)")
        print("  --newer: newer files already imported, whose readings this file's corrections must not change")
        sys.exit(1)

    file_path = sys.argv[1]
    full_reload = "--full-reload" in sys.argv
    newer = parse_newer(sys.argv[sys.argv.index("--newer") + 1]) if "--newer" in sys.argv else []

    with app.app_context():
        try:
            if full_reload:
                print("[INFO] Full reload mode - replacing all existing data...")
                replace_all(db.session, file_path, allow_shrink="--allow-shrink" in sys.argv)
            else:
                print("[INFO] Incremental mode - adding only new records...")
                inject_new_sampling_data(file_path, newer=newer)
        except InvalidFile as e:
            print(f"[ERROR] {e}")
            sys.exit(INVALID_FILE_EXIT)
        except RefusedReload as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    print("[DONE] Sampling data injection complete.")
