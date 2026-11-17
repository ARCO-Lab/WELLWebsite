# WELL West Campus Monthly Data

Continuous environmental monitoring data from the WELL (Watershed-Ecosystems: Living Laboratories) site at
McMaster University's West Campus, in the Ancaster Creek sub-watershed, Hamilton, Ontario, Canada.

This dataset holds the readings from a cluster of instruments at the West Campus site: one weather station, one
multi-parameter water quality sonde, and five water level loggers along the creek. Readings are taken roughly
every 10 minutes and published here as one CSV file per calendar month. Each monthly file is a self-contained
snapshot of that month's readings, so you can download only the months you need.

License: Creative Commons Attribution (CC-BY). You may reuse the data for any purpose as long as you credit the
dataset.

## How to use this dataset (Tree view)

In Borealis, open the **Tree** view (the file listing) to browse the monthly files. Each file is named for the
month it covers, for example `WELLWestCampus_Jul2025.csv`. Download the month or months you want. You do not need
the whole dataset to work with a single month. If you are scripting a download, the file names sort in a readable
way and each file stands on its own.

## What a file contains

Each row is one timestamp (one ~10 minute interval). The columns are grouped by instrument. Reading left to right,
a file has:

1. `ID` and `Timestamp` (see the time zone note below).
2. A **Weather** section: the weather station's readings.
3. A **Quality** section: the water quality sonde's readings.
4. A **Logger** section: the five water level loggers, one after another.

A blank spacer column separates each section from the next, so the sections are easy to see when the file is open
in a spreadsheet.

### Column layout, left to right

| Column(s) | Meaning |
|---|---|
| `ID` | A simple row counter (1, 2, 3, ...) within the file. Not a sensor value. |
| `Timestamp` | The date and time of the reading (see time zone below). |
| `Group` = `Weather` | Marks the start of the weather station section. |
| `Latitude`, `Longitude` | The weather station's location. |
| weather variables | One column per weather variable, headed `Name: unit` (see variables below). |
| (blank spacer) | Separates Weather from Quality. |
| `Group` = `Quality` | Marks the start of the water quality sonde section. |
| `Latitude`, `Longitude` | The water quality sonde's location. |
| quality variables | One column per sonde parameter, headed `Name: unit`. |
| (blank spacer) | Separates Quality from Logger. |
| `Group` = `Logger` | Marks the start of the water level logger section. |
| `Sensor` = `Logger 1` | Names the first logger. |
| `Latitude`, `Longitude` | Logger 1's location. |
| Logger 1 variables | Logger 1's readings. |
| `Sensor` = `Logger 2` | Names the second logger. |
| `Latitude`, `Longitude` | Logger 2's location. |
| Logger 2 variables | Logger 2's readings. |
| ... | ... and so on through `Logger 5`. |

### About the multiple Latitude / Longitude columns

A reviewer noticed that each row has several Latitude and Longitude columns, spread out between the other
variables. Here is why, and how to read them.

Every instrument sits in a slightly different spot at the West Campus site, so every instrument carries its own
coordinates. **Each Latitude / Longitude pair belongs to the group or sensor label immediately to its left.** In
other words:

- The Latitude / Longitude right after `Group` = `Weather` are the **weather station's** coordinates.
- The Latitude / Longitude right after `Group` = `Quality` are the **water quality sonde's** coordinates.
- In the Logger section, each logger is introduced by its own `Sensor` label (`Logger 1` ... `Logger 5`), and the
  Latitude / Longitude right after each `Sensor` label are **that logger's** coordinates.

So if you see coordinates part way across a row, look left to the nearest `Group` or `Sensor` label to find which
instrument they describe. The coordinates repeat on every row because every row carries the full set of
instruments.

[TODO: confirm the published site coordinates. The CSV embeds a latitude/longitude for each instrument. Please
confirm these are the coordinates you want released, and set the dataset's geospatial metadata (the West Campus
site location, or a bounding box covering all instruments) in the Borealis Metadata tab.]

## The variables

Column headers for the variables are written as `Name: unit`, for example `Air Temperature: °C`.

### Weather station

The weather station reports air and soil conditions. Confirmed variables:

| Variable | Unit | What it is |
|---|---|---|
| Air Temperature | °C | Air temperature above the ground. |
| Relative Humidity | % | Relative humidity of the air. |
| Soil Temperature | °C | Temperature of a probe in the soil. |

[TODO: confirm the full list of weather station channels. The station may also report other channels (for example
rainfall, wind, or solar radiation) under the station vendor's own names and units. List the make and model of the
weather station, and confirm every channel and unit you want described here.]

### Water quality sonde

A sonde is a multi-parameter water quality probe: a single instrument lowered into the water that measures several
properties at once and reports them together on each reading. The West Campus sonde reports these parameters:

| Variable | Unit | What it is |
|---|---|---|
| Water Temperature | °C | Temperature of the water. |
| Conductivity | uS/cm | Electrical conductivity (microsiemens per centimetre); rises with dissolved ions. |
| Salinity | PPT | Salinity, in parts per thousand. |
| TDS | g/L | Total dissolved solids. |
| ODO | mg/L | Optical dissolved oxygen, the concentration of oxygen in the water. |
| ODOSat | % | Dissolved oxygen as a percentage of saturation. |
| Turbidity | NTU | Water cloudiness (nephelometric turbidity units). |
| TSS | mg/L | Total suspended solids. |

[TODO: fill in the exact make and model of the water quality sonde.]

### Water level loggers (Logger 1 to Logger 5)

Five pressure/temperature loggers are placed along the creek. Each reports:

| Variable | Unit | What it is |
|---|---|---|
| Water Surface Elevation | m asl | Height of the water surface in metres above sea level, computed from the logger's measured depth and its surveyed installation values. |
| Water Temperature | °C | Temperature of the water at the logger. |

## Timestamps and time zone

- Timestamps are **local Hamilton time (America/Toronto)**, which follows Eastern Standard Time in winter and
  Eastern Daylight Time in summer. They are written as local wall-clock time with no zone offset or `Z` suffix, so
  read them as the time a clock in Hamilton showed.
- During the autumn switch back from daylight time, the repeated hour (for example 01:00 to 02:00 on the changeover
  night) is stored as written, without a marker for which pass it was.
- Readings are taken at roughly 10 minute intervals. The exact spacing can vary slightly between instruments, and
  gaps occur when an instrument is offline.

## Blank cells

A blank cell means **no reading was stored for that instrument and variable at that timestamp**. Blanks are left
empty on purpose rather than filled with a zero, so a blank is never a measured value of zero.

A blank can happen when:

- the instrument was offline or not reporting at that timestamp, or
- that timestamp has a reading from one instrument but not from another (the instruments do not always report on
  exactly the same clock), or
- the variable is one the instrument on that row does not report.

[TODO: confirm this reading of blank cells, and add any site-specific reason you want researchers to know about
(for example planned maintenance windows, or a known outage period).]

## Credit and contact

Please cite this dataset if you use it. The suggested citation is shown on the dataset's Borealis page.

[TODO: list the dataset authors and their ORCID iDs. Include the people responsible for data collection, data
processing, and analysis.]
