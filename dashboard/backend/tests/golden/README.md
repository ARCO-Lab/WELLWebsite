# Golden files: the public file formats

These files are exactly what the backend produces today for a small, fixed set of readings
(`tests/test_golden_csv.py`). Researchers and other users open, script against and cite these files, so the
columns, their order, the row order, how numbers and times are written and the file names are a public format.

**If a test here fails, the format of a file people depend on has changed.** Decide whether that is intended. If it
is, regenerate the golden files (below), review the diff line by line, and say in the pull request what changes for
people who use the files. If it isn't, fix the code.

## What each file is

| File | Produced by | What it pins |
|---|---|---|
| `sensor_export_all_groups.csv` | Download Data on the dashboard (sensor tab, every group) via `/api/exports/sync` or an export job; `api/services/exports.py` | The layout `ID, Timestamp (America/Toronto)`, then Weather, Quality and Logger blocks (`Group` plus one column per metric, a blank column between blocks, one `Sensor` block per logger: the five configured ones, then any other seen). Download name `WELLWestCampus_WaterLogger_WaterQuality_WeatherStation_20261031_20261101.csv` |
| `sensor_export_two_loggers.csv` | The same, with two loggers and the metrics picked per group | The picked order of loggers and metrics. Name `WELLWestCampus_WaterLogger_20261101_20261101.csv` |
| `sampling_export.csv` | Download Data on the Ancaster Watershed tab (sampling) | One reading per row: `domain, recorded_at (America/Toronto), group_type, station_id, creek_id, site_id, measurement_type, value, unit`. Name `well_export_sampling_20261031_20261102.csv` |
| `monthly/WELLWestCampus_Oct2026.csv`, `monthly/WELLWestCampus_Nov2026.csv` | The monthly file sent to Borealis and SharePoint (`scripts/upload_data.py`, `exported_month()`) | The dashboard layout with `Latitude, Longitude` after each `Group` and `Sensor`, only the metrics and loggers seen that month, and the month as a half-open range. The same cell rules as the dashboard download (empty for a missing value, `'` before formula-like text) |
| `sampling_upload.csv` | Input, not output: a sampling file as a researcher would upload it (`docs/sampling-csv-format.md`) | |
| `sampling_upload_rows.json` | `utils/sampling_csv.validate_csv()` on that file | The rows it stores: site and creek ids, parameter and unit names after aliases, values, local times |
| `samples_ancaster_coldwater.json` | `/api/samples` for two creeks | The fields of each reading, and their order (time, site, parameter) |
| `recent.json` | `/api/recent` | The latest reading of each parameter |

The fixture readings (in `test_golden_csv.py`) cover several groups and stations, missing readings and a missing
group, a stored NULL, a unit that changes partway (Turbidity FNU, then NTU: the latest unit names the column), a
unit ending in ` asl`, numbers such as `-2.5`, `0.0`, `1e-05` and `0.30000000000000004` (values are written as Python
writes floats, unrounded), the hour repeated when clocks fall back on 2026-11-01, the month boundary (the reading
at midnight on November 1 is in November's file only), and both ends of a download's date range: the dashboard
sends the picked days' bounds in UTC, so readings at 01:00 on the first day are in the file, and readings at 03:00
the day after the last (sensor) or 04:30 (sampling), before the end bound read as wall-clock time, are not. Times
are America/Toronto wall clock time with no offset, as stored; the time column's header names the zone
(`Timestamp (America/Toronto)`, `recorded_at (America/Toronto)`).

For the fall-back hour the fixture holds a single naive `01:30` row per sensor and metric, which is all ingestion's
unique key (station, metric, naive time) can store of that hour, so the files show it once. How ingestion collapses
the two `01:30` readings isn't tested here; the files show what is stored.

No value is a vendor "no reading" sentinel such as `-100000`: these files pin the format, not how sentinels are
filtered.

Text cells starting with `=`, `+`, `-`, `@`, a tab or a carriage return get a leading `'` in the dashboard
downloads and the monthly file, so a spreadsheet shows them as text instead of running them; the fixtures include
such a measurement name and sampling site. A missing value (a stored NULL or NaN) is an empty field in every file.

Rows that share a time come in a fixed order: sampling rows by site number, then parameter (text compared byte for
byte, so the same on SQLite and PostgreSQL whatever its locale; `db/ordering.py`), in the sampling download,
`/api/samples` and `/api/recent`. Sensor readings of one time are read by station, then metric, so a cell two
stations could fill is always filled the same way.

One thing is pinned as it is today, intended or not:

- The monthly file's headers keep the unit as stored, `Water Surface Elevation: m asl`, while the dashboard
  download drops ` asl` (`Water Surface Elevation: m`).

## Regenerating

Only when a format change is intended. From `dashboard/backend`, with the backend's requirements installed:

```sh
UPDATE_GOLDEN=1 python -m unittest tests.test_golden_csv
git diff tests/golden
```

or in the backend image, as CI runs it:

```sh
docker build -t well-backend:golden dashboard/backend
docker run --rm -v "$PWD/dashboard/backend/tests:/app/tests" -w /app -e UPDATE_GOLDEN=1 well-backend:golden \
  python -m unittest tests.test_golden_csv
```

Then run the tests again without `UPDATE_GOLDEN`, and with `TEST_POSTGRES_URL` set to a throwaway PostgreSQL
database (CI does both): the same golden files must hold on SQLite and PostgreSQL.

The files are compared byte for byte, line endings included (the CSV files are written with CRLF line endings, as
Python's `csv` module does). `.gitattributes` here keeps git from changing them.
