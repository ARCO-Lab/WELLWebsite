"""Turns parsed sampling-sheet entries (api/services/sampling.py) into sampling_measurements rows.

Pure: no database. Used by scripts/inject_sampling.py, which inserts the rows with ON CONFLICT DO NOTHING
on the table's unique key and reports (never applies) skipped rows whose stored value differs.
"""
import math
from datetime import datetime

import pandas as pd

# The sampling_measurements unique key: a site, a measurement and a sampling date identify a reading.
KEY = ("site_id", "measurement_type", "recorded_at")

# Creek keyword -> creek ID (OpenStreetMap way IDs, as used by the dashboard's map)
CREEK_ID_MAP = {
    "ancaster": "19431905",
    "tiffany": "20962187",
    "sulphur": "3212839",
    "coldwater": "336415129",
    "spencer": "19755185",
}

# Keyword in the site name -> site ID
SITE_ID_MAP = {
    "Falkirk": 1,
    "Maple": 2,
    "Jerseyville": 3,
    "Sulphur": 4,
    "Sherman": 5,
    "Tiffany": 6,
    "Unknown": 7,  # Placeholder for unlisted sites
    "Osler": 8,
    "McMaster": 9,
    "Cootes": 10,
}


def resolve_creek_id(creek_name):
    creek_name_lower = creek_name.lower()
    for keyword, creek_id in CREEK_ID_MAP.items():
        if keyword in creek_name_lower:
            return creek_id
    return "00000000"  # Default if unknown


def resolve_site_id(site_name):
    for keyword, sid in SITE_ID_MAP.items():
        if keyword in site_name:
            return sid
    return SITE_ID_MAP["Unknown"]


