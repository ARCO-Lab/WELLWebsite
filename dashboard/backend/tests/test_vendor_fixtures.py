"""Whole vendor responses (tests/fixtures/*.json) through the fetching and parsing code, from the HTTP reply to the
rows that would be stored. Run from dashboard/backend: python -m unittest discover -s tests -t .

The fixtures copy the shapes the code reads from LI-COR (HOBOlink) and WQData, with this station's sensor serials
and made-up values; they hold no keys or tokens. Both cover the night of 2026-11-01, when Toronto's clocks went
back from 02:00 EDT to 01:00 EST, and the WQData pages include one that says more=false while count < total, as
WQData has done. No test here makes a network request."""
import datetime as dt
import json
import math
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.services import quality, weather  # noqa: E402
from scripts import wqdata_backfill as bf  # noqa: E402
from utils import parsers  # noqa: E402
from utils.fetching import BadVendorResponse  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
UTC = dt.timezone.utc
STATION = "22051538"   # the weather station's logger serial; WQData's device id below is made up
DEVICE = "4501"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def toronto():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Toronto")
    except Exception:
        raise unittest.SkipTest("no time zone database on this machine")


def reply(body):
    """A stand-in for a requests.Response: HTTP 200 with this JSON body."""
    resp = mock.Mock(status_code=200)
    resp.raise_for_status.return_value = None
    resp.json.return_value = body
    return resp


class FixturesAreSanitized(unittest.TestCase):
    def test_no_credentials(self):
        for path in FIXTURES.glob("*.json"):
            text = path.read_text(encoding="utf-8").lower()
            for word in ("apikey", "token", "authorization", "bearer", "password"):
                self.assertNotIn(word, text, f"{path.name} mentions {word}")


class Licor(unittest.TestCase):
    body = load("licor_fall_back_2026-11-01.json")

    def test_get_page_returns_every_record_and_the_cap_flag(self):
        service = weather.WeatherService("https://licor.example/api", "token-not-real", STATION)
        start, end = dt.datetime(2026, 11, 1, 4, 30, tzinfo=UTC), dt.datetime(2026, 11, 1, 7, 30, tzinfo=UTC)
        with mock.patch.object(weather.requests, "get", return_value=reply(self.body)) as get:
            records, capped = service.get_page(start, end)
        self.assertEqual((len(records), capped), (16, False))
        self.assertEqual(get.call_args.kwargs["params"],
                         {"loggers": STATION, "start_date_time": "2026-11-01 04:30:00",
                          "end_date_time": "2026-11-01 07:29:59"})
        with mock.patch.object(weather.requests, "get", return_value=reply({**self.body, "max_results": True})):
            self.assertTrue(service.get_page(start, end)[1])

    def test_a_reply_without_a_data_list_is_an_error_not_an_empty_page(self):
        service = weather.WeatherService("https://licor.example/api", "token-not-real", STATION)
        start, end = dt.datetime(2026, 11, 1, 4, 30, tzinfo=UTC), dt.datetime(2026, 11, 1, 7, 30, tzinfo=UTC)
        for body in ({"error": "invalid date range"}, {"data": None}, {"data": "x"}, [], None):
            with mock.patch.object(weather.requests, "get", return_value=reply(body)):
                with self.assertRaisesRegex(BadVendorResponse, "no 'data' list"):
                    service.get_page(start, end)
        with mock.patch.object(weather.requests, "get", return_value=reply({"data": []})):
            self.assertEqual(service.get_page(start, end), ([], False))   # a real empty page is still fine

    def test_rows_on_the_fall_back_night(self):
        rows = parsers.licor_rows(self.body["data"], {"Weather", "Logger"}, STATION, toronto())
        local = dt.datetime(2026, 11, 1, 1, 0)
        self.assertEqual({k: r["value"] for k, r in rows.items() if r["group_type"] == "Weather"}, {
            (STATION, "Air Temperature", local): 4.1,                                 # 05:00Z, 01:00 EDT
            (STATION, "Air Temperature", local + dt.timedelta(minutes=50)): 4.0,      # 05:50Z, sent twice
            (STATION, "Air Temperature", local + dt.timedelta(hours=1)): 3.7,         # 07:00Z, 02:00 EST
            (STATION, "Relative Humidity", local): 91.5,
            (STATION, "Soil Temperature", local): 8.2,
            (STATION, "Solar Radiation", local): 0.6,
        })   # the station's battery (-B) isn't stored
        cfg = parsers.LOGGER_CONFIG["22168653"]
        logger = {k: r for k, r in rows.items() if r["group_type"] == "Logger"}
        self.assertEqual(sorted(logger), [("2577531", "Water Surface Elevation", local),
                                          ("2577531", "Water Temperature", local)])
        wse = logger[("2577531", "Water Surface Elevation", local)]
        self.assertEqual(wse["unit"], "m asl")
        self.assertAlmostEqual(wse["value"], cfg["z"] - cfg["L"] * math.cos(math.radians(cfg["theta"])) + 0.412,
                               places=12)   # from the 05:00Z depth; the 06:00Z one falls in the repeated hour
        # (the depth records say 'meters', as the live loggers do; that's accepted as 'm')
        self.assertEqual(logger[("2577531", "Water Temperature", local)]["value"], 7.31)

    def test_the_repeated_hour_keeps_only_its_first_reading(self):
        # recorded_at is stored as naive local time, so 06:00Z (01:00 EST) has the same key as 05:00Z (01:00 EDT).
        # The first reading wins and the second hour's readings are dropped: 3 of this fixture's records. This
        # pins today's behaviour; storing the hour twice needs a time-zone-aware column.
        rows = parsers.licor_rows(self.body["data"], {"Weather", "Logger"}, STATION, toronto())
        local = dt.datetime(2026, 11, 1, 1, 0)
        self.assertEqual(rows[(STATION, "Air Temperature", local)]["value"], 4.1)            # not 06:00Z's 3.9
        self.assertEqual(rows[(STATION, "Air Temperature", local + dt.timedelta(minutes=50))]["value"], 4.0)  # not 3.8
        self.assertNotIn(3.9, [r["value"] for r in rows.values()])
        self.assertNotIn(3.8, [r["value"] for r in rows.values()])


