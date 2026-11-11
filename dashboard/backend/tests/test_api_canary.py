"""Tests for scripts/api_canary.py (no network). Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import api_canary as canary  # noqa: E402

SECRET = "SECRET-KEY-123"
NOW = dt.datetime(2026, 11, 10, 11, 17, tzinfo=dt.timezone.utc)

LICOR = {"max_results": False, "data": [
    {"logger_sn": "21893775", "sensor_sn": "21901556-1", "timestamp": "2026-11-10 10:00:00Z",
     "value": 3.2, "unit": "°C", "sensor_measurement_type": "Temperature"},
    {"logger_sn": "21893775", "sensor_sn": "22168653-1", "timestamp": "2026-11-10 10:00:00Z",
     "value": "0.41", "unit": "m"},
]}
WQDATA = {"info": {"count": 2, "total": 2, "more": False, "lastDataPointTimestamp": "2026-11-10 10:00:00"},
          "data": [{"timestamp": "2026-11-10 10:00:00",
                    "values": [{"parameterId": 125001, "value": "7.1"}, {"parameterId": 999, "value": "x"}]}]}
BOREALIS = {"status": "OK", "data": {"latestVersion": {"versionState": "RELEASED", "files": [
    {"label": "WELLAncasterWatershed_Fall2025.xlsx",
     "dataFile": {"id": 12345, "filename": "WELLAncasterWatershed_Fall2025.xlsx", "restricted": False}}]}}}


def without(d, key):
    return {k: v for k, v in d.items() if k != key}


class LicorShape(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(canary.check_licor(LICOR), "2 records (1 weather, 1 water-level logger)")

    def test_rejects(self):
        bad = [
            [],                                                        # not an object
            without(LICOR, "data"),
            {"data": []},                                              # no recent data
            {"data": [without(LICOR["data"][0], "sensor_sn")]},
            {"data": [{**LICOR["data"][0], "timestamp": "yesterday"}]},
            {"data": [{**LICOR["data"][0], "value": "n/a"}]},
        ]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(canary.ShapeError):
                canary.check_licor(body)

    def test_logger_prefix_matches_ingestion(self):
        try:
            from utils.parsers import LOGGER_PREFIX
        except ImportError as e:
            self.skipTest(f"backend packages not installed: {e}")
        self.assertEqual(canary.LOGGER_PREFIX, LOGGER_PREFIX)


class WqdataShape(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(canary.check_wqdata(WQDATA), "1 points, 1 values ingestion stores")

    def test_rejects(self):
        point = WQDATA["data"][0]
        bad = [
            None,
            without(WQDATA, "data"),
            without(WQDATA, "info"),
            {**WQDATA, "data": []},
            {**WQDATA, "data": [without(point, "values")]},
            {**WQDATA, "data": [{**point, "timestamp": "2026-11-10T10:00:00Z"}]},   # ingestion parses a fixed format
            {**WQDATA, "data": [{**point, "values": [{"value": "7.1"}]}]},
            {**WQDATA, "data": [{**point, "values": [{"parameterId": 999, "value": "1"}]}]},
        ]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(canary.ShapeError):
                canary.check_wqdata(body)

    def test_parameter_ids_match_ingestion(self):
        try:
            from utils.parsers import QUALITY_PARAM_ID_MAP
        except ImportError as e:
            self.skipTest(f"backend packages not installed: {e}")
        self.assertEqual(canary.WQ_PARAMETER_IDS, set(QUALITY_PARAM_ID_MAP))


class BorealisShape(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(canary.check_borealis(BOREALIS), "RELEASED, 1 files")

    def test_rejects(self):
        latest = BOREALIS["data"]["latestVersion"]
        bad = [
            {"status": "ERROR", "message": "Bad api key"},
            {"data": {}},
            {"data": {"latestVersion": without(latest, "versionState")}},
            {"data": {"latestVersion": without(latest, "files")}},
            {"data": {"latestVersion": {**latest, "files": [{"label": "x"}]}}},
            {"data": {"latestVersion": {**latest, "files": [{"dataFile": {"id": 1}}]}}},
        ]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(canary.ShapeError):
                canary.check_borealis(body)


class Response:
    """Enough of requests.Response for get_json: the URL carries the key, as WQData's does."""
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body
        self.url = f"https://example.invalid/data?apiKey={SECRET}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} Client Error for url: {self.url}", response=self)

    def json(self):
        if self.body is None:
            raise requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
        return self.body


