"""How a sampling import compares a file's rows with the stored ones. Pure: no database.

utils/sampling_csv.py turns a file into sampling_measurements rows, keyed by the table's unique key (site,
measurement, sampling date and time). scripts/inject_sampling.py looks up the stored rows with the file's keys and
uses split_rows() here: a key not stored yet is a new row, and a stored key whose value (or unit) differs is a
correction, applied because the newer file is the lab's latest word (scripts/download_data.py imports the dataset's
files oldest first, so the newest upload is applied last). A file imported out of that order (an older file retried
after a newer one, or re-imported by hand) must not undo a newer file's values, so a correction to a reading that an
already imported newer file covers is held back and reported instead (hold_back()). Stored rows that the file covers
but no longer has (withdrawn()) are only reported, never deleted: a row missing from a file may be a mistake in the
file.
"""
import datetime as dt
import math

from utils.sampling_csv import KEY

__all__ = ["KEY", "row_key", "values_differ", "split_rows", "file_scope", "scope_json", "scope_from_json", "covers",
           "hold_back", "withdrawn", "correction_lines", "held_lines", "withdrawn_lines"]

_EXAMPLES = 20  # rows listed per report; the count is always given in full


def row_key(row):
    """A row's unique key, in KEY order (also the order the import's RETURNING clause uses)."""
    return tuple(row[k] for k in KEY)


def values_differ(a, b):
    """True if two readings differ (None-safe; ignores float round-off)."""
    if a is None or b is None:
        return (a is None) != (b is None)
    return not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def split_rows(rows, stored):
    """(new rows, corrections) of a file's `rows` against `stored`, which maps the keys already stored to their
    (value, unit). A correction is (row, stored value, stored unit) for a stored key whose value or unit differs
    from the file's. Rows stored with the same value are in neither list."""
    new, corrections = [], []
    for row in rows:
        key = row_key(row)
        if key not in stored:
            new.append(row)
            continue
        value, unit = stored[key]
        if values_differ(value, row["value"]) or (unit or "") != (row["unit"] or ""):
            corrections.append((row, value, unit))
    return new, corrections


def file_scope(rows):
    """What a file covers, to find stored rows it no longer has: its sites, its measurement types, and its sampling
    days from the first to the last ([start, end) as midnights). None for a file with no rows."""
    if not rows:
        return None
    days = [row["recorded_at"].date() for row in rows]
    return {"sites": sorted({row["site_id"] for row in rows}),
            "measurement_types": sorted({row["measurement_type"] for row in rows}),
            "start": dt.datetime.combine(min(days), dt.time()),
            "end": dt.datetime.combine(max(days) + dt.timedelta(days=1), dt.time())}


def scope_json(scope):
    """A file_scope() as JSON-ready values (times as ISO text), as recorded for each processed file."""
    return None if scope is None else {**scope, "start": scope["start"].isoformat(), "end": scope["end"].isoformat()}


def scope_from_json(value):
    """The inverse of scope_json(). None (unknown: a file imported before scopes were recorded) stays None."""
    if value is None:
        return None
    return {**value, "start": dt.datetime.fromisoformat(value["start"]),
            "end": dt.datetime.fromisoformat(value["end"])}


def covers(scope, row):
    """True if `scope` (file_scope) covers the row's reading. A scope of None is unknown and covers everything."""
    if scope is None:
        return True
    return (row["site_id"] in scope["sites"] and row["measurement_type"] in scope["measurement_types"]
            and scope["start"] <= row["recorded_at"] < scope["end"])


def hold_back(corrections, newer):
    """(corrections to apply, corrections held back), given `newer`: (file name, scope) of each file already imported
    that is newer than this one. A correction that a newer file covers is held back, as (row, stored value, stored
    unit, that file's name), so an older file never undoes a newer file's value."""
    apply, held = [], []
    for row, value, unit in corrections:
        newer_file = next((name for name, scope in newer if covers(scope, row)), None)
        if newer_file is None:
            apply.append((row, value, unit))
        else:
            held.append((row, value, unit, newer_file))
    return apply, held


def withdrawn(rows, stored_in_scope):
    """The stored rows within the file's scope (file_scope) whose key isn't in the file's `rows`. `stored_in_scope`
    holds dicts with the KEY columns and "value"."""
    keys = {row_key(row) for row in rows}
    return [row for row in stored_in_scope if row_key(row) not in keys]


def _describe(row):
    return f"site {row['site_id']} {row['measurement_type']} on {row['recorded_at']:%Y-%m-%d %H:%M}"


def _reading(value, unit):
    return f"{value} {unit or ''}".strip()


def correction_lines(corrections):
    """One [CORRECTED] line per stored reading the file changed."""
    return [f"[CORRECTED] {_describe(row)}: {_reading(value, unit)} -> {_reading(row['value'], row['unit'])}"
            for row, value, unit in corrections]


def held_lines(held):
    """[WARN] lines for the corrections held back because a newer file covers the reading (hold_back)."""
    if not held:
        return []
    lines = [f"[WARN] {len(held)} corrections not applied: a newer file, already imported, covers these readings, so "
             f"its values stay. If this file is the right one, update them by hand:"]
    for row, value, unit, newer_file in held[:_EXAMPLES]:
        lines.append(f"[WARN]   {_describe(row)}: stored {_reading(value, unit)}, this file "
                     f"{_reading(row['value'], row['unit'])} (newer: {newer_file})")
    if len(held) > _EXAMPLES:
        lines.append(f"[WARN]   ... and {len(held) - _EXAMPLES} more")
    return lines


def _sql_text(value):
    # A value as an SQL string literal, for the example DELETE printed below (shown to a person, never executed).
    return "'" + str(value).replace("'", "''") + "'"


def withdrawn_lines(rows):
    """[WARN] lines for stored rows the file covers but no longer has: they are kept, and a person decides."""
    if not rows:
        return []
    lines = [f"[WARN] {len(rows)} rows present in the DB but not in the latest file (same sites, parameters and "
             f"dates as the file covers). They were kept; if the file withdrew them on purpose, delete them by hand:"]
    for row in rows[:_EXAMPLES]:
        lines.append(f"[WARN]   {_describe(row)}: stored {row['value']}")
    if len(rows) > _EXAMPLES:
        lines.append(f"[WARN]   ... and {len(rows) - _EXAMPLES} more")
    row = rows[0]
    lines.append(f"[WARN] e.g. DELETE FROM sampling_measurements WHERE site_id = {_sql_text(row['site_id'])} "
                 f"AND measurement_type = {_sql_text(row['measurement_type'])} "
                 f"AND recorded_at = {_sql_text(row['recorded_at'])};")
    return lines
