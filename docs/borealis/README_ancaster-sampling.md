# WELL Ancaster Watershed Sampling Uploads

Grab sampling results from creeks in the Ancaster Creek watershed near McMaster University, Hamilton, Ontario,
Canada. These are laboratory and field results from water samples taken by hand at fixed sites on sampling visits,
as opposed to the continuous sensor readings in the West Campus monthly dataset.

Each file in this dataset is a CSV of sampling results in the project's standard format. The WELL dashboard reads
new files from this dataset and shows the results on its Ancaster Watershed tab.

License: Creative Commons Attribution (CC-BY). You may reuse the data for any purpose as long as you credit the
dataset.

## How to use this dataset (Tree view)

In Borealis, open the **Tree** view to see the uploaded sampling files. Each file is a CSV you can download and
open directly in a spreadsheet or load into any analysis tool. The files share one simple layout, described below,
so a file from any visit reads the same way.

## The file format

Files use a **long** layout: **one reading per row**. A single site visit that measured nine parameters is nine
rows, one per parameter. This keeps every value next to its own unit and quality flags, and lets different visits
record different parameters without reshaping the file.

Files are UTF-8 text, comma separated, with a header row. Column names are not case-sensitive and may appear in any
order.

A step-by-step guide to preparing and checking a file, including an in-browser format checker, is published here:
https://well.mcmaster.ca/sampling-upload-guide-05beeadb/

### Columns

| Column | Required | What it holds |
|---|---|---|
| `date` | yes | Sampling date as `YYYY-MM-DD`, e.g. `2026-05-06`. Only this format is accepted, so there is no day/month ambiguity. |
| `time` | no | Time of sampling in 24-hour `HH:MM`, local Hamilton time (America/Toronto). Empty means the reading is stored at midnight of that date. |
| `site` | yes | One of the sites listed below, by name, number, or both. |
| `parameter` | yes | One of the parameters listed below. |
| `value` | yes | A plain decimal number (scientific notation such as `1.5e-3` is fine), with a `.` for decimals and no thousands separator. See the notes on blanks and the below-detection convention. |
| `unit` | yes | The parameter's expected unit from the table below. A mismatched unit is an error, not converted. |
| `creek` | no | The creek name. If given, it must match the site's creek (a cross-check). |
| `below_detection` | no | `true` if the value is below the detection limit (see below), otherwise `false` or empty. |
| `qc_flag` | no | `ok`, `suspect`, or `rejected` (or empty). `rejected` rows are kept in the file but not imported to the dashboard. |
| `sampler` | no | Who took the sample (initials are fine). |
| `method` | no | Method or instrument used. |
| `notes` | no | Anything else worth recording. |

The dashboard stores the core readings (date, time, site, parameter, value, unit). The extra columns (`creek`,
`below_detection`, `qc_flag`, `sampler`, `method`, `notes`) are carried in the uploaded file, which is the archived
copy of record.

### Sites

| Site number | Name | Creek |
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

There is no site 7. The site names and numbers match the field sheet.

[TODO: add the geospatial coordinates (latitude/longitude) of each sampling site, and set the dataset's geospatial
metadata in the Borealis Metadata tab (a point per site, or a bounding box covering the watershed).]

### Parameters and units

| Parameter | Unit | What it is |
|---|---|---|
| E. coli | CFU/100 mL | Escherichia coli bacteria count. |
| Total coliform | CFU/100 mL | Total coliform bacteria count. |
| Turbidity | NTU | Water cloudiness. |
| pH | pH units | Acidity/alkalinity (0 to 14). |
| Conductivity | µS/cm | Electrical conductivity (`uS/cm` is also accepted). |
| Chloride | mg/L | Dissolved chloride. |
| Total phosphorus | µg/L | Total phosphorus. |
| Soluble reactive phosphorus | µg/L | Dissolved, biologically available phosphorus. |
| Total nitrogen | mg/L | Total nitrogen. |
| Nitrate nitrogen | mg/L | Nitrate as nitrogen. |
| Ammonia nitrogen | mg/L | Ammonia as nitrogen. |

## Blank values: a parameter that was not measured

If a parameter was not measured on a visit, leave the row out, or leave the `value` empty (`NA` and `N/A` mean the
same). Blank readings are skipped, not stored as zero, so a blank never reads as a measured value of zero. Never
write `0` to mean "not measured".

## Below the detection limit

When a result is below the laboratory's detection limit, write the detection limit with a `<` in front of it, for
example `<0.01`. You can also write the limit and set `below_detection` to `true`. The stored value is the detection
limit itself, so it represents an upper bound rather than an exact measurement. Values above an upper reporting
limit (for example `>2420`) should be written as the number with the limit noted in `notes`.

## One value per site, parameter, date and time

Each combination of site, parameter, date, and time holds a single value. For replicate or duplicate samples,
report their mean and say so in `notes` (for example `mean of 3 replicates`). Two samples taken at different times
on the same day are separate readings: give each its own `time`.

## Timestamps and time zone

Sampling times (`time`) are local Hamilton time (America/Toronto), which follows Eastern Standard Time in winter
and Eastern Daylight Time in summer. They are recorded as the local wall-clock time of sampling.

## Credit and contact

Please cite this dataset if you use it. The suggested citation is shown on the dataset's Borealis page.

[TODO: list the dataset authors and their ORCID iDs, covering sample collection, laboratory analysis, and data
processing.]
