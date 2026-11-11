# WELL Data Upload Instructions for Dataverse

## Overview
This document explains how to upload creek sampling data to the WELL (Watershed and Ecosystems Living Lab) dataset
on Dataverse (Borealis) so that the dashboard imports it automatically.

## File format

**Use the standard sampling CSV format: [docs/sampling-csv-format.md](../../../../docs/sampling-csv-format.md).**
Start from the template, `dashboard/backend/app/sampling_template.csv`, which the dashboard also offers as
"CSV template" on its Ancaster Watershed tab. In short: UTF-8 CSV, one reading per row, columns `date` (YYYY-MM-DD),
optional `time` (24-hour HH:MM, local time), `site`, `parameter`, `value`, `unit`, plus optional
`below_detection`, `qc_flag`, `sampler`, `method` and `notes`.

Every file is checked in full before anything is imported. If any row has a problem (an unknown site, a date such as
`01/02/2026` that could be read two ways, a unit that doesn't match the parameter, a repeated reading...), **nothing
from that file is imported**, and the import log lists each problem with its row number. Check a file yourself before
uploading it:

```sh
cd dashboard/backend/app
python scripts/check_sampling_csv.py WELLAncasterWatershed_May2026.csv
```

Excel files (`.xlsx`) in the older one-row-per-visit layout are still accepted and go through the same checks; see
the format page.

## Naming convention

`WELLAncasterWatershed_[description].csv` (or `.xlsx`)
- **Required prefix**: `WELLAncasterWatershed_`
- **Description**: a meaningful identifier, e.g. `WELLAncasterWatershed_May2026.csv`,
  `WELLAncasterWatershed_Site1_Q1.csv`
- Files without the prefix (e.g. `lancaster_data.csv`) and `WELLAncasterWatershed_SAMPLE.*` are ignored.

## Upload
1. Log into the Dataverse repository and open the WELL dataset.
2. Upload the file (Dataverse may show a CSV as `.tab` after upload; that's expected, the original is what's
   imported).
3. Check that the filename follows the naming convention.

## Troubleshooting

**My file wasn't imported.** The import log lists each problem with its row number: fix the rows and upload the file
again. Running `scripts/check_sampling_csv.py` on the file shows the same list.

**I need a new site or parameter.** Contact the WELL dashboard team first: the dashboard needs to know where a site is
and how to show a parameter, and until then rows with it are rejected.

**I uploaded a corrected value.** Readings already stored are never overwritten automatically. The import log reports
the difference and the SQL to remove the old reading; after that, importing the file again stores the new value.

**Can I upload multiple files at once?** Yes. Each file is checked and imported on its own, and re-importing a file
(or one that overlaps another) never stores a reading twice.
