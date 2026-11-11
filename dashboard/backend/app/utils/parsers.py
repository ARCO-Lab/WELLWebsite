# Turns raw vendor API records into SensorMeasurement objects and table rows.
# Pure functions (no network or database access), shared by the 10-minute ingestion
# (scripts/inject_from_api.py) and the backfills (scripts/licor_backfill.py, scripts/wqdata_backfill.py)
# so they all store identical rows.
import math
from datetime import datetime, timezone

from db.models import SensorMeasurement
from utils.timezone import as_utc
from utils.sensor_names import weather_measurement_name

# Water-level loggers report through the weather station; every sensor whose serial starts with
# this prefix is a logger channel, everything else on the station is weather.
LOGGER_PREFIX = "2216865"

QUALITY_PARAM_ID_MAP = {
    125001: {"key": "Water Temperature", "unit": "°C"},
    125002: {"key": "Conductivity", "unit": "uS/cm"},
    125004: {"key": "Salinity", "unit": "PPT"},
    125005: {"key": "TDS", "unit": "g/L"},
    125006: {"key": "ODO", "unit": "mg/L"},
    125007: {"key": "ODOSat", "unit": "%"},
    125008: {"key": "Turbidity", "unit": "NTU"},
    125009: {"key": "TSS", "unit": "mg/L"}
}

LOGGER_CONFIG = {
    # sensor_sn_base: { "logger_num": #, "station_id": #, "z": #, "L": #, "theta": # }
    "22168653": { "logger_num": 1, "station_id": 2577531, "z": 39.701, "L": 1.525, "theta": 57.7 },
    "22168654": { "logger_num": 2, "station_id": 2577532, "z": 39.767, "L": 1.781, "theta": 46.5 },
    "22168655": { "logger_num": 3, "station_id": 2577533, "z": 39.711, "L": 1.685, "theta": 49.1 },
    "22168656": { "logger_num": 4, "station_id": 2577534, "z": 39.736, "L": 1.62, "theta": 55.2 },
    "22168657": { "logger_num": 5, "station_id": 2577535, "z": 39.568, "L": 1.75, "theta": 48.4 },
}

# The unit each stored measurement is read in. A LI-COR record in another unit (a sensor swapped or reconfigured,
# say to °F or kPa) is skipped, and licor_rows reports it, rather than stored under the wrong unit or, for depth,
# turned into a wrong water surface elevation. Measurements not listed here aren't checked and keep LI-COR's unit.
# Matches the units stored in Nov 2026.
WEATHER_UNITS = {
    "Air Temperature": "°C", "Soil Temperature": "°C", "Dew Point": "°C", "Relative Humidity": "%",
    "Pressure": "mbar", "Rain": "mm", "Solar Radiation": "W/m²", "Water Content": "m³/m³",
    "Wind Speed": "m/s", "Gust Speed": "m/s", "Wind Direction": "°",
}
LOGGER_UNITS = {"1": "m", "3": "°C"}   # logger channel suffix: 1 sensor depth (for the elevation), 3 water temperature
# Other spellings LI-COR uses for an expected unit, as lowercase words (compared ignoring case and surrounding spaces;
# the units themselves must match exactly, since case matters in SI symbols: mm vs Mm, mbar vs Mbar). The water-level
# loggers' depth channels report 'meters' (seen Nov 2026); without this they'd all be skipped.
UNIT_ALIASES = {"m": {"meters", "meter", "metres", "metre"}}


def same_unit(unit, expected):
    """Whether LI-COR's unit string names the expected unit: equal, or a listed alias in any case, ignoring
    surrounding spaces. Units themselves are compared exactly: 'Mbar' (megabar) isn't 'mbar'."""
    if not isinstance(unit, str):
        return False
    unit = unit.strip()
    return unit == expected or unit.casefold() in UNIT_ALIASES.get(expected, ())


def unit_mismatch(entry):
    """(sensor_sn, LI-COR's unit, the expected unit) when a LI-COR record we store comes in an unexpected unit,
    else None."""
    sensor_sn = str(entry.get("sensor_sn") or "")
    if sensor_sn.startswith(LOGGER_PREFIX):
        base_sn, _, suffix = sensor_sn.partition("-")
        expected = LOGGER_UNITS.get(suffix) if base_sn in LOGGER_CONFIG else None
    else:
        expected = WEATHER_UNITS.get(weather_measurement_name(sensor_sn, entry.get("sensor_measurement_type")))
    unit = entry.get("unit")
    if expected is None or same_unit(unit, expected):
        return None
    return sensor_sn, unit, expected


def stored_unit(entry):
    """The unit to store with a LI-COR record that passed unit_mismatch: the expected unit when one is checked
    (so an alias such as 'meters' is stored as 'm', like the rows before it), else LI-COR's own unit."""
    sensor_sn = str(entry.get("sensor_sn") or "")
    if sensor_sn.startswith(LOGGER_PREFIX):
        expected = LOGGER_UNITS.get(sensor_sn.partition("-")[2])
    else:
        expected = WEATHER_UNITS.get(weather_measurement_name(sensor_sn, entry.get("sensor_measurement_type")))
    return expected if expected is not None else entry.get("unit", "")


# Vendors can report "no reading" as a huge negative number instead of leaving it out: every Quality measurement
# was stored as -100000 on 2026-06-12 11:10. No sensor here reads anywhere near this low, so a value at or below it
# is treated as missing. /api/series and scripts/clean_sentinels.py use the same threshold.
SENTINEL_MAX = -99999