class WQData(unittest.TestCase):
    pages = load("wqdata_pages_fall_back_2026-11-01.json")
    START, TO = "2026-11-01 04:00:00", "2026-11-02 04:59:59"   # local midnight to midnight: 25 hours of UTC
    FROMS = [START, "2026-11-01 06:30:00", "2026-11-01 12:00:00"]

    def expected_rows(self):
        local = dt.datetime(2026, 11, 1)
        at = {"00:00": local, "01:30": local.replace(hour=1, minute=30), "07:00": local.replace(hour=7),
              "23:50": local.replace(hour=23, minute=50)}
        return {
            (DEVICE, "Water Temperature", at["00:00"]): 9.1,   # 04:00Z, EDT
            (DEVICE, "ODO", at["00:00"]): 10.2,
            (DEVICE, "Water Temperature", at["01:30"]): 9.0,   # 05:30Z, 01:30 EDT; 06:30Z (01:30 EST) is dropped
            (DEVICE, "ODO", at["01:30"]): 10.3,
            (DEVICE, "Water Temperature", at["07:00"]): 8.7,   # 12:00Z, EST; device power and "N/A" aren't stored
            (DEVICE, "ODO", at["07:00"]): 10.6,
            (DEVICE, "Water Temperature", at["23:50"]): 8.4,   # 04:50Z on Nov 2 is still Nov 1 in Toronto
        }

    def test_the_backfills_day_window_spans_25_hours(self):
        tz = toronto()
        [(day, lo, hi)] = bf.day_windows(dt.datetime(2026, 11, 2, 5, tzinfo=UTC), 1, tz)
        self.assertEqual(day, dt.date(2026, 11, 1))
        self.assertEqual(bf.to_utc(hi, tz) - bf.to_utc(lo, tz), dt.timedelta(hours=25))
        self.assertEqual(bf.to_utc(lo, tz).strftime(bf.FMT), self.START)

    def test_ingestion_pages_past_more_false_and_merges_the_split_point(self):
        service = quality.QualityService("https://wqdata.example/api", "key-not-real", DEVICE)
        service.sleep = lambda s: None
        with mock.patch.object(quality.requests, "get", side_effect=[reply(p) for p in self.pages]) as get:
            points = service.get_quality_data(self.START, self.TO)
        self.assertEqual([c.kwargs["params"]["from"] for c in get.call_args_list], self.FROMS)
        self.assertEqual(len(points), 5)   # 06:30 and 12:00 were sent on two pages each
        split = next(p for p in points if p["timestamp"] == "2026-11-01 06:30:00")
        self.assertEqual(sorted(v["parameterId"] for v in split["values"]), [125001, 125006])
        rows = parsers.quality_rows(points, DEVICE, toronto())
        self.assertEqual({k: r["value"] for k, r in rows.items()}, self.expected_rows())

    def test_backfill_reads_the_same_pages_into_the_same_rows(self):
        calls = []

        def get(url, params=None, timeout=None):
            calls.append(params)
            return reply(self.pages[len(calls) - 1])
        client = bf.WQData("https://wqdata.example/api", "key-not-real", DEVICE, get=get, sleep=lambda s: None)
        points = bf.fetch_points(client.get_page, dt.datetime(2026, 11, 1, 4, tzinfo=UTC),
                                 dt.datetime(2026, 11, 2, 5, tzinfo=UTC))
        self.assertEqual([(c["from"], c["to"]) for c in calls], [(f, self.TO) for f in self.FROMS])
        rows = parsers.quality_rows(points, DEVICE, toronto())
        self.assertEqual({k: r["value"] for k, r in rows.items()}, self.expected_rows())


if __name__ == "__main__":
    unittest.main()