ENV = {"HOBO_API_URL": "https://licor.invalid/v1/data", "HOBO_API_TOKEN": SECRET, "HOBO_LOGGERS": "21893775,x",
       "WQ_API_URL": "https://wq.invalid/api/v1", "WQ_API_KEY": SECRET, "WQ_DEVICE_ID": "42",
       "DEMO_BOREALIS_URL": "https://borealis.invalid", "BOREALIS_API_TOKEN": SECRET,
       "DEMO_BOREALIS_AW_PERSISTENT_ID": "doi:aw", "DEMO_BOREALIS_WC_PERSISTENT_ID": "doi:wc"}


class Run(unittest.TestCase):
    def run_with(self, responses, **env):
        """Run every probe against canned responses (one list per probe, in order); returns (failed, lines, calls)."""
        queue = list(responses)
        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return queue.pop(0)

        lines = []
        with mock.patch.multiple(canary.Config, **{**ENV, **env}), mock.patch.object(canary.requests, "get", fake_get):
            failed = canary.run(now=NOW, out=lines.append)
        return failed, lines, calls

    def test_all_ok(self):
        failed, lines, calls = self.run_with([Response(200, LICOR), Response(200, WQDATA),
                                              Response(200, BOREALIS), Response(200, BOREALIS)])
        self.assertEqual(failed, [])
        self.assertEqual([line.split(":")[0] for line in lines], ["OK   LI-COR", "OK   WQData", "OK   Borealis"])
        # One request each to LI-COR and WQData (WQData's quota is shared with ingestion), one per Borealis dataset.
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0][1]["params"]["loggers"], "21893775")
        self.assertEqual(calls[1][1]["params"], {"apiKey": SECRET, "from": "2026-11-10 05:17:00",
                                                 "to": "2026-11-10 11:17:00"})
        self.assertEqual([c[1]["params"]["persistentId"] for c in calls[2:]], ["doi:aw", "doi:wc"])

    def test_failures_are_reported_without_secrets_and_dont_stop_the_others(self):
        failed, lines, calls = self.run_with([Response(200, {"data": []}), Response(500), Response(401)])
        self.assertEqual(failed, ["LI-COR", "WQData", "Borealis"])
        self.assertEqual(lines, [
            "FAIL LI-COR: unexpected response: no records in the last 6 h",
            "FAIL WQData: HTTPError (HTTP 500)",
            "FAIL Borealis: download dataset: HTTPError (HTTP 401)",
        ])
        self.assertEqual(len(calls), 3)   # no retries; Borealis stops at the first failed dataset

    def test_non_json_and_network_errors(self):
        def boom(url, **kwargs):
            raise requests.exceptions.ConnectionError(f"Max retries exceeded with url: {url}?apiKey={SECRET}")

        failed, lines, _ = self.run_with([Response(200, None)] * 4)
        self.assertTrue(all(SECRET not in line and "invalid" not in line for line in lines))
        self.assertEqual(failed, ["LI-COR", "WQData", "Borealis"])
        lines = []
        with mock.patch.multiple(canary.Config, **ENV), mock.patch.object(canary.requests, "get", boom):
            canary.run(now=NOW, out=lines.append)
        self.assertEqual(lines[1], "FAIL WQData: ConnectionError")
        self.assertTrue(all(SECRET not in line for line in lines))

    def test_missing_settings_name_the_variables(self):
        failed, lines, calls = self.run_with([Response(200, WQDATA), Response(200, BOREALIS), Response(200, BOREALIS)],
                                             HOBO_API_TOKEN=None)
        self.assertEqual(failed, ["LI-COR"])
        self.assertEqual(lines[0], "FAIL LI-COR: not configured: HOBOLINK_API_TOKEN")
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
