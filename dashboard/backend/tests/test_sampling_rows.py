"""Tests for utils/sampling_rows.py (sampling-sheet entries -> database rows). Run from dashboard/backend:
python -m unittest discover -s tests"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.sampling_rows import KEY, entry_to_row, rows_from_entries  # noqa: E402


def entry(site="Falkirk Rd", creek="Tiffany Creek", measurement="E. coli", value=12.0, when="2025-06-01T00:00:00"):
    """An entry shaped like api/services/sampling.py's output."""
    return {"site_id": site, "creek_id": creek, "measurement_type": measurement, "value": value,
            "unit": "CFU/100 mL", "recorded_at": when}


class EntryToRowTests(unittest.TestCase):
    def test_maps_site_creek_and_date(self):
        row = entry_to_row(entry())
        self.assertEqual(row["site_id"], "1")  # stored as text, like the existing rows
        self.assertEqual(row["creek_id"], "20962187")
        self.assertEqual(row["recorded_at"], dt.datetime(2025, 6, 1))
        self.assertEqual(set(KEY) <= set(row), True)

    def test_unknown_names(self):
        row = entry_to_row(entry(site="Mystery Bridge", creek="Some Brook"))
        self.assertEqual(row["site_id"], "7")
        self.assertEqual(row["creek_id"], "00000000")

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            entry_to_row(entry(when="not a date"))


class RowsFromEntriesTests(unittest.TestCase):
    def test_keeps_older_rows_and_other_creeks(self):
        """The old import kept only rows newer than the newest stored row of any creek; nothing here
        filters by date, so backfills and late creeks survive (the database's unique key dedupes)."""
        rows, stats = rows_from_entries([
            entry(when="2025-06-01T00:00:00"),
            entry(site="Maple Lane", creek="Ancaster Creek", when="2024-09-15T00:00:00"),
        ], log=lambda *_: None)
        self.assertEqual(len(rows), 2)
        self.assertEqual(stats["failed"], 0)

    def test_repeated_key_in_file_keeps_the_first(self):
        rows, stats = rows_from_entries([entry(value=1.0), entry(value=2.0), entry(measurement="pH", value=7.1)],
                                        log=lambda *_: None)
        self.assertEqual([r["value"] for r in rows], [1.0, 7.1])
        self.assertEqual(stats["duplicates"], 1)

    def test_counts_failures_and_collects_unknown_sites(self):
        logs = []
        rows, stats = rows_from_entries([entry(when="garbage"), entry(site="Mystery Bridge")], log=logs.append)
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["unknown_sites"], {"Mystery Bridge"})
        self.assertTrue(any("Failed to parse" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
