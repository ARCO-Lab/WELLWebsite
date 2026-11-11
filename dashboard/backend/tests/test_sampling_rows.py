"""Tests for utils/sampling_rows.py (reports on rows a sampling import skipped). Run from dashboard/backend:
python -m unittest discover -s tests -t ."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.sampling_rows import KEY, check_skipped, classify_skipped, import_warnings, row_key  # noqa: E402


def row(site="1", measurement="E. coli", value=12.0, when=dt.datetime(2025, 6, 1)):
    """A row shaped like utils/sampling_csv.py's records."""
    return {"site_id": site, "creek_id": "20962187", "measurement_type": measurement, "value": value,
            "unit": "CFU/100 mL", "recorded_at": when}


class SkippedRowTests(unittest.TestCase):
    """Rows ON CONFLICT DO NOTHING skipped: a stored reading with a different value is reported, never applied."""

    def setUp(self):
        self.rows = [
            row(value=1.0, when=dt.datetime(2025, 6, 1)),             # new
            row(value=240.0, when=dt.datetime(2025, 7, 1)),           # stored as 2400: a correction
            row(value=5.0, when=dt.datetime(2025, 8, 1, 9, 40)),      # stored with the same value
        ]
        keys = [row_key(r) for r in self.rows]
        self.inserted = {keys[0]}
        self.stored = {keys[1]: 2400.0, keys[2]: 5.0}

    def test_key_order(self):
        self.assertEqual(KEY, ("site_id", "measurement_type", "recorded_at"))
        self.assertEqual(row_key(self.rows[0]), ("1", "E. coli", dt.datetime(2025, 6, 1)))

    def test_classify_skipped(self):
        changed = classify_skipped(self.rows, self.inserted, self.stored)
        self.assertEqual([(r["value"], stored) for r, stored in changed], [(240.0, 2400.0)])

    def test_warnings_say_corrections_are_not_applied(self):
        text = "\n".join(import_warnings(classify_skipped(self.rows, self.inserted, self.stored)))
        self.assertIn("1 rows differ from the stored reading and were NOT applied", text)
        self.assertIn("site 1 E. coli on 2025-07-01 00:00: stored 2400.0, file 240.0", text)
        self.assertIn("DELETE FROM sampling_measurements WHERE site_id = '1' AND measurement_type = 'E. coli' "
                      "AND recorded_at = '2025-07-01 00:00:00';", text)
        self.assertTrue(all(line.startswith("[WARN]") for line in text.splitlines()))

    def test_no_warnings_for_a_clean_reimport(self):
        stored = {row_key(r): r["value"] for r in self.rows}
        self.assertEqual(import_warnings(classify_skipped(self.rows, set(), stored)), [])

    def test_check_skipped_looks_up_only_the_skipped_keys(self):
        asked = []
        changed = check_skipped(self.rows, self.inserted, lambda keys: asked.extend(keys) or self.stored,
                                log=self.fail)
        self.assertEqual(asked, [row_key(r) for r in self.rows[1:]])
        self.assertEqual([r["value"] for r, _ in changed], [240.0])

    def test_check_skipped_failure_only_warns(self):
        """The rows are committed and "Inserted N" printed before this lookup, so it must not raise."""
        def broken(keys):
            raise RuntimeError("permission denied for table sampling_measurements")
        logs = []
        self.assertEqual(check_skipped(self.rows, self.inserted, broken, log=logs.append), [])
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].startswith("[WARN] Could not compare the 2 skipped rows"))
        self.assertIn("permission denied", logs[0])

    def test_nothing_skipped_needs_no_lookup(self):
        keys = {row_key(r) for r in self.rows}
        self.assertEqual(check_skipped(self.rows, keys, self.fail), [])


if __name__ == "__main__":
    unittest.main()
