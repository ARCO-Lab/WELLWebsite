# Sampling data: the standard CSV format

Creek sampling results reach the dashboard's **Ancaster Watershed** tab as files. This page says how to write a
file so that it imports reliably. The template, with a header and example rows, is
[`dashboard/backend/app/sampling_template.csv`](../dashboard/backend/app/sampling_template.csv); the dashboard
links to it under **Download Data** on the Ancaster Watershed tab ("CSV template").

The import checks the whole file first and lists every problem with its row number. **If anything is wrong, nothing
from the file is stored**: fix the rows it names and upload the file again. To check a file yourself before
uploading it (nothing is written anywhere):

```sh
cd dashboard/backend/app
python scripts/check_sampling_csv.py ~/WELLAncasterWatershed_May2026.csv
```

## The file

- **UTF-8 text, comma-separated, with a header row.** In Excel: *File > Save As > CSV UTF-8 (Comma delimited)*.
  Values that contain a comma must be in double quotes (Excel does this for you).
- **One reading per row** ("long" layout): one site, one parameter, one date. A visit where nine parameters were
  measured is nine rows.
- Column names are not case-sensitive and may come in any order. Columns not listed below are an error, so a typo
  in a header is caught rather than ignored.
- Empty lines are ignored, and so are columns with neither a header nor any value (Excel sometimes saves a few
  trailing `,,`). A column with values but no header is an error.
- A file with no readings at all (only blank or rejected rows) is an error.

### Columns

| Column | Required | What to write |
|---|---|---|
| `date` | yes | The sampling date as `YYYY-MM-DD`, e.g. `2026-05-06`. Nothing else is accepted: `05/06/2026` could be 5 June or 6 May, so it is rejected. In Excel, format the column as `yyyy-mm-dd` before saving. |
| `time` | no | Time of sampling, 24-hour `HH:MM` (`09:40`, `14:05`), local Hamilton time (America/Toronto, EST/EDT as on your watch). Leave empty if not recorded; the reading is then stored at midnight of that date. A time in the hour repeated when clocks fall back (e.g. `01:30` on the first Sunday of November) is stored as written, without recording which of the two it was. |
| `site` | yes | One of the sites below: its name (`Falkirk Forest`), its number (`1`), or both as on the field sheet (`#1 Falkirk Forest`). Case and extra spaces don't matter; spelling does. |
| `parameter` | yes | One of the parameters below. |
| `value` | yes | A plain number in digits 0–9, with a `.` for decimals and no thousands separator: `1295`, `0.015`, `1.5e-3`. See *Blanks* and *Below the detection limit*. |
| `unit` | yes | The parameter's unit from the table below. A different unit is an error, not converted: convert the value first. `uS/cm` is accepted for `µS/cm`. May be left empty on a blank row. |
| `creek` | no | The creek's name. If given it must be the site's creek (a cross-check against site mix-ups). |
| `below_detection` | no | `true` if the value is below the detection limit (see below); `false` or empty otherwise. |
| `qc_flag` | no | `ok`, `suspect` or `rejected` (or empty). `rejected` rows are checked but not imported. |
| `sampler` | no | Who sampled (initials are fine). |
| `method` | no | Method or instrument. |
| `notes` | no | Anything else (weather, a missed site, ...). |

`creek`, `below_detection` (beyond what the stored value means), `qc_flag`, `sampler`, `method` and `notes` are
checked but are **not stored in the dashboard's database**; they stay in the uploaded file, which is the archived
copy.

### Sites

| `site` number | Name | Creek |
|---|---|---|
| 1 | Falkirk Forest | Tiffany Creek |
| 2 | Maple Lane Pk | Ancaster Creek |
| 3 | Jerseyville Rd | Sulphur Creek |
| 4 | Sulphur Springs | Sulphur Creek |
| 5 | Sherman Falls | Ancaster Creek |
| 6 | Tiffany Falls | Tiffany Creek |
| 8 | Osler Dr | Coldwater Creek |
| 9 | McMaster Lot P | Coldwater Creek |
| 10 | Cootes Dr | Spencer's Creek |

There is no site 7. A site that isn't in this list is an error: a new site has to be added to the dashboard (its map
position and filters) before its data can be imported, so ask the dashboard maintainers.

### Parameters and units

