"""Whole vendor responses (tests/fixtures/*.json) through the fetching and parsing code, from the HTTP reply to the
rows that would be stored. Run from dashboard/backend: python -m unittest discover -s tests -t .

The fixtures copy the shapes the code reads from LI-COR (HOBOlink) and WQData, with this station's sensor serials
and made-up values; they hold no keys or tokens. Both cover the night of 2026-11-01, when Toronto's clocks went
back from 02:00 EDT to 01:00 EST, and both copies of the repeated hour must be kept. The WQData pages include one
that says more=false while count < total, as WQData has done. No test here makes a network request."""
import datetime as dt
import json
import math
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.services import quality, weather  # noqa: E402
from scripts import wqdata_backfill as bf  # noqa: E402
from utils import parsers  # noqa: E402
from utils.timezone import site_wall_time  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
UTC = dt.timezone.utc
STATION = "22051538"   # the weather station's logger serial; WQData's device id below is made up
DEVICE = "4501"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
                with self.assertRaisesRegex(weather.LicorReplyError, "no 'data' list"):
                    service.get_page(start, end)
        with mock.patch.object(weather.requests, "get", return_value=reply({"data": []})):
            self.assertEqual(service.get_page(start, end), ([], False))   # a real empty page is still fine

    def test_rows_on_the_fall_back_night(self):
        rows = parsers.licor_rows(self.body["data"], {"Weather", "Logger"}, STATION)
        at = {h: dt.datetime(2026, 11, 1, *h, tzinfo=UTC) for h in ((5, 0), (5, 50), (6, 0), (6, 50), (7, 0))}
        self.assertEqual({k: r["value"] for k, r in rows.items() if r["group_type"] == "Weather"}, {
            (STATION, "Air Temperature", at[5, 0]): 4.1,     # 01:00 EDT
            (STATION, "Air Temperature", at[5, 50]): 4.0,    # 01:50 EDT, sent twice
            (STATION, "Air Temperature", at[6, 0]): 3.9,     # 01:00 EST, the repeated hour
            (STATION, "Air Temperature", at[6, 50]): 3.8,    # 01:50 EST
            (STATION, "Air Temperature", at[7, 0]): 3.7,     # 02:00 EST
            (STATION, "Relative Humidity", at[5, 0]): 91.5,
            (STATION, "Soil Temperature", at[5, 0]): 8.2,
            (STATION, "Solar Radiation", at[5, 0]): 0.6,
        })   # the station's battery (-B) isn't stored
        cfg = parsers.LOGGER_CONFIG["22168653"]
        logger = {k: r for k, r in rows.items() if r["group_type"] == "Logger"}
        self.assertEqual(sorted(logger), [("2577531", "Water Surface Elevation", at[5, 0]),
                                          ("2577531", "Water Surface Elevation", at[6, 0]),
                                          ("2577531", "Water Temperature", at[5, 0])])
        base = cfg["z"] - cfg["L"] * math.cos(math.radians(cfg["theta"]))
        wse = logger[("2577531", "Water Surface Elevation", at[5, 0])]
        self.assertEqual(wse["unit"], "m asl")
        self.assertAlmostEqual(wse["value"], base + 0.412, places=12)
        self.assertAlmostEqual(logger[("2577531", "Water Surface Elevation", at[6, 0])]["value"], base + 0.418, places=12)
        self.assertEqual(logger[("2577531", "Water Temperature", at[5, 0])]["value"], 7.31)

    def test_the_repeated_hour_keeps_both_readings(self):
        # 05:00Z and 06:00Z are both 01:00 on the site's clock. recorded_at holds instants, so both are stored;
        # before, the second hour's readings had the first hour's key and were dropped.
        rows = parsers.licor_rows(self.body["data"], {"Weather", "Logger"}, STATION)
        air = sorted((k[2], r["value"]) for k, r in rows.items() if k[1] == "Air Temperature")
        self.assertEqual([site_wall_time(t).strftime("%H:%M") for t, _ in air], ["01:00", "01:50", "01:00", "01:50", "02:00"])
        self.assertEqual([v for _, v in air], [4.1, 4.0, 3.9, 3.8, 3.7])
        self.assertTrue(all(k[2].tzinfo is UTC for k in rows))   # stored as aware UTC


