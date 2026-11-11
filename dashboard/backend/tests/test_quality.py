"""WQData fetching (api/services/quality.py): paging that doesn't trust info.more alone, and failures logged
without the API key. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.services import quality  # noqa: E402

KEY = "secret-wqdata-key-123"
URL = "https://wqdata.example/api"
START, END = "2026-11-01 00:00:00", "2026-11-15 00:00:00"


def http_error(status):
    """What requests raises for a 4xx/5xx: its message includes the full URL, query string and all."""
    resp = requests.Response()
    resp.status_code = status
    resp.url = f"{URL}/devices/1/parameters/data?apiKey={KEY}&from=x&to=y"
    resp.reason = "Too Many Requests"
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        return e
    raise AssertionError("raise_for_status did not raise")


def page(points, more, count=None, total=None):
    """A fake WQData response. points: (timestamp, [parameterId, ...])."""
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    info = {"more": more, "lastDataPointTimestamp": points[-1][0] if points else None}
    if count is not None:
        info.update(count=count, total=total)
    resp.json.return_value = {
        "data": [{"timestamp": ts, "values": [{"parameterId": p, "value": "1.0"} for p in params]} for ts, params in points],
        "info": info,
    }
    return resp


def fetch(responses, max_pages=None):
    """(points, log, the `from` of each request) for a fetch served by `responses`."""
    service = quality.QualityService(URL, KEY, "1")
    service.sleep = lambda s: None
    if max_pages:
        service.MAX_PAGES = max_pages
    out = io.StringIO()
    with mock.patch.object(quality.requests, "get", side_effect=responses) as get, contextlib.redirect_stdout(out):
        points = service.get_quality_data(START, END)
    return points, out.getvalue(), [c.kwargs["params"]["from"] for c in get.call_args_list]


class QualityPagingTests(unittest.TestCase):
    def test_keeps_paging_when_more_is_false_but_count_is_below_total(self):
        """Seen on WQData: a 14-day request's 4th page said more=false with count 6,963 of total 12,591."""
        points, _, froms = fetch([
            page([("2026-11-01 00:00:00", [1, 2]), ("2026-11-05 00:00:00", [1, 2])], more=False, count=4, total=8),
            page([("2026-11-05 00:00:00", [1, 2]), ("2026-11-10 00:00:00", [1, 2])], more=False, count=4, total=6),
            page([("2026-11-10 00:00:00", [1, 2]), ("2026-11-14 00:00:00", [1, 2])], more=False, count=4, total=4),
        ])
        self.assertEqual(froms, [START, "2026-11-05 00:00:00", "2026-11-10 00:00:00"])
        self.assertEqual([p["timestamp"] for p in points],
                         ["2026-11-01 00:00:00", "2026-11-05 00:00:00", "2026-11-10 00:00:00", "2026-11-14 00:00:00"])

    def test_a_point_split_across_two_pages_is_merged_once(self):
        points, _, _ = fetch([
            page([("2026-11-01 00:00:00", [1, 2]), ("2026-11-02 00:00:00", [1])], more=True, count=3, total=5),
            page([("2026-11-02 00:00:00", [1, 2]), ("2026-11-03 00:00:00", [1])], more=False, count=3, total=3),
        ])
        self.assertEqual([p["timestamp"] for p in points], ["2026-11-01 00:00:00", "2026-11-02 00:00:00", "2026-11-03 00:00:00"])
        self.assertEqual(sorted(v["parameterId"] for v in points[1]["values"]), [1, 2])

    def test_stops_when_more_is_false_and_count_reaches_total(self):
        _, _, froms = fetch([page([("2026-11-01 00:00:00", [1])], more=False, count=1, total=1)])
        self.assertEqual(froms, [START])

    def test_stops_on_more_false_when_counts_are_missing(self):
        _, _, froms = fetch([page([("2026-11-01 00:00:00", [1])], more=False)])
        self.assertEqual(froms, [START])

    def test_stops_and_logs_when_paging_does_not_advance(self):
        stuck = page([("2026-11-02 00:00:00", [1])], more=True, count=1, total=9)
        points, log, froms = fetch([stuck, stuck, stuck])
        self.assertEqual(len(froms), 2)
        self.assertEqual(len(points), 1)
        self.assertIn("didn't advance", log)

    def test_the_page_cap_is_logged(self):
        pages = [page([(f"2026-11-0{d} 00:00:00", [1])], more=True, count=1, total=9) for d in range(2, 5)]
        points, log, froms = fetch(pages, max_pages=3)
        self.assertEqual(len(froms), 3)
        self.assertEqual(len(points), 3)
        self.assertIn("stopped after 3 pages", log)


class QualityErrorLoggingTests(unittest.TestCase):
    def test_the_raw_error_text_would_contain_the_key(self):
        self.assertIn(KEY, str(http_error(429)))  # why the message must not be printed as-is

    def test_a_failed_page_is_logged_without_the_key(self):
        _, log, _ = fetch(http_error(429))
        self.assertIn("HTTPError (HTTP 429)", log)
        self.assertNotIn(KEY, log)

    def test_a_failed_later_page_is_logged_without_the_key_and_keeps_what_was_read(self):
        conn_error = requests.ConnectionError(f"Max retries exceeded with url: /data?apiKey={KEY}")
        points, log, _ = fetch([page([("2026-11-02 00:00:00", [1])], more=True, count=1, total=5), conn_error])
        self.assertEqual(len(points), 1)
        self.assertIn("ConnectionError", log)
        self.assertNotIn(KEY, log)


if __name__ == "__main__":
    unittest.main()
