"""Tests for scripts/licor_backfill.py. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import licor_backfill as bf  # noqa: E402


class Spans(unittest.TestCase):
    def test_runs(self):
        d = dt.date(2026, 1, 1)
        days = [d + dt.timedelta(n) for n in (0, 1, 2, 5, 7, 8)]
        self.assertEqual(bf.spans(days), ["2026-01-01..2026-01-03", "2026-01-08..2026-01-09"])

    def test_empty(self):
        self.assertEqual(bf.spans([]), [])


class Args(unittest.TestCase):
    def test_defaults(self):
        a = bf.parse_args([])
        self.assertEqual((a.check, a.days, a.groups), (False, 364, {"Logger", "Weather"}))

    def test_days_capped_to_licor_limit(self):
        self.assertEqual(bf.parse_args(["--days", "999"]).days, 364)

    def test_bad_group_rejected(self):
        with self.assertRaises(SystemExit):
            bf.parse_args(["--groups", "Quality"])


if __name__ == "__main__":
    unittest.main()
