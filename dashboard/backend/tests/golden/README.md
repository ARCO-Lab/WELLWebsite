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
| `sensor_export_all_groups.csv` | Download Data on the dashboard (sensor tab, every group) via `/api/exports/sync` or an export job; `api/services/exports.py` | The layout `ID, Timestamp`, then Weather, Quality and Logger blocks (`Group` plus one column per metric, a blank column between blocks, one `Sensor` block per logger: the five configured ones, then any other seen). Download name `WELLWestCampus_WaterLogger_WaterQuality_WeatherStation_20261031_20261101.csv` |
| `sensor_export_two_loggers.csv` | The same, with two loggers and the metrics picked per group | The picked order of loggers and metrics. Name `WELLWestCampus_WaterLogger_20261101_20261101.csv` |
| `sampling_export.csv` | Download Data on the Ancaster Watershed tab (sampling) | One reading per row: `domain, recorded_at, group_type, station_id, creek_id, site_id, measurement_type, value, unit`. Name `well_export_sampling_20261031_20261102.csv` |
| `monthly/WELLWestCampus_Oct2026.csv`, `monthly/WELLWestCampus_Nov2026.csv` | The monthly file sent to Borealis and SharePoint (`scripts/upload_data.py`, `exported_month()`) | The dashboard layout with `Latitude, Longitude` after each `Group` and `Sensor`, only the metrics and loggers seen that month, and the month as a half-open range |
| `sampling_upload.csv` | Input, not output: a sampling file as a researcher would upload it (`docs/sampling-csv-format.md`) | |
| `sampling_upload_rows.json` | `utils/sampling_csv.validate_csv()` on that file | The rows it stores: site and creek ids, parameter and unit names after aliases, values, local times |
| `samples_ancaster_coldwater.json` | `/api/samples` for two creeks | The fields of each reading |
| `recent.json` | `/api/recent` | The latest reading of each parameter |

The fixture readings (in `test_golden_csv.py`) cover several groups and stations, missing readings and a missing
group, a stored NULL, a unit that changes partway (Turbidity FNU, then NTU: the latest unit names the column), a
unit ending in ` asl`, numbers such as `-2.5`, `0.0`, `1e-05` and `0.30000000000000004` (values are written as Python
writes floats, unrounded), the hour repeated when clocks fall back on 2026-11-01, the month boundary (the reading
at midnight on November 1 is in November's file only), and both ends of a download's date range: the dashboard
sends the picked days' bounds in UTC, so readings at 01:00 on the first day are in the file, and readings at 03:00
the day after the last (sensor) or 04:30 (sampling), before the end bound read as wall-clock time, are not. Times
are America/Toronto wall clock time with no offset, as the downloads have always shown them (sensor readings are
stored as instants, `timestamptz`, and shown in site time; sampling times are stored as naive site time).

For the fall-back hour the fixture holds a single `01:30` row per sensor and metric, given as naive site time and
so stored as its first occurrence (EDT), so the files show it once. With both copies stored (the instants 05:30Z
and 06:30Z), a download shows two lines reading `01:30`, in time order; that case is tested in
test_timestamptz_postgres.py, test_data_route.py and the end-to-end check (dashboard/e2e), not here.

No value is a vendor "no reading" sentinel such as `-100000`: these files pin the format, not how sentinels are
filtered.

Text cells starting with `=`, `+`, `-`, `@`, a tab or a carriage return get a leading `'` in the dashboard
downloads, so a spreadsheet shows them as text instead of running them; the fixtures include such a measurement
name and sampling site.

Three things are pinned as they are today, intended or not:

- The monthly file writes a stored NULL value as `nan` (the dashboard download leaves the cell empty), and it
  doesn't add the `'` to formula-like text. The monthly fixture has no formula-like text, so only the `nan` shows.
- Readings with the same time (one site's parameters, or sites sampled together) come out of the sampling download
  and `/api/samples` in no defined order, which differs between SQLite and PostgreSQL. The tests sort the rows of
  each timestamp before comparing, and the golden files are stored that way. The sensor files have one row per time,
  so their order is exact.
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
