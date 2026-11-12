"""Tests for utils/sampling_rows.py (how a sampling import compares a file with the stored rows). Run from
dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.sampling_rows import (  # noqa: E402
    KEY, correction_lines, covers, file_scope, held_lines, hold_back, row_key, scope_from_json, scope_json, split_rows,
    withdrawn, withdrawn_lines,
)


def row(site="1", measurement="E. coli", value=12.0, when=dt.datetime(2025, 6, 1), unit="CFU/100 mL"):
    """A row shaped like utils/sampling_csv.py's records."""
    return {"site_id": site, "creek_id": "20962187", "measurement_type": measurement, "value": value,
            "unit": unit, "recorded_at": when}


class SplitRowsTests(unittest.TestCase):
    """A file's rows against the stored ones: new rows are inserted, changed ones are corrections."""

    def setUp(self):
        self.rows = [
            row(value=1.0, when=dt.datetime(2025, 6, 1)),             # new
            row(value=120.0, when=dt.datetime(2025, 7, 1)),           # stored as 1200: a correction
            row(value=5.0, when=dt.datetime(2025, 8, 1, 9, 40)),      # stored with the same value
            row(value=5.0 + 1e-13, when=dt.datetime(2025, 8, 2)),     # the same value up to float round-off
        ]
        keys = [row_key(r) for r in self.rows]
        self.stored = {keys[1]: (1200.0, "CFU/100 mL"), keys[2]: (5.0, "CFU/100 mL"), keys[3]: (5.0, "CFU/100 mL")}

    def test_key_order(self):
        self.assertEqual(KEY, ("site_id", "measurement_type", "recorded_at"))
        self.assertEqual(row_key(self.rows[0]), ("1", "E. coli", dt.datetime(2025, 6, 1)))

    def test_new_rows_and_corrections(self):
        new, corrections = split_rows(self.rows, self.stored)
        self.assertEqual(new, [self.rows[0]])
        self.assertEqual(corrections, [(self.rows[1], 1200.0, "CFU/100 mL")])

    def test_a_changed_unit_or_a_value_now_blank_is_a_correction(self):
        rows = [row(unit="MPN/100 mL"), row(value=None, when=dt.datetime(2025, 6, 2))]
        stored = {row_key(rows[0]): (12.0, "CFU/100 mL"), row_key(rows[1]): (3.0, "CFU/100 mL")}
        self.assertEqual([old for _, old, _ in split_rows(rows, stored)[1]], [12.0, 3.0])

    def test_a_clean_reimport_changes_nothing(self):
        stored = {row_key(r): (r["value"], r["unit"]) for r in self.rows}
        self.assertEqual(split_rows(self.rows, stored), ([], []))

    def test_each_correction_is_logged_with_old_and_new_value(self):
        lines = correction_lines(split_rows(self.rows, self.stored)[1])
        self.assertEqual(lines, ["[CORRECTED] site 1 E. coli on 2025-07-01 00:00: 1200.0 CFU/100 mL -> "
                                 "120.0 CFU/100 mL"])


class HoldBackTests(unittest.TestCase):
    """A file imported after a newer one never undoes the newer file's values."""

    def setUp(self):
        self.inside = row(site="3", when=dt.datetime(2026, 10, 6, 9, 40), value=120.0)
        self.outside = row(site="4", when=dt.datetime(2026, 10, 6, 9, 40), value=7.0)
        self.scope = file_scope([row(site="3", when=dt.datetime(2026, 10, 6, 12))])

    def test_scope_json_round_trip(self):
        text = scope_json(self.scope)
        self.assertEqual(text["start"], "2026-10-06T00:00:00")
        self.assertEqual(scope_from_json(text), self.scope)
        self.assertIsNone(scope_from_json(None))

    def test_covers(self):
        self.assertTrue(covers(self.scope, self.inside))
        self.assertFalse(covers(self.scope, self.outside))
        self.assertFalse(covers(self.scope, row(site="3", when=dt.datetime(2026, 10, 7))))   # the day after
        self.assertTrue(covers(None, self.outside))   # unknown scope: covers everything

    def test_a_newer_file_holds_back_only_what_it_covers(self):
        corrections = [(self.inside, 1200.0, "CFU/100 mL"), (self.outside, 70.0, "CFU/100 mL")]
        apply, held = hold_back(corrections, [("WELLAncasterWatershed_Oct2026.csv (ID: 9)", self.scope)])
        self.assertEqual(apply, [(self.outside, 70.0, "CFU/100 mL")])
        self.assertEqual(held, [(self.inside, 1200.0, "CFU/100 mL", "WELLAncasterWatershed_Oct2026.csv (ID: 9)")])
        self.assertEqual(hold_back(corrections, []), (corrections, []))
        self.assertEqual(hold_back(corrections, [("legacy.csv (ID: 7)", None)])[0], [])
        lines = held_lines(held)
        self.assertIn("[WARN] 1 corrections not applied: a newer file, already imported, covers these readings",
                      lines[0])
        self.assertEqual(lines[1], "[WARN]   site 3 E. coli on 2026-10-06 09:40: stored 1200.0 CFU/100 mL, this "
                                   "file 120.0 CFU/100 mL (newer: WELLAncasterWatershed_Oct2026.csv (ID: 9))")
        self.assertEqual(held_lines([]), [])


class WithdrawnTests(unittest.TestCase):
    """Stored rows a newer file covers but no longer has are reported, never deleted."""

    def setUp(self):
        self.rows = [row(site="1", when=dt.datetime(2026, 10, 6, 9, 40)),
                     row(site="3", measurement="Chloride", when=dt.datetime(2026, 10, 20, 12, 5), unit="mg/L")]

    def test_the_scope_is_the_files_sites_parameters_and_days(self):
        self.assertEqual(file_scope(self.rows), {
            "sites": ["1", "3"], "measurement_types": ["Chloride", "E. coli"],
            "start": dt.datetime(2026, 10, 6), "end": dt.datetime(2026, 10, 21)})
        self.assertIsNone(file_scope([]))

    def test_stored_rows_missing_from_the_file(self):
        stored = [{**row_key_dict(self.rows[0]), "value": 12.0},
                  {"site_id": "3", "measurement_type": "E. coli", "recorded_at": dt.datetime(2026, 10, 20, 12, 5),
                   "value": 1200.0}]
        gone = withdrawn(self.rows, stored)
        self.assertEqual(gone, stored[1:])
        text = "\n".join(withdrawn_lines(gone))
        self.assertIn("[WARN] 1 rows present in the DB but not in the latest file", text)
        self.assertIn("They were kept", text)
        self.assertIn("site 3 E. coli on 2026-10-20 12:05: stored 1200.0", text)
        self.assertIn("DELETE FROM sampling_measurements WHERE site_id = '3' AND measurement_type = 'E. coli' "
                      "AND recorded_at = '2026-10-20 12:05:00';", text)
        self.assertTrue(all(line.startswith("[WARN]") for line in text.splitlines()))
        self.assertEqual(withdrawn_lines([]), [])

    def test_a_long_list_is_cut_but_counted(self):
        stored = [{"site_id": "1", "measurement_type": "E. coli", "recorded_at": dt.datetime(2026, 10, 6, 10, m),
                   "value": 1.0} for m in range(25)]
        lines = withdrawn_lines(withdrawn(self.rows, stored))
        self.assertIn("[WARN] 25 rows present in the DB", lines[0])
        self.assertIn("[WARN]   ... and 5 more", lines)


def row_key_dict(r):
    return {k: r[k] for k in KEY}


if __name__ == "__main__":
    unittest.main()
