"""Tests for utils/sampling_rows.py (sampling-sheet entries -> database rows). Run from dashboard/backend:
python -m unittest discover -s tests"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.sampling_rows import (KEY, classify_skipped, entry_to_row, import_warnings, row_key,  # noqa: E402
                                 rows_from_entries)


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

    def test_different_names_mapping_to_one_site_are_reported_as_collisions(self):
        rows, stats = rows_from_entries([entry(site="Mystery Bridge"), entry(site="Other Lane"),
                                         entry(site="Mystery Bridge")], log=lambda *_: None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["duplicates"], 1)  # the same name again
        self.assertEqual([c[:2] for c in stats["collisions"]], [("Mystery Bridge", "Other Lane")])
        self.assertEqual(stats["unknown_sites"], {"Mystery Bridge"})  # only names whose rows were kept

    def test_counts_failures_and_collects_unknown_sites(self):
        logs = []
        rows, stats = rows_from_entries([entry(when="garbage"), entry(site="Mystery Bridge")], log=logs.append)
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["unknown_sites"], {"Mystery Bridge"})
        self.assertTrue(any("Failed to parse" in line for line in logs))

    def test_repeat_with_a_different_value_is_reported(self):
        rows, stats = rows_from_entries([entry(value=2400.0), entry(value=240.0), entry(value=2400.0)],
                                        log=lambda *_: None)
        self.assertEqual([r["value"] for r in rows], [2400.0])
        self.assertEqual(stats["duplicates"], 2)
        self.assertEqual([(r[0], r[3], r[4]) for r in stats["differing_repeats"]], [("Falkirk Rd", 2400.0, 240.0)])


class SkippedRowTests(unittest.TestCase):
    """Rows ON CONFLICT DO NOTHING skipped: corrected readings and clashes on site 7 are reported."""

    def setUp(self):
        self.rows, _ = rows_from_entries([
            entry(value=1.0, when="2025-06-01T00:00:00"),               # new
            entry(value=240.0, when="2025-07-01T00:00:00"),             # stored as 2400: a correction
            entry(value=5.0, when="2025-08-01T00:00:00"),               # stored with the same value
            entry(site="Other Lane", value=9.0, when="2025-06-01T00:00:00"),  # site 7 already has this key
        ], log=lambda *_: None)
        keys = [row_key(r) for r in self.rows]
        self.inserted = {keys[0]}
        self.stored = {keys[1]: 2400.0, keys[2]: 5.0, keys[3]: 3.0}

    def test_classify_skipped(self):
        changed, unknown = classify_skipped(self.rows, self.inserted, self.stored)
        self.assertEqual([(r["value"], stored) for r, stored in changed], [(240.0, 2400.0)])
        self.assertEqual([(r["value"], stored) for r, stored in unknown], [(9.0, 3.0)])

    def test_warnings_say_corrections_are_not_applied_and_how_to_fix_site_7(self):
        _, stats = rows_from_entries([entry(site="Other Lane")], log=lambda *_: None)
        changed, unknown = classify_skipped(self.rows, self.inserted, self.stored)
        text = "\n".join(import_warnings(stats, changed, unknown))
        self.assertIn("1 rows differ from the stored reading and were NOT applied", text)
        self.assertIn("stored 2400.0, file 240.0", text)
        self.assertIn("DELETE FROM sampling_measurements WHERE site_id = '1' AND measurement_type = 'E. coli' "
                      "AND recorded_at = '2025-07-01 00:00:00';", text)
        self.assertIn("1 rows of unlisted sites were not imported", text)
        self.assertIn("may be from a different unlisted site", text)
        self.assertIn("site_id = '7'", text)
        self.assertTrue(all(line.startswith("[WARN]") for line in text.splitlines()))

    def test_no_warnings_for_a_clean_reimport(self):
        rows, stats = rows_from_entries([entry(), entry(measurement="pH", value=7.1)], log=lambda *_: None)
        stored = {row_key(r): r["value"] for r in rows}
        changed, unknown = classify_skipped(rows, set(), stored)
        self.assertEqual(import_warnings(stats, changed, unknown), [])

    def test_site_7_examples_list_differing_readings_first(self):
        rows, stats = rows_from_entries([entry(site="Other Lane", when=f"2025-0{m}-01T00:00:00", value=float(m))
                                         for m in range(1, 8)], log=lambda *_: None)
        stored = {row_key(r): r["value"] for r in rows}
        stored[row_key(rows[-1])] = 99.0  # only the last one differs
        _, unknown = classify_skipped(rows, set(), stored)
        lines = import_warnings(stats, (), unknown)
        self.assertIn("7 rows of unlisted sites were not imported", lines[1])
        self.assertIn("(1 with a different value)", lines[1])
        self.assertEqual(lines[2], "[WARN]   E. coli on 2025-07-01: stored 99.0, file 7.0")
        self.assertEqual(len(lines), 2 + 5)

    def test_collision_warning_says_to_delete_site_7_rows_before_reimporting(self):
        _, stats = rows_from_entries([entry(site="Mystery Bridge"), entry(site="Other Lane")], log=lambda *_: None)
        text = "\n".join(import_warnings(stats))
        self.assertIn("kept 'Mystery Bridge', dropped 'Other Lane'", text)
        self.assertIn("delete the rows already stored under the shared site id (site_id = '7'", text)


if __name__ == "__main__":
    unittest.main()
