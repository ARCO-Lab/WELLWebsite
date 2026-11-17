# Borealis dataset descriptions

Short description paragraphs for the Borealis **Metadata** tab, one per dataset. Each is written to stand on its
own on the dataset's landing page. Paste the matching paragraph into the dataset's Description field.

All three datasets are licensed Creative Commons Attribution (CC-BY).

---

## WELL West Campus Monthly Data

Continuous environmental monitoring data from the WELL (Watershed-Ecosystems: Living Laboratories) site at
McMaster University's West Campus, in the Ancaster Creek sub-watershed in Hamilton, Ontario, Canada. A cluster of
instruments at the site records readings roughly every 10 minutes: a weather station (air and soil conditions), a
multi-parameter water quality sonde (temperature, dissolved oxygen, conductivity, salinity, total dissolved solids,
turbidity, and total suspended solids), and five water level loggers along the creek (water surface elevation and
water temperature). The data is published as one CSV file per calendar month, with timestamps in local Hamilton
time (America/Toronto). Each file carries the coordinates of each instrument alongside its readings. See the
dataset README for the full column layout and how to read it.

---

## WELL Ancaster Watershed Sampling Uploads

Grab sampling results from creeks in the Ancaster Creek watershed near McMaster University in Hamilton, Ontario,
Canada. These are laboratory and field results from water samples taken by hand at fixed monitoring sites,
covering bacteria (E. coli and total coliform), nutrients (nitrogen and phosphorus forms), chloride, and physical
measures such as turbidity, conductivity, and pH. Files use a standard long-format CSV (one reading per row) so
that each value is stored with its own unit and quality information. The dataset README describes the sites, the
parameters and their units, and the conventions for blank and below-detection values.

---

## WELL Documentation and Templates

Supporting documents for the WELL Ancaster Watershed sampling data from McMaster University in Hamilton, Ontario,
Canada: a blank CSV template and a plain-language format guide. Together they let anyone prepare a sampling results
file in the standard long format that the WELL project accepts, with the correct columns, sites, parameters, and
units, and the conventions for recording blanks and below-detection results. Use these files before uploading
results to the WELL Ancaster Watershed Sampling Uploads dataset.

---

## Placeholders to complete before publishing

Before finalizing each dataset's metadata in Borealis, fill in:

- Dataset authors and their ORCID iDs (data collection, processing, and analysis contributors).
- Geospatial coordinates: the West Campus instrument site, and each Ancaster Creek sampling site.
- The exact make and model of the water quality sonde (West Campus dataset).
- Confirmation of the blank-value meaning described in the West Campus README.
