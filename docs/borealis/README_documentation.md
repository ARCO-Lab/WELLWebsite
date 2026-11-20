# WELL Documentation and Templates

Supporting documents for the WELL (Watershed-Ecosystems: Living Laboratories) datasets from McMaster University,
Hamilton, Ontario, Canada. This dataset holds the files you need to prepare and understand creek sampling data for
the Ancaster Watershed project: a blank CSV template and a format guide.

Use this dataset as the starting point before you upload sampling results to the WELL Ancaster Watershed Sampling
Uploads dataset.

License: Creative Commons Attribution (CC-BY).

## How to use this dataset (Tree view)

In Borealis, open the **Tree** view to see the files. Download the template, fill it in with your results, and
check it against the format guide before uploading it to the sampling dataset.

## What is in this dataset

### Sampling CSV template

A blank CSV with the correct header row and a few example rows, ready to fill in. It uses the standard long layout
(one reading per row) that the WELL dashboard imports. Open it in a spreadsheet, keep the header row as it is, and
replace the example rows with your own readings. When you save, use CSV UTF-8 (comma delimited) so the text and
units are preserved.

The example rows show the common cases: an ordinary reading, a below-detection reading written with a `<`, and a
reading with optional fields filled in.

### Format guide

A plain-language guide to the sampling CSV format. It explains:

- the columns, which are required, and what each one holds;
- the list of sampling sites and their creeks;
- the list of parameters and the unit each one must use;
- how to record a parameter that was not measured (blank values);
- how to record a result below the detection limit (the `<` convention);
- the rule of one value per site, parameter, date, and time, and how to handle replicates;
- the date and time formats, and the time zone (local Hamilton time, America/Toronto).

The same guide is published as a help page for researchers, with an in-browser format checker, here:
https://well.mcmaster.ca/sampling-upload-guide-05beeadb/

## How the pieces fit together

1. Download the **template** from this dataset.
2. Fill it in with your sampling results, following the **format guide**.
3. Check the file using the format checker on the guide page (it finds every problem at once and lists each by row
   number).
4. Upload the corrected file to the **WELL Ancaster Watershed Sampling Uploads** dataset.

A file that does not pass the checks is not imported, so checking first saves a round trip.

## Credit and contact

Please cite this dataset if you use it. The suggested citation is shown on the dataset's Borealis page.

[TODO: list the dataset authors and their ORCID iDs for the people who prepared the template and format guide.]
