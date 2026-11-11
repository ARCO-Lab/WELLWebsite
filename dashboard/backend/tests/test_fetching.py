"""Tests for utils/fetching.py. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import collections
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils import fetching  # noqa: E402

UTC = dt.timezone.utc


def ny():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:
        raise unittest.SkipTest("no time zone database on this machine")


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
    def test_utc_to_stored_local_time(self):
        tz = ny()
        self.assertEqual(fetching.to_local(dt.datetime(2026, 11, 10, 4, tzinfo=UTC), tz), dt.datetime(2026, 11, 9, 23))  # EST
        self.assertEqual(fetching.to_local(dt.datetime(2026, 7, 1, 16, tzinfo=UTC), tz), dt.datetime(2026, 7, 1, 12))    # EDT
        self.assertEqual(fetching.to_local(dt.datetime(2026, 1, 1, 12), tz), dt.datetime(2026, 1, 1, 12))                # naive: unchanged

    def test_start_from_newest_converts_local_to_utc(self):
        # Regression: the stored local time used to be labelled UTC, re-fetching ~5 h every run.
        tz, first = ny(), dt.datetime(2025, 1, 1, tzinfo=UTC)
        self.assertEqual(fetching.start_from_newest(dt.datetime(2026, 11, 9, 23), tz, first),
                         dt.datetime(2026, 11, 10, 3, tzinfo=UTC))   # 23:00 EST = 04:00 UTC, minus 1 h overlap
        self.assertEqual(fetching.start_from_newest(dt.datetime(2026, 7, 1, 12), tz, first),
                         dt.datetime(2026, 7, 1, 15, tzinfo=UTC))    # 12:00 EDT = 16:00 UTC, minus 1 h
        self.assertEqual(fetching.start_from_newest(None, tz, first), first)


if __name__ == "__main__":
    unittest.main()
