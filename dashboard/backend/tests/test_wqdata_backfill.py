"""Tests for scripts/wqdata_backfill.py (no network, no database).
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import pathlib
import sys
import traceback
import unittest
import unittest.mock

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

    def test_server_error_then_ok_is_retried(self):
        wq, calls, sleeps = client(Response(503), Response(200, {"data": []}))
        self.assertEqual(wq.get_page("a", "b"), {"data": []})
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [10, bf.PAUSE])   # back off, then the usual pause

    def test_quota_used_up_stops_at_once(self):
        # A 429 means the hourly quota (shared with the ingestion) is used up: retrying would spend more of it.
        wq, calls, sleeps = client(Response(429, {"message": "Request exceeds hourly limit"}), Response(200, {"data": []}))
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assertEqual((len(calls), sleeps), (1, []))
        self.assertIn("hourly request limit is used up", str(cm.exception))

    def test_timeout_is_retried(self):
        wq, calls, _ = client(requests.Timeout(f"read timed out: ?apiKey={KEY}"), Response(200, {"data": []}))
        self.assertEqual(wq.get_page("a", "b"), {"data": []})
        self.assertEqual(len(calls), 2)

    def test_other_request_errors_fail_at_once(self):
        wq, calls, _ = client(requests.exceptions.InvalidURL(f"bad url ?apiKey={KEY}"))
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assertIn("InvalidURL", str(cm.exception))
        self.assertEqual(len(calls), 1)
        self.assert_no_key(cm.exception)

    def test_client_error_fails_at_once_with_status_only(self):
        wq, calls, _ = client(Response(401, {"error": "bad key"}))
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assertIn("HTTP 401", str(cm.exception))
        self.assertEqual(len(calls), 1)
        self.assert_no_key(cm.exception)

    def test_wqdata_message_is_shown_without_the_key(self):
        quota = Response(429, {"message": f"Request exceeds hourly limit for {KEY}"})
        wq, calls, _ = client(quota)
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        self.assertIn("HTTP 429 (Request exceeds hourly limit for ***)", str(cm.exception))
        self.assert_no_key(cm.exception)

    def test_key_across_the_200_character_cut_is_scrubbed_whole(self):
        # Shortening first would keep the key's first characters, then no longer match it to scrub it.
        wq, _, _ = client(Response(401, {"message": "x" * 195 + KEY + " and more"}))
        with self.assertRaises(bf.WQDataError) as cm:
            wq.get_page("a", "b")
        text = str(cm.exception)
        self.assertIn("(" + "x" * 195 + "*** a)", text)   # scrubbed, then cut to 200 characters
        self.assertNotIn(KEY[:4], text)
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

    def test_more_false_with_values_left_keeps_paging(self):
        # Seen live: a long request's last page said more=false although count < total.
        pages = {"2026-11-09 05:00:00": {"data": [point("2026-11-09 05:00:00", 125001), point("2026-11-09 05:10:00", 125001)],
                                         "info": {"more": False, "count": 2, "total": 3, "lastDataPointTimestamp": "2026-11-09 05:10:00"}},
                 "2026-11-09 05:10:00": {"data": [point("2026-11-09 05:10:00", 125001), point("2026-11-09 05:20:00", 125001)],
                                         "info": {"more": False, "count": 2, "total": 2, "lastDataPointTimestamp": "2026-11-09 05:20:00"}}}
        calls = []

        def get_page(frm, to):
            calls.append(frm)
            return pages[frm]
        points = bf.fetch_points(get_page, self.start, self.end)
        self.assertEqual(calls, ["2026-11-09 05:00:00", "2026-11-09 05:10:00"])
        self.assertEqual(len(quality_rows(points, "4501", UTC)), 3)

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


class FallBackHour(unittest.TestCase):
    def test_repeated_hour_shares_keys_with_the_first(self):
        # 2026-11-01 05:00-06:00Z is 01:00-02:00 EDT and 06:00-07:00Z is 01:00-02:00 EST again: the naive
        # stored times repeat, so the second hour merges into the first (its reading kept), as in the table.
        tz = toronto()
        points = [{"timestamp": ts, "values": [{"parameterId": 125001, "value": v}]}
                  for ts, v in (("2026-11-01 05:00:00", "1"), ("2026-11-01 05:30:00", "2"),
                                ("2026-11-01 06:00:00", "3"), ("2026-11-01 06:30:00", "4"))]
        rows = quality_rows(points, "4501", tz)
        self.assertEqual({k[2]: r["value"] for k, r in rows.items()},
                         {dt.datetime(2026, 11, 1, 1, 0): 1.0, dt.datetime(2026, 11, 1, 1, 30): 2.0})
        missing, extra, differ = bf.compare(rows, {k: r["value"] for k, r in rows.items()})
        self.assertEqual((missing, extra, differ), ([], 0, 0))   # the repeat isn't reported missing


class Backfill(unittest.TestCase):
    """backfill() with stand-ins for WQData and the database."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.ids_path = pathlib.Path(self.dir.name) / "wqdata-backfill-test.ids"
        self.ids_path.touch()   # main() creates it up front
        self.tz = toronto()
        self.days = bf.day_windows(dt.datetime(2026, 11, 11, 5, tzinfo=UTC), 2, self.tz)   # Nov 9 and 10, local
        self.log = []

    def tearDown(self):
        self.dir.cleanup()

    def run_backfill(self, check=False, fail_on_day=None, stored=None, window=bf.WINDOW_DAYS):
        events, next_id, self.requests = [], iter(range(100, 200)), []

        def get_page(frm, to):   # one point per day at 05:00Z (local midnight in EST), two stored parameters each
            self.requests.append((frm, to))
            if fail_on_day and frm.startswith(fail_on_day):
                raise bf.WQDataError("WQData request for ... failed: HTTP 503")
            t, end, data = dt.datetime.fromisoformat(frm), dt.datetime.fromisoformat(to), []
            while t <= end:
                if t.hour == 5 and t.minute == 0:
                    data.append(point(t.strftime("%Y-%m-%d %H:%M:%S"), 125001, 125002))
                t += dt.timedelta(hours=1)
            return {"data": data, "info": {"more": False}}

        def insert_rows(rows, record_ids):
            ids = [next(next_id) for _ in rows]
            record_ids(ids)
            events.append(("commit", self.ids_path.read_text().split()))   # the file's ids at commit time
            return ids
        code = bf.backfill(self.days, self.tz, "4501", get_page, lambda lo, hi: dict(stored or {}),
                           insert_rows, self.ids_path, check, log=self.log.append, window=window)
        return code, events

    def test_days_are_read_a_window_at_a_time_and_compared_per_day(self):
        self.days = bf.day_windows(dt.datetime(2026, 11, 20, 5, tzinfo=UTC), 9, self.tz)   # Nov 11-19, local
        from utils import parsers

        class Later(dt.datetime):   # read as if after Nov 19: points dated in the future are skipped
            @classmethod
            def now(cls, tz=None):
                return dt.datetime(2026, 12, 1, tzinfo=tz)
        with unittest.mock.patch.object(parsers, "datetime", Later):
            code, events = self.run_backfill()
        self.assertEqual(code, 0)
        self.assertEqual(self.requests, [("2026-11-11 05:00:00", "2026-11-18 04:59:59"),    # 7 days
                                         ("2026-11-18 05:00:00", "2026-11-20 04:59:59")])   # the other 2
        self.assertEqual(len(events), 9)   # still one insert (transaction) per day
        self.assertEqual(sum(" 2 missing" in line for line in self.log), 9)   # each day sees only its own point

    def test_insert_records_ids_before_commit(self):
        code, events = self.run_backfill()
        self.assertEqual(code, 0)
        self.assertEqual(events, [("commit", ["100", "101"]), ("commit", ["100", "101", "102", "103"])])
        self.assertIn("4 inserted (ids in", self.log[-1])

    def test_nothing_inserted_removes_the_empty_ids_file(self):
        stored = {("4501", m, lo): 1.5 for _, lo, _ in self.days for m in ("Water Temperature", "Conductivity")}
        code, events = self.run_backfill(stored=stored)
        self.assertEqual((code, events), (0, []))
        self.assertFalse(self.ids_path.exists())
        self.assertIn("0 missing", self.log[-1])

    def test_failure_reports_what_was_inserted_and_keeps_the_ids(self):
        code, _ = self.run_backfill(fail_on_day="2026-11-10", window=1)   # the second window's request fails
        self.assertEqual(code, 1)
        self.assertEqual(self.ids_path.read_text().split(), ["100", "101"])
        self.assertTrue(any("HTTP 503" in line for line in self.log))
        self.assertIn("stopped early", self.log[-1])
        self.assertIn("2 inserted (ids in", self.log[-1])

    def test_failure_with_nothing_inserted_removes_the_empty_ids_file(self):
        code, _ = self.run_backfill(fail_on_day="2026-11-09")
        self.assertEqual(code, 1)
        self.assertFalse(self.ids_path.exists())

    def test_check_inserts_nothing(self):
        code, events = self.run_backfill(check=True)
        self.assertEqual((code, events), (0, []))
        self.assertIn("4 missing on 2026-11-09 (2), 2026-11-10 (2)", self.log[-1])


class Settings(unittest.TestCase):
    def test_unset_wqdata_settings_stop_with_a_clear_error(self):
        from unittest import mock
        from config import Config
        with mock.patch.object(Config, "WQ_API_KEY", None), mock.patch("builtins.print") as out:
            self.assertEqual(bf.main(["--check"]), 2)
        self.assertIn("WQ_API_KEY", out.call_args[0][0])


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