| `parameter` | `unit` | Also accepted as the name |
|---|---|---|
| E. coli | CFU/100 mL | E.coli, E coli |
| Total coliform | CFU/100 mL | |
| Turbidity | NTU | |
| pH | pH units (or `pH`) | |
| Conductivity | µS/cm | Specific conductance |
| Chloride | mg/L | |
| Total phosphorus | µg/L | TP |
| Soluble reactive phosphorus | µg/L | SRP |
| Total nitrogen | mg/L | TN |
| Nitrate nitrogen | mg/L | Nitrate-N, Total nitrate nitrogen |
| Ammonia nitrogen | mg/L | Ammonia-N, Total ammonia nitrogen |

Negative values are rejected, and pH must be between 0 and 14. Other parameters (e.g. TSS or water temperature) are
not shown by the dashboard, so rows with them are rejected.

### Blanks: a parameter that wasn't measured

Leave the row out, or leave `value` empty (`NA` and `N/A` mean the same). Such rows are skipped, not stored as zero,
and their `unit` may be empty. Never write `0` for "not measured".

### Below the detection limit

Write the detection limit with a `<` in front, e.g. `<0.01`, or write the limit and `below_detection` = `true`
(both together are fine too). The dashboard stores the detection limit itself as the value, so a chart shows an upper
bound, not a measurement.

Values above an upper limit (`>2420`) are rejected: write the number and put the limit in `notes`.

### Duplicates and replicates

Each site, parameter, date and time has **one** value. A second row with the same four is an error, even with the
same value. For replicates or duplicate samples, report their mean and say so in `notes` (e.g. `mean of 3
replicates`). Two samples taken at different times on one day are different readings: give each its `time`.

Re-importing a file adds nothing: readings already stored with the same value are skipped. A row whose value (or
unit) differs from the stored one is a **correction and is applied**: the stored reading takes the file's value, and
the import log has one `[CORRECTED]` line per change with the old and new value. Files are imported oldest first, so
the newest upload's value is the one kept. A file imported after a newer one (an older upload whose import failed
and is retried, or one re-imported by hand) doesn't change readings the newer file covers: those differences are
reported as "corrections not applied" instead. A stored reading that the file covers (same site, parameter and a date
between the file's first and last) but no longer has is **kept**, not deleted: the log reports "N rows present in
the DB but not in the latest file" with the rows and an example `DELETE`, so a maintainer can remove them if the
file withdrew them on purpose.

## Files uploaded to the dataset

The weekly download imports each new file of the Borealis dataset once. A file with problems is **refused**: its
problems are logged once (the first 50, then the total), the run is reported as failed, and the file isn't tried
again. Upload a corrected file (Borealis gives it a new id) and it is imported on the next run. A maintainer can
re-import a specific file with `python scripts/download_data.py --force --file <id or filename>`.

## Older Excel sheets

Excel files in the older layout (one row per site visit: `Date`, `Site`, optionally `Stream`, then one column per
parameter such as `E. coli (CFU/100 mL)`) still import, through the same checks: each filled cell becomes one
reading. Their known extra columns (`Trip #`, `Year`, `Latitude`, `Longitude`, `Weather`, `Note`, `TSS (mg/L)`,
`Temp (C)`) are read but not imported. Any other column is an error, and so are two headers that mean the same
column and a workbook with data on more than one sheet. New files should use the CSV format above.

## Example

```csv
date,time,site,parameter,value,unit,below_detection,qc_flag,sampler,method,notes
2026-05-06,09:40,Falkirk Forest,E. coli,48,CFU/100 mL,,ok,AB,membrane filtration,
2026-05-06,09:40,Falkirk Forest,Ammonia nitrogen,<0.01,mg/L,true,ok,AB,,below the 0.01 mg/L detection limit
2026-05-06,10:15,Maple Lane Pk,pH,8.06,pH units,,,AB,field meter,
```

## For maintainers

- The site and parameter lists are defined once for imports, in `dashboard/backend/app/utils/sampling_csv.py`
  (`SITES`, `PARAMETERS`). The dashboard's own lists, in
  `dashboard/frontend/src/components/config/filters.tsx`, must name the same sites and parameters; change both
  together, and this page.
- `validate_file(path)` in that module checks a file and returns every problem; it needs no database, so any source of
  files (such as the Borealis download in `scripts/download_data.py`) can use it. `scripts/inject_sampling.py`
  imports a file with it, and `scripts/check_sampling_csv.py` only checks.
- Why one reading per row: the field sheets so far have had different columns from trip to trip (parameters missing
  for a trip, renamed or misspelled headers), and a wide sheet has no room for a per-value detection-limit flag, QC
  flag or method. In the long layout a new parameter is a new row value, not a new column, and every value is checked
  against its own unit.
