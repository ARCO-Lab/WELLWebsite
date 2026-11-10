"""Tests for scripts/wqdata_backfill.py (no network, no database).
Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import pathlib
import sys
import traceback
import unittest

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import wqdata_backfill as bf  # noqa: E402
from utils.parsers import quality_rows  # noqa: E402

UTC = dt.timezone.utc
KEY = "SECRET-KEY-123"


def toronto():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Toronto")
    except Exception:
        raise unittest.SkipTest("no time zone database on this machine")


def point(ts, *params):
    return {"timestamp": ts, "values": [{"parameterId": p, "value": "1.5"} for p in params]}


class Response:
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body

    def json(self):
        if self.body is None:
            raise requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
        return self.body


def fake_get(*outcomes):
    """A stand-in for requests.get that returns (or raises) the given outcomes in turn."""
    calls = []

    def get(url, params=None, timeout=None):
        calls.append(params)
        out = outcomes[len(calls) - 1]
        if isinstance(out, Exception):
            raise out
        return out
    return get, calls


def client(*outcomes):
    get, calls = fake_get(*outcomes)
    sleeps = []
    return bf.WQData("https://wqdata.example/api", KEY, "4501", get=get, sleep=sleeps.append), calls, sleeps


class Requests(unittest.TestCase):
    def assert_no_key(self, err):
        text = str(err) + "".join(traceback.format_exception(type(err), err, err.__traceback__))
        self.assertNotIn(KEY, text)

    def test_ok_and_paced(self):
        wq, calls, sleeps = client(Response(200, {"data": []}), Response(200, {"data": [1]}))
        self.assertEqual(wq.get_page("2026-11-09 05:00:00", "2026-11-10 04:59:59"), {"data": []})
        self.assertEqual(wq.get_page("a", "b"), {"data": [1]})
        self.assertEqual(calls[0], {"apiKey": KEY, "from": "2026-11-09 05:00:00", "to": "2026-11-10 04:59:59"})
        self.assertEqual(sleeps, [bf.PAUSE])   # requests are paced; no wait before the first

    def test_network_error_never_shows_the_key(self):
        # requests puts the full URL, apiKey included, in its exception messages.
        err = requests.ConnectionError(f"Max retries exceeded with url: /devices/4501/parameters/data?apiKey={KEY}")
        wq, calls, _ = client(*[err] * bf.ATTEMPTS)
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assertIn("ConnectionError", str(cm.exception))
        self.assertEqual(len(calls), bf.ATTEMPTS)
        self.assert_no_key(cm.exception)

    def test_throttled_then_ok_is_retried(self):
        wq, calls, sleeps = client(Response(429), Response(200, {"data": []}))
        self.assertEqual(wq.get_page("a", "b"), {"data": []})
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [10, bf.PAUSE])   # back off, then the usual pause

    def test_client_error_fails_at_once_with_status_only(self):
        wq, calls, _ = client(Response(401, {"error": "bad key"}))
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assertIn("HTTP 401", str(cm.exception))
        self.assertEqual(len(calls), 1)
        self.assert_no_key(cm.exception)

    def test_non_json_response(self):
        wq, _, _ = client(Response(200, None))
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assert_no_key(cm.exception)


class Paging(unittest.TestCase):
    start, end = dt.datetime(2026, 11, 9, 5, tzinfo=UTC), dt.datetime(2026, 11, 10, 5, tzinfo=UTC)

    def test_one_page(self):
        calls = []

        def get_page(frm, to):
            calls.append((frm, to))
            return {"data": [point("2026-11-09 05:00:00", 125001)], "info": {"more": False}}
        self.assertEqual(len(bf.fetch_points(get_page, self.start, self.end)), 1)
        self.assertEqual(calls, [("2026-11-09 05:00:00", "2026-11-10 04:59:59")])   # `to` stops before the next day

    def test_follows_more_from_the_last_point(self):
        pages = {"2026-11-09 05:00:00": {"data": [point("2026-11-09 05:00:00", 125001), point("2026-11-09 05:10:00", 125001)],
                                         "info": {"more": True, "lastDataPointTimestamp": "2026-11-09 05:10:00"}},
                 "2026-11-09 05:10:00": {"data": [point("2026-11-09 05:10:00", 125001, 125002), point("2026-11-09 05:20:00", 125001)],
                                         "info": {"more": False, "lastDataPointTimestamp": "2026-11-09 05:20:00"}}}
        calls = []

        def get_page(frm, to):
            calls.append(frm)
            return pages[frm]
        points = bf.fetch_points(get_page, self.start, self.end)
        self.assertEqual(calls, ["2026-11-09 05:00:00", "2026-11-09 05:10:00"])
        # The point split across the pages is read whole; the repeat merges into one row per key.
        rows = quality_rows(points, "4501", UTC)
        self.assertEqual(len(rows), 4)

    def test_paging_that_doesnt_advance_stops(self):
        def get_page(frm, to):
            return {"data": [], "info": {"more": True, "lastDataPointTimestamp": frm}}
        with self.assertRaises(bf.WQDataError):
            bf.fetch_points(get_page, self.start, self.end)


class Days(unittest.TestCase):
    def test_local_days_ending_at_end(self):
        tz = toronto()
        end = dt.datetime(2026, 11, 10, 18, 5, tzinfo=UTC)   # 13:05 EST
        self.assertEqual(bf.day_windows(end, 3, tz), [
            (dt.date(2026, 11, 8), dt.datetime(2026, 11, 8), dt.datetime(2026, 11, 9)),
            (dt.date(2026, 11, 9), dt.datetime(2026, 11, 9), dt.datetime(2026, 11, 10)),
            (dt.date(2026, 11, 10), dt.datetime(2026, 11, 10), dt.datetime(2026, 11, 10, 13, 5)),
        ])

    def test_end_at_midnight_closes_the_day_before(self):
        tz = toronto()
        end = dt.datetime(2026, 11, 10, 5, tzinfo=UTC)   # midnight EST
        self.assertEqual(bf.day_windows(end, 1, tz), [(dt.date(2026, 11, 9), dt.datetime(2026, 11, 9), dt.datetime(2026, 11, 10))])

    def test_day_clocks_go_back_is_25_hours_of_utc(self):
        tz = toronto()
        (day, lo, hi), = [w for w in bf.day_windows(dt.datetime(2026, 11, 3, tzinfo=UTC), 5, tz) if w[0] == dt.date(2026, 11, 1)]
        self.assertEqual((bf.to_utc(lo, tz), bf.to_utc(hi, tz)),
                         (dt.datetime(2026, 11, 1, 4, tzinfo=UTC), dt.datetime(2026, 11, 2, 5, tzinfo=UTC)))


class Compare(unittest.TestCase):
    def test_missing_extra_and_changed_values(self):
        tz = toronto()
        points = [point("2026-11-09 05:00:00", 125001, 125002),
                  point("2026-11-09 05:10:00", 115219),            # power only: never stored, so never missing
                  point("2026-11-09 05:20:00", 125001)]
        rows = quality_rows(points, "4501", tz)
        stored = {("4501", "Water Temperature", dt.datetime(2026, 11, 9, 0, 0)): 1.5,
                  ("4501", "Conductivity", dt.datetime(2026, 11, 9, 0, 0)): 9.0,         # value differs
                  ("4501", "Water Temperature", dt.datetime(2026, 11, 8, 23, 50)): 1.0}  # not at WQData
        missing, extra, differ = bf.compare(rows, stored)
        self.assertEqual([(r["measurement_type"], r["recorded_at"], r["value"], r["unit"]) for r in missing],
                         [("Water Temperature", dt.datetime(2026, 11, 9, 0, 20), 1.5, "°C")])
        self.assertEqual((extra, differ), (1, 1))

    def test_same_value(self):
        self.assertTrue(bf.same_value(float("nan"), float("nan")))
        self.assertTrue(bf.same_value(None, None))
        self.assertFalse(bf.same_value(None, 0.0))
        self.assertFalse(bf.same_value(1.0, 1.001))


class Args(unittest.TestCase):
    def test_defaults(self):
        a = bf.parse_args([])
        self.assertEqual((a.check, a.days), (False, 14))

    def test_check_and_days(self):
        a = bf.parse_args(["--check", "--days", "31"])
        self.assertEqual((a.check, a.days), (True, 31))

    def test_days_must_be_positive(self):
        with self.assertRaises(SystemExit):
            bf.parse_args(["--days", "0"])


if __name__ == "__main__":
    unittest.main()
