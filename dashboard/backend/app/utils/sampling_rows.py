"""Turns parsed sampling-sheet entries (api/services/sampling.py) into sampling_measurements rows.

Pure: no database. Used by scripts/inject_sampling.py, which inserts the rows with
ON CONFLICT DO NOTHING on the table's unique key.
"""
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


def rows_from_entries(entries, log=print):
    """Rows for every entry that parses, keeping the first of any rows that share the unique key.

    Returns (rows, stats):
    - `failed`: entries that couldn't be parsed;
    - `duplicates`: rows that repeat an earlier row of the file (same site name, measurement and date);
    - `collisions`: rows dropped because a *different* site name maps to the same site, e.g. two
      unlisted sites that both become site 7 ("Unknown"), as (kept name, dropped name, measurement, date);
    - `unknown_sites`: names that matched no known site and whose rows were kept (stored as site 7).
    """
    rows, seen = [], {}
    stats = {"failed": 0, "duplicates": 0, "collisions": [], "unknown_sites": set()}
    for entry in entries:
        try:
            row = entry_to_row(entry)
        except Exception as e:
            stats["failed"] += 1
            log(f"[ERROR] Failed to parse sampling entry: {e} | {entry}")
            continue
        name = str(entry.get("site_id"))
        key = tuple(row[k] for k in KEY)
        if key in seen:
            if seen[key] == name:
                stats["duplicates"] += 1
            else:
                stats["collisions"].append((seen[key], name, row["measurement_type"], row["recorded_at"]))
            continue
        seen[key] = name
        rows.append(row)
        if row["site_id"] == str(SITE_ID_MAP["Unknown"]):
            stats["unknown_sites"].add(name)
    return rows, stats