class WQData(unittest.TestCase):
    pages = load("wqdata_pages_fall_back_2026-11-01.json")
    START, TO = "2026-11-01 04:00:00", "2026-11-02 04:59:59"   # local midnight to midnight: 25 hours of UTC
    FROMS = [START, "2026-11-01 06:30:00", "2026-11-01 12:00:00"]

    def expected_rows(self):
        at = {s: dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
              for s in ("2026-11-01 04:00", "2026-11-01 05:30", "2026-11-01 06:30", "2026-11-01 12:00", "2026-11-02 04:50")}
        return {
            (DEVICE, "Water Temperature", at["2026-11-01 04:00"]): 9.1,   # 00:00 EDT
            (DEVICE, "ODO", at["2026-11-01 04:00"]): 10.2,
            (DEVICE, "Water Temperature", at["2026-11-01 05:30"]): 9.0,   # 01:30 EDT
            (DEVICE, "ODO", at["2026-11-01 05:30"]): 10.3,
            (DEVICE, "Water Temperature", at["2026-11-01 06:30"]): 8.9,   # 01:30 EST, the repeated hour, sent on two pages
            (DEVICE, "ODO", at["2026-11-01 06:30"]): 10.4,
            (DEVICE, "Water Temperature", at["2026-11-01 12:00"]): 8.7,   # 07:00 EST; device power and "N/A" aren't stored
            (DEVICE, "ODO", at["2026-11-01 12:00"]): 10.6,
            (DEVICE, "Water Temperature", at["2026-11-02 04:50"]): 8.4,   # 23:50 EST, still Nov 1 in Toronto
        }

    def test_the_backfills_day_window_spans_25_hours(self):
        [(day, lo, hi)] = bf.day_windows(dt.datetime(2026, 11, 2, 5, tzinfo=UTC), 1)
        self.assertEqual(day, dt.date(2026, 11, 1))
        self.assertEqual(hi - lo, dt.timedelta(hours=25))
        self.assertEqual(lo.strftime(bf.FMT), self.START)

    def test_backfill_inserts_the_repeated_hour_the_table_lacks(self):
        # The table as it was before timestamptz: the first (EDT) 01:30 reading, not the second (EST) one.
        stored = {k: v for k, v in self.expected_rows().items() if k[2] != dt.datetime(2026, 11, 1, 6, 30, tzinfo=UTC)}
        calls, inserted = [], []

        def get(url, params=None, timeout=None):
            calls.append(params)
            return reply(self.pages[len(calls) - 1])

        def insert_rows(rows, record_ids):
            inserted.extend(rows)
            record_ids(list(range(len(rows))))
            return list(range(len(rows)))
        client = bf.WQData("https://wqdata.example/api", "key-not-real", DEVICE, get=get, sleep=lambda s: None)
        days = bf.day_windows(dt.datetime(2026, 11, 2, 5, tzinfo=UTC), 1)
        with tempfile.TemporaryDirectory() as tmp:
            log = []
            code = bf.backfill(days, DEVICE, client.get_page, lambda lo, hi: dict(stored), insert_rows,
                               pathlib.Path(tmp) / "ids", check=False, log=log.append)
        self.assertEqual(code, 0)
        self.assertEqual(sorted((r["measurement_type"], r["recorded_at"], r["value"]) for r in inserted), [
            ("ODO", dt.datetime(2026, 11, 1, 6, 30, tzinfo=UTC), 10.4),
            ("Water Temperature", dt.datetime(2026, 11, 1, 6, 30, tzinfo=UTC), 8.9)])

    def test_ingestion_pages_past_more_false_and_merges_the_split_point(self):
        service = quality.QualityService("https://wqdata.example/api", "key-not-real", DEVICE)
        service.sleep = lambda s: None
        with mock.patch.object(quality.requests, "get", side_effect=[reply(p) for p in self.pages]) as get:
            points = service.get_quality_data(self.START, self.TO)
        self.assertEqual([c.kwargs["params"]["from"] for c in get.call_args_list], self.FROMS)
        self.assertEqual(len(points), 5)   # 06:30 and 12:00 were sent on two pages each
        split = next(p for p in points if p["timestamp"] == "2026-11-01 06:30:00")
        self.assertEqual(sorted(v["parameterId"] for v in split["values"]), [125001, 125006])
        rows = parsers.quality_rows(points, DEVICE)
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
        rows = parsers.quality_rows(points, DEVICE)
        self.assertEqual({k: r["value"] for k, r in rows.items()}, self.expected_rows())


if __name__ == "__main__":
    unittest.main()
