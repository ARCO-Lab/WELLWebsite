"""WQData failures must be logged without the API key. Run from dashboard/backend: python -m unittest discover -s tests"""
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


def fetch_logging(side_effect):
    service = quality.QualityService(URL, KEY, "1")
    out = io.StringIO()
    with mock.patch.object(quality.requests, "get", side_effect=side_effect), contextlib.redirect_stdout(out):
        service.get_quality_data("2026-11-01 00:00:00", "2026-11-02 00:00:00")
    return out.getvalue()


class QualityErrorLoggingTests(unittest.TestCase):
    def test_the_raw_error_text_would_contain_the_key(self):
        self.assertIn(KEY, str(http_error(429)))  # why the message must not be printed as-is

    def test_a_failed_page_is_logged_without_the_key(self):
        log = fetch_logging(http_error(429))
        self.assertIn("HTTPError (HTTP 429)", log)
        self.assertNotIn(KEY, log)

    def test_a_failed_tail_fetch_is_logged_without_the_key(self):
        page = mock.Mock()
        page.raise_for_status.return_value = None
        page.json.return_value = {"data": [{"v": 1}], "info": {"lastDataPointTimestamp": "2026-11-01 10:00:00", "more": False}}
        conn_error = requests.ConnectionError(f"Max retries exceeded with url: /data?apiKey={KEY}")
        log = fetch_logging([page, conn_error])
        self.assertIn("Tail fetch failed: ConnectionError", log)
        self.assertNotIn(KEY, log)


if __name__ == "__main__":
    unittest.main()
