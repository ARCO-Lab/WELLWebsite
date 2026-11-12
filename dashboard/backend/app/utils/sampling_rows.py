"""Reports on a sampling import's skipped rows. Pure: no database.

utils/sampling_csv.py turns a file into sampling_measurements rows; scripts/inject_sampling.py inserts them with
ON CONFLICT DO NOTHING on the table's unique key, so a re-import adds nothing. A skipped row whose stored value
differs (e.g. a corrected reading) is reported here, never applied.
"""
import math

from utils.sampling_csv import KEY

__all__ = ["KEY", "row_key", "values_differ", "classify_skipped", "check_skipped", "import_warnings"]

_EXAMPLES = 5  # example rows per warning


def row_key(row):
    """A row's unique key, in KEY order (also the order the import's RETURNING clause uses)."""
    return tuple(row[k] for k in KEY)


def values_differ(a, b):
    """True if two readings differ (None-safe; ignores float round-off)."""
    if a is None or b is None:
        return (a is None) != (b is None)
    return not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def classify_skipped(rows, inserted_keys, stored_values):
    """The rows that ON CONFLICT DO NOTHING skipped and whose value differs from the stored one, as (row, stored).

    `inserted_keys` holds the keys the insert returned; `stored_values` maps the other keys to their stored value.
    Stored values are never overwritten, so these are only reported.
    """
    changed = []
    for row in rows:
        key = row_key(row)
        if key not in inserted_keys and key in stored_values and values_differ(stored_values[key], row["value"]):
            changed.append((row, stored_values[key]))
    return changed


def check_skipped(rows, inserted_keys, fetch_stored, log=print):
    """classify_skipped() on the stored values that fetch_stored(keys) returns for the skipped keys.

    Best effort: the rows are already committed and the "Inserted N" line printed by then, so a failed lookup only
    logs a [WARN] and returns no findings, rather than failing the import.
    """
    skipped = [row_key(r) for r in rows if row_key(r) not in inserted_keys]
    if not skipped:
        return []
    try:
        stored_values = fetch_stored(skipped)
    except Exception as e:
        log(f"[WARN] Could not compare the {len(skipped)} skipped rows with the stored ones ({e}); corrected "
            f"readings are not reported for this run.")
        return []
    return classify_skipped(rows, inserted_keys, stored_values)


def _sql_text(value):
    # A value as an SQL string literal, for the example DELETE printed below (shown to a person, never executed).
    return "'" + str(value).replace("'", "''") + "'"


def import_warnings(changed):
    """[WARN] lines for readings that differ from the stored one (stored values are never overwritten)."""
    if not changed:
        return []
    lines = [f"[WARN] {len(changed)} rows differ from the stored reading and were NOT applied (stored values are "
             f"never overwritten), e.g.:"]
    for row, stored in changed[:_EXAMPLES]:
        lines.append(f"[WARN]   site {row['site_id']} {row['measurement_type']} on "
                     f"{row['recorded_at']:%Y-%m-%d %H:%M}: stored {stored}, file {row['value']}")
    row = changed[0][0]
    lines.append(f"[WARN] To apply a correction, delete the stored row and re-import the file, e.g. "
                 f"DELETE FROM sampling_measurements WHERE site_id = {_sql_text(row['site_id'])} "
                 f"AND measurement_type = {_sql_text(row['measurement_type'])} "
                 f"AND recorded_at = {_sql_text(row['recorded_at'])};")
    return lines