def parse_date_flexible(date_string):
    """
    Parse date string with flexible format handling.
    Supports:
    - "2026-03-15" (date only, defaults to 00:00:00)
    - "2026-03-15 14:30:00" (date with time)
    - ISO format strings
    """
    try:
        # First try parsing as ISO format (from recorded_at field)
        if 'T' in str(date_string):
            return datetime.fromisoformat(str(date_string).replace('T', ' ').replace('Z', ''))

        # Handle date-only format (default to midnight)
        date_str = str(date_string).strip()

        # Try various date formats
        date_formats = [
            "%Y-%m-%d %H:%M:%S",  # Full datetime
            "%Y-%m-%d %H:%M",     # Date with hour:minute
            "%Y-%m-%d",           # Date only
            "%m/%d/%Y",           # US format
            "%d/%m/%Y",           # EU format
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Fallback: use pandas to_datetime which is very flexible
        parsed_date = pd.to_datetime(date_str)
        if pd.isna(parsed_date):
            raise ValueError(f"Could not parse date: {date_string}")

        # Convert to datetime and remove timezone if present
        if hasattr(parsed_date, 'tz_localize'):
            parsed_date = parsed_date.tz_localize(None)

        return parsed_date.to_pydatetime()

    except Exception as e:
        print(f"[ERROR] Failed to parse date '{date_string}': {e}")
        raise ValueError(f"Invalid date format: {date_string}")


def entry_to_row(entry):
    """One parsed sheet entry as a sampling_measurements row (raises ValueError on a bad date)."""
    return {
        "site_id": str(resolve_site_id(entry["site_id"])),
        "creek_id": resolve_creek_id(entry["creek_id"]),
        "measurement_type": entry["measurement_type"],
        "value": entry["value"],
        "unit": entry["unit"],
        "recorded_at": parse_date_flexible(entry["recorded_at"]),
    }


def row_key(row):
    """A row's unique key, in KEY order (also the order the import's RETURNING clause uses)."""
    return tuple(row[k] for k in KEY)


def values_differ(a, b):
    """True if two readings differ (None-safe; ignores float round-off)."""
    if a is None or b is None:
        return (a is None) != (b is None)
    return not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def rows_from_entries(entries, log=print):
    """Rows for every entry that parses, keeping the first of any rows that share the unique key.

    Returns (rows, stats):
    - `failed`: entries that couldn't be parsed;
    - `duplicates`: rows that repeat an earlier row of the file (same site name, measurement and date);
    - `differing_repeats`: those of the duplicates whose value differs from the kept row's, as
      (site name, measurement, date, kept value, dropped value);
    - `collisions`: rows dropped because a *different* site name maps to the same site, e.g. two
      unlisted sites that both become site 7 ("Unknown"), as (kept name, dropped name, measurement, date);
    - `unknown_sites`: names that matched no known site and whose rows were kept (stored as site 7).
    """
    rows, seen = [], {}
    stats = {"failed": 0, "duplicates": 0, "differing_repeats": [], "collisions": [], "unknown_sites": set()}
    for entry in entries:
        try:
            row = entry_to_row(entry)
        except Exception as e:
            stats["failed"] += 1
            log(f"[ERROR] Failed to parse sampling entry: {e} | {entry}")
            continue
        name = str(entry.get("site_id"))
        key = row_key(row)
        if key in seen:
            kept_name, kept_value = seen[key]
            if kept_name == name:
                stats["duplicates"] += 1
                if values_differ(kept_value, row["value"]):
                    stats["differing_repeats"].append(
                        (name, row["measurement_type"], row["recorded_at"], kept_value, row["value"]))
            else:
                stats["collisions"].append((kept_name, name, row["measurement_type"], row["recorded_at"]))
            continue
        seen[key] = (name, row["value"])
        rows.append(row)
        if row["site_id"] == str(SITE_ID_MAP["Unknown"]):
            stats["unknown_sites"].add(name)
    return rows, stats


def classify_skipped(rows, inserted_keys, stored_values):
    """Sort out the rows that ON CONFLICT DO NOTHING skipped because their key was already stored.

    `inserted_keys` holds the keys the insert returned; `stored_values` maps the other keys to their
    stored value. Returns (changed, unknown_site), each a list of (row, stored value):
    - `changed`: rows of a known site whose value differs from the stored one, e.g. a corrected
      reading. Stored values are never overwritten, so these are only reported;
    - `unknown_site`: site-7 rows that weren't inserted. Site 7 holds every unlisted site, so these
      may be readings of a different unlisted site than the stored ones, not repeats.
    """
    changed, unknown_site = [], []
    for row in rows:
        key = row_key(row)
        if key in inserted_keys:
            continue
        stored = stored_values.get(key)
        if row["site_id"] == str(SITE_ID_MAP["Unknown"]):
            unknown_site.append((row, stored))
        elif key in stored_values and values_differ(stored, row["value"]):
            changed.append((row, stored))
    return changed, unknown_site


# How to repair rows that landed on a shared site id (site 7 holds every unlisted name)
_SITE_FIX = ("add the names to SITE_ID_MAP in utils/sampling_rows.py, delete the rows already stored under the shared "
             "site id (site_id = '7' for unlisted names; otherwise they stay and those readings end up stored twice), "
             "then re-import every file with those sites")
_EXAMPLES = 5  # example rows per warning


def _sql_text(value):
    return "'" + str(value).replace("'", "''") + "'"


def import_warnings(stats, changed=(), unknown_skipped=()):
    """[WARN] lines for an import, from rows_from_entries()'s stats and classify_skipped()'s lists.

    Covers unlisted site names, rows dropped by a site-name clash (in this file, or with rows already
    stored on site 7), and readings that differ from the stored one or from an earlier row of the file.
    Differing readings are only reported: stored values are never overwritten automatically.
    """
    lines = []
    if stats["unknown_sites"]:
        lines.append(f"[WARN] Site names matching no known site map to site 7 (Unknown): "
                     f"{sorted(stats['unknown_sites'])}")
    if stats["collisions"]:
        lines.append(f"[WARN] {len(stats['collisions'])} rows were not imported because a different site name in "
                     f"this file maps to the same site. To keep both: {_SITE_FIX}. E.g.:")
        for kept, dropped, measurement, when in stats["collisions"][:_EXAMPLES]:
            lines.append(f"[WARN]   kept {kept!r}, dropped {dropped!r}: {measurement} on {when:%Y-%m-%d}")
    if unknown_skipped:
        differing = sum(values_differ(stored, row["value"]) for row, stored in unknown_skipped)
        lines.append(f"[WARN] {len(unknown_skipped)} rows of unlisted sites were not imported because site 7 "
                     f"(Unknown) already has a reading for that measurement and date ({differing} with a different "
                     f"value). They may be from a different unlisted site than the stored rows, e.g. one named in "
                     f"another file. To keep both: {_SITE_FIX}. E.g.:")
        for row, stored in unknown_skipped[:_EXAMPLES]:
            lines.append(f"[WARN]   {row['measurement_type']} on {row['recorded_at']:%Y-%m-%d}: "
                         f"stored {stored}, file {row['value']}")
    if changed:
        lines.append(f"[WARN] {len(changed)} rows differ from the stored reading and were NOT applied (stored "
                     f"values are never overwritten), e.g.:")
        for row, stored in changed[:_EXAMPLES]:
            lines.append(f"[WARN]   site {row['site_id']} {row['measurement_type']} on {row['recorded_at']:%Y-%m-%d}: "
                         f"stored {stored}, file {row['value']}")
        row = changed[0][0]
        lines.append(f"[WARN] To apply a correction, delete the stored row and re-import the file, e.g. "
                     f"DELETE FROM sampling_measurements WHERE site_id = {_sql_text(row['site_id'])} "
                     f"AND measurement_type = {_sql_text(row['measurement_type'])} "
                     f"AND recorded_at = {_sql_text(row['recorded_at'])};")
    if stats["differing_repeats"]:
        lines.append(f"[WARN] {len(stats['differing_repeats'])} rows repeat an earlier row of the file with a "
                     f"different value; the first was kept, e.g.:")
        for name, measurement, when, kept, dropped in stats["differing_repeats"][:_EXAMPLES]:
            lines.append(f"[WARN]   {name!r} {measurement} on {when:%Y-%m-%d}: kept {kept}, dropped {dropped}")
    return lines
