"""Tests for utils/fetching.py. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import collections
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils import fetching  # noqa: E402

UTC = dt.timezone.utc


def fake_api(cap_over=dt.timedelta(days=3), step=dt.timedelta(minutes=10)):
    """A stand-in for LI-COR: one record per `step`, capped (like LI-COR at 100k) when the window is longer than `cap_over`."""
    calls = []

    def get_page(start, end):
        calls.append((start, end))
        if end - start > cap_over:
            return [{"partial": True}], True
        recs, t = [], start
        while t < end:
            recs.append({"timestamp": t})
            t += step
        return recs, False
    return get_page, calls


class FetchWindow(unittest.TestCase):
    start = dt.datetime(2026, 1, 1, tzinfo=UTC)

    def test_uncapped_window_is_one_call(self):
        get_page, calls = fake_api()
        recs = fetching.fetch_window(get_page, self.start, self.start + dt.timedelta(days=1))
        self.assertEqual((len(calls), len(recs)), (1, 144))

    def test_capped_window_is_split_until_complete(self):
        get_page, _ = fake_api(cap_over=dt.timedelta(days=3))
        stats = collections.Counter()
        recs = fetching.fetch_window(get_page, self.start, self.start + dt.timedelta(days=30), stats)
        self.assertEqual(len(recs), 30 * 144)                                # nothing lost
        self.assertEqual(len({r["timestamp"] for r in recs}), 30 * 144)      # nothing duplicated
        self.assertFalse(any(r.get("partial") for r in recs))                # truncated pages discarded
        self.assertGreater(stats["split"], 0)

    def test_capped_tiny_window_raises(self):
        get_page, _ = fake_api(cap_over=dt.timedelta(minutes=1))
        with self.assertRaises(RuntimeError):
            fetching.fetch_window(get_page, self.start, self.start + dt.timedelta(days=1))

    def test_fetch_range_never_asks_for_more_than_a_window(self):
        get_page, calls = fake_api(cap_over=dt.timedelta(days=30))
        recs = fetching.fetch_range(get_page, self.start, self.start + dt.timedelta(days=20))
        self.assertEqual(len(recs), 20 * 144)
        self.assertTrue(all(b - a <= fetching.WINDOW for a, b in calls))


class Windows(unittest.TestCase):
    def test_contiguous_and_bounded(self):
        start, end = dt.datetime(2025, 11, 12, tzinfo=UTC), dt.datetime(2026, 11, 10, 5, tzinfo=UTC)
        ws = list(fetching.windows(start, end))
        self.assertEqual((ws[0][0], ws[-1][1]), (start, end))
        self.assertTrue(all(a[1] == b[0] for a, b in zip(ws, ws[1:])))
        self.assertTrue(all(w1 - w0 <= fetching.WINDOW for w0, w1 in ws))

    def test_empty_range(self):
        t = dt.datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(list(fetching.windows(t, t)), [])


class Times(unittest.TestCase):
    def test_start_from_newest_is_the_stored_instant_minus_the_overlap(self):
        first = dt.datetime(2025, 1, 1, tzinfo=UTC)
        newest = dt.datetime(2026, 11, 10, 4, tzinfo=UTC)
        self.assertEqual(fetching.start_from_newest(newest, first), dt.datetime(2026, 11, 10, 3, tzinfo=UTC))
        # psycopg2 returns timestamptz in the session's zone: the same instant, whatever its offset
        same = newest.astimezone(dt.timezone(dt.timedelta(hours=-5)))
        self.assertEqual(fetching.start_from_newest(same, first), dt.datetime(2026, 11, 10, 3, tzinfo=UTC))
        self.assertEqual(fetching.start_from_newest(None, first), first)

    def test_start_from_newest_in_the_repeated_hour(self):
        # 06:30Z is 01:30 EST, the second 01:30 of 2026-11-01. As naive wall time it read as 05:30Z, an hour early.
        newest = dt.datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
        self.assertEqual(fetching.start_from_newest(newest, newest), dt.datetime(2026, 11, 1, 5, 30, tzinfo=UTC))

if __name__ == "__main__":
    unittest.main()
