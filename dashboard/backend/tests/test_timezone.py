"""Tests for the site-time helpers in utils/timezone.py, around both DST changes of 2026 in Toronto.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.timezone import UTC, as_utc, parse_instant, site_to_utc, site_wall_time  # noqa: E402


def utc(*args):
    return dt.datetime(*args, tzinfo=UTC)


class SiteTime(unittest.TestCase):
    def test_ordinary_times(self):
        self.assertEqual(site_to_utc(dt.datetime(2026, 7, 1, 12)), utc(2026, 7, 1, 16))    # EDT
        self.assertEqual(site_to_utc(dt.datetime(2026, 1, 15, 12)), utc(2026, 1, 15, 17))  # EST
        self.assertEqual(site_wall_time(utc(2026, 7, 1, 16)), dt.datetime(2026, 7, 1, 12))

    def test_the_repeated_fall_back_hour(self):
        wall = dt.datetime(2026, 11, 1, 1, 30)
        self.assertEqual(site_to_utc(wall), utc(2026, 11, 1, 5, 30))           # first: EDT
        self.assertEqual(site_to_utc(wall, fold=1), utc(2026, 11, 1, 6, 30))   # second: EST
        self.assertEqual(site_wall_time(utc(2026, 11, 1, 5, 30)), wall)
        self.assertEqual(site_wall_time(utc(2026, 11, 1, 6, 30)), wall)        # both read 01:30, without an offset

    def test_the_skipped_spring_forward_hour(self):
        # 02:30 doesn't exist on 2026-03-08; like PostgreSQL, it is read with the offset before the change (EST)
        self.assertEqual(site_to_utc(dt.datetime(2026, 3, 8, 2, 30)), utc(2026, 3, 8, 7, 30))
        self.assertEqual(site_wall_time(utc(2026, 3, 8, 7, 30)), dt.datetime(2026, 3, 8, 3, 30))

    def test_as_utc(self):
        est = dt.timezone(dt.timedelta(hours=-5))
        self.assertEqual(as_utc(dt.datetime(2026, 11, 1, 1, 30, tzinfo=est)), utc(2026, 11, 1, 6, 30))
        self.assertIs(as_utc(dt.datetime(2026, 11, 1, 1, 30, tzinfo=est)).tzinfo, UTC)
        self.assertEqual(as_utc(dt.datetime(2026, 11, 1, 0, 30)), utc(2026, 11, 1, 4, 30))   # naive: site wall time


class ParseInstant(unittest.TestCase):
    def test_what_the_dashboard_sends(self):
        self.assertEqual(parse_instant("2026-11-01T04:00:00.000Z"), utc(2026, 11, 1, 4))
        self.assertEqual(parse_instant("2026-11-02T04:59:59.999Z"), utc(2026, 11, 2, 4, 59, 59, 999000))

    def test_offsets_and_naive_times(self):
        self.assertEqual(parse_instant("2026-11-01T01:30:00-05:00"), utc(2026, 11, 1, 6, 30))
        self.assertEqual(parse_instant("2026-11-01T01:30:00"), utc(2026, 11, 1, 5, 30))   # naive: site time, first copy
        self.assertEqual(parse_instant("2026-11-01"), utc(2026, 11, 1, 4))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            parse_instant("yesterday")


if __name__ == "__main__":
    unittest.main()
