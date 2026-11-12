"""Tests for scripts/api_canary.py (no network). Run from dashboard/backend: python -m unittest discover -s tests -t .

CI runs these on every pull request, including the checks that the constants the canary copies still match
utils/parsers.py (the canary's own workflow installs only requests, so it can't run them)."""
import datetime as dt
import os
import pathlib
import sys
from unittest import SkipTest, TestCase, main, mock

import requests

os.environ["DATABASE_URL"] = "sqlite://"  # config is read once on first import; never a real database
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import api_canary as canary  # noqa: E402

SECRET = "SECRET-KEY-123"
NOW = dt.datetime(2026, 11, 10, 11, 17, tzinfo=dt.timezone.utc)

LICOR = {"max_results": False, "data": [
    {"logger_sn": "21893775", "sensor_sn": "21901556-1", "timestamp": "2026-11-10 10:00:00Z",
     "value": 3.2, "unit": "°C", "sensor_measurement_type": "Temperature"},
    {"logger_sn": "21893775", "sensor_sn": "22168653-1", "timestamp": "2026-11-10 10:00:00Z",
     "value": "0.41", "unit": "m"},
    # Records ingestion skips, so a null value or timestamp in them mustn't fail the canary: battery channels
    # ("-B") and logger channels whose base serial isn't a known logger.
    {"logger_sn": "21893775", "sensor_sn": "22168653-B", "timestamp": "2026-11-10 10:00:00Z",
     "value": None, "unit": "V"},
    {"logger_sn": "21893775", "sensor_sn": "21901556-B", "timestamp": None, "value": None},
    {"logger_sn": "21893775", "sensor_sn": "22168659-1", "timestamp": "2026-11-10 10:00:00Z", "value": None},
]}


def parsers():
    """utils.parsers, for the checks that the canary's copies of its constants still match. Skips only when a
    third-party package it needs (the database libraries) isn't installed; any other import error fails."""
    try:
        from utils import parsers as p
    except ModuleNotFoundError as e:
        if (e.name or "").split(".")[0] in {"utils", "db", "config", "scripts", "api"}:
            raise
        raise SkipTest(f"backend package not installed: {e.name}")
    return p
WQDATA = {"info": {"count": 2, "total": 2, "more": False, "lastDataPointTimestamp": "2026-11-10 10:00:00"},
          "data": [{"timestamp": "2026-11-10 10:00:00",
                    "values": [{"parameterId": 125001, "value": "7.1"}, {"parameterId": 999, "value": "x"}]}]}
BOREALIS = {"status": "OK", "data": {"latestVersion": {"versionState": "RELEASED", "files": [
    {"label": "WELLAncasterWatershed_Fall2025.xlsx",
     "dataFile": {"id": 12345, "filename": "WELLAncasterWatershed_Fall2025.xlsx", "restricted": False}}]}}}


def without(d, key):
    return {k: v for k, v in d.items() if k != key}