def reading_value(raw):
    """A vendor reading as a finite float, or None when it can't be stored: missing (None or absent), not a
    number ("N/A", ""), a boolean, NaN/infinity (Python's json reads a bare NaN or Infinity), or the "no reading"
    sentinel (≤ SENTINEL_MAX, e.g. -100000). Such readings are skipped rather than stored as 0 or averaged into
    charts, and one of them no longer fails a whole ingestion run."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):   # OverflowError: an integer too large for a float
        return None
    return value if math.isfinite(value) and value > SENTINEL_MAX else None


def parse_weather_entry(entry, logger_id):
    # Parse a single weather data entry into a SensorMeasurement object
    sensor_sn = entry.get("sensor_sn")

    # Skip battery sensors
    if sensor_sn and sensor_sn.endswith("-B"):
        return None
    value = reading_value(entry.get("value"))
    if value is None or unit_mismatch(entry):
        return None

    return SensorMeasurement(
        station_id=logger_id,
        group_type="Weather",
        measurement_type=weather_measurement_name(sensor_sn, entry.get("sensor_measurement_type")),
        value=value,
        unit=stored_unit(entry),
        recorded_at=datetime.fromisoformat(entry.get("timestamp"))
    )


def parse_logger_entry(entry):
    # Parse a single logger data entry into a SensorMeasurement object
    sensor_sn = entry.get("sensor_sn", "")

    # Skip battery sensors
    if sensor_sn.endswith("-B"):
        return None

    sn_parts = sensor_sn.split('-')
    if len(sn_parts) != 2:
        return None

    base_sn, metric_suffix = sn_parts
    if base_sn not in LOGGER_CONFIG:
        return None

    config = LOGGER_CONFIG[base_sn]
    station_id = config["station_id"]
    h = reading_value(entry.get("value"))
    if h is None or unit_mismatch(entry):
        return None
    recorded_at = datetime.fromisoformat(entry.get("timestamp"))

    if metric_suffix == '1':
        # Sensor depth -> water surface elevation (m above sea level) from the logger's survey values
        wse = config["z"] - config["L"] * math.cos(math.radians(config["theta"])) + h
        return SensorMeasurement(station_id=station_id, group_type="Logger", measurement_type="Water Surface Elevation",
                                 value=wse, unit="m asl", recorded_at=recorded_at)
    if metric_suffix == '3':
        return SensorMeasurement(station_id=station_id, group_type="Logger", measurement_type="Water Temperature",
                                 value=h, unit=stored_unit(entry), recorded_at=recorded_at)
    return None


def parse_quality_entry(entry, station_id):
    # Parse a single quality data entry into a list of SensorMeasurement objects.
    # WQData timestamps are UTC without an offset.
    timestamp = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    results = []
    for reading in entry["values"]:
        param_id = reading["parameterId"]
        if param_id not in QUALITY_PARAM_ID_MAP:
            continue
        value = reading_value(reading.get("value"))
        if value is None:
            continue
        results.append(SensorMeasurement(
            station_id=station_id,
            group_type="Quality",
            measurement_type=QUALITY_PARAM_ID_MAP[param_id]["key"],
            value=value,
            unit=QUALITY_PARAM_ID_MAP[param_id]["unit"],
            recorded_at=timestamp
        ))
    return results


def to_row(obj):
    """(unique key, insertable row) for a SensorMeasurement, with recorded_at as stored: an aware UTC instant, so
    the two readings of the hour repeated when clocks fall back get different keys."""
    key = (str(obj.station_id), obj.measurement_type, as_utc(obj.recorded_at))
    return key, {"station_id": key[0], "group_type": obj.group_type, "measurement_type": key[1],
                 "value": obj.value, "unit": obj.unit, "recorded_at": key[2]}


def licor_rows(records, groups, weather_station) -> dict:
    """Rows from LI-COR records for the given groups ("Weather" and/or "Logger"), keyed by unique key.
    Prints one [ERROR] line per sensor whose records were skipped for an unexpected unit."""
    rows = {}
    wrong_units = {}
    for entry in records:
        is_logger = str(entry.get("sensor_sn", "")).startswith(LOGGER_PREFIX)
        if ("Logger" if is_logger else "Weather") not in groups:
            continue
        mismatch = unit_mismatch(entry)
        if mismatch:
            wrong_units[mismatch] = wrong_units.get(mismatch, 0) + 1
            continue
        obj = parse_logger_entry(entry) if is_logger else parse_weather_entry(entry, weather_station)
        if obj is not None:
            key, row = to_row(obj)
            rows.setdefault(key, row)
    for (sensor_sn, unit, expected), count in sorted(wrong_units.items(), key=str):
        print(f"[ERROR] LI-COR sensor {sensor_sn} reports {unit!r}, not {expected!r}: skipped its {count} "
              f"record(s). Check the sensor, then update WEATHER_UNITS/LOGGER_UNITS (or UNIT_ALIASES, for "
              f"another spelling of the same unit) in utils/parsers.py "
              f"(and convert if needed), then run scripts/licor_backfill.py --days N for the skipped period: "
              f"the 10-minute ingestion won't fetch it again, since the other sensors' readings move its start.")
    return rows


def quality_rows(entries, station_id) -> dict:
    """Rows from WQData entries, keyed by unique key."""
    rows = {}
    for entry in entries:
        for obj in parse_quality_entry(entry, station_id):
            key, row = to_row(obj)
            rows.setdefault(key, row)
    return rows