class LicorShape(TestCase):
    def test_ok(self):
        self.assertEqual(canary.check_licor(LICOR),
                         "5 records (1 weather, 1 water-level logger read by ingestion)")

    def test_rejects(self):
        weather, logger, battery = LICOR["data"][0], LICOR["data"][1], LICOR["data"][2]
        bad = [
            [],                                                        # not an object
            without(LICOR, "data"),
            {"data": []},                                              # no recent data
            {"data": [without(weather, "sensor_sn")]},
            {"data": [{**weather, "timestamp": "yesterday"}]},
            {"data": [{**weather, "value": "n/a"}]},
            {"data": [{**weather, "value": None}]},
            {"data": [without(logger, "value")]},
            {"data": [battery]},                                       # nothing ingestion would store
        ]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(canary.ShapeError):
                canary.check_licor(body)

    def test_some_readings_without_a_number_are_counted_not_failed(self):
        weather, logger = LICOR["data"][0], LICOR["data"][1]
        body = {"data": [weather, {**logger, "value": None}, {**weather, "value": "n/a"}]}
        self.assertEqual(canary.check_licor(body),
                         "3 records (1 weather, 0 water-level logger read by ingestion), 2 without a number (skipped)")

    def test_a_unit_change_fails(self):
        air = {**LICOR["data"][0], "sensor_sn": "21948438-1", "unit": "°F"}
        depth = {**LICOR["data"][1], "unit": "ft"}
        with self.assertRaisesRegex(canary.ShapeError, r"21948438-1 reports '°F', not '°C'; 22168653-1 reports 'ft'"):
            canary.check_licor({"data": [air, depth]})

    def test_depth_in_meters_passes(self):
        # What the live loggers send (Nov 2026): ingestion accepts it as 'm', so the canary mustn't fail on it.
        depth = [{**LICOR["data"][1], "sensor_sn": f"2216865{n}-1", "unit": "meters"} for n in (3, 4, 5, 6)]
        self.assertEqual(canary.check_licor({"data": [LICOR["data"][0], *depth]}),
                         "5 records (1 weather, 4 water-level logger read by ingestion)")

    def test_constants_match_ingestion(self):
        p = parsers()
        from utils.sensor_names import WEATHER_SENSOR_NAMES
        self.assertEqual(canary.LOGGER_PREFIX, p.LOGGER_PREFIX)
        self.assertEqual(canary.LOGGER_SERIALS, set(p.LOGGER_CONFIG))
        self.assertEqual(canary.WEATHER_UNITS, p.WEATHER_UNITS)
        self.assertEqual(canary.LOGGER_UNITS, p.LOGGER_UNITS)
        self.assertEqual(canary.SENTINEL_MAX, p.SENTINEL_MAX)
        self.assertEqual(canary.UNIT_ALIASES, p.UNIT_ALIASES)
        self.assertEqual(canary.WEATHER_SENSOR_NAMES, WEATHER_SENSOR_NAMES)

    def test_numbers_and_units_judged_as_ingestion_does(self):
        p = parsers()
        for value in (None, "", "n/a", True, float("nan"), "inf", 10 ** 400, 0, "4.5", -1.25,
                      -100000, "-99999", -99998.5):  # the last three: the vendors' "no reading" sentinel and just above
            self.assertEqual(canary.has_number(value), p.reading_value(value) is not None, repr(value))
        for r in LICOR["data"][:2] + [{**LICOR["data"][0], "sensor_sn": "21948438-1", "unit": "°F"},
                                      {**LICOR["data"][1], "unit": "ft"}, {**LICOR["data"][1], "unit": "meters"},
                                      {**LICOR["data"][1], "unit": " Metre "}, {**LICOR["data"][0], "unit": "°c"},
                                      {**LICOR["data"][0], "unit": "meters"}, {**LICOR["data"][1], "unit": None},
                                      {**LICOR["data"][0], "unit": " °C "}, {**LICOR["data"][1], "unit": "M"},
                                      {**LICOR["data"][1], "unit": "METERS"},
                                      *({**LICOR["data"][0], "sensor_sn": "21999998-1", "sensor_measurement_type": "Pressure",
                                         "unit": unit} for unit in ("mbar", " mbar ", "Mbar"))]:
            expected = canary.expected_unit(r)
            self.assertEqual(expected is not None and not canary.same_unit(r["unit"], expected),
                             p.unit_mismatch(r) is not None, r)

    def test_skips_the_same_records_as_ingestion(self):
        p = parsers()
        for r in LICOR["data"]:
            with self.subTest(sensor_sn=r["sensor_sn"]):
                rows = p.licor_rows([r], {"Weather", "Logger"}, "21893775", dt.timezone.utc)
                self.assertEqual(canary.licor_record_used(r["sensor_sn"]), bool(rows))


class WqdataShape(TestCase):
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
        self.assertEqual(canary.WQ_PARAMETER_IDS, set(parsers().QUALITY_PARAM_ID_MAP))


class BorealisShape(TestCase):
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
       "BOREALIS_URL": "https://borealis.invalid/dataverse/WELL", "BOREALIS_API_TOKEN": SECRET,
       "BOREALIS_SAMPLING_PERSISTENT_ID": "doi:aw", "BOREALIS_UPLOAD_PERSISTENT_ID": "doi:wc"}


class Run(TestCase):
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
    main()
