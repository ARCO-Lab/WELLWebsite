"""Export file names must use the days the user picked (site time), not UTC.
Run from dashboard/backend: python -m unittest discover -s tests"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.services.exports import default_export_filename, normalize_export_payload  # noqa: E402

ALL_SENSOR_GROUPS = ["Weather", "Quality", "Logger"]


def sensor(start, end, groups=ALL_SENSOR_GROUPS):
    return normalize_export_payload({"domain": "sensor", "start": start, "end": end, "group_types": groups})


def sampling(start, end):
    return normalize_export_payload({"domain": "sampling", "start": start, "end": end})


class ExportFilenames(unittest.TestCase):
    def test_single_day_in_winter(self):
        # What the dashboard sends for Nov 9: local 00:00 and 23:59:59.999 (EST, UTC-5) as UTC.
        name = default_export_filename(sensor("2026-11-09T05:00:00.000Z", "2026-11-10T04:59:59.999Z"))
        self.assertEqual(name, "WELLWestCampus_WaterLogger_WaterQuality_WeatherStation_20261109_20261109.csv")

    def test_range_in_summer_time(self):
        # Aug 1 .. Oct 31, both in EDT (UTC-4).
        name = default_export_filename(sensor("2026-08-01T04:00:00.000Z", "2026-11-01T03:59:59.999Z", ["Logger"]))
        self.assertEqual(name, "WELLWestCampus_WaterLogger_20260801_20261031.csv")

    def test_day_the_clocks_change(self):
        # Nov 1 2026 starts in EDT and ends in EST.
        name = default_export_filename(sensor("2026-11-01T04:00:00.000Z", "2026-11-02T04:59:59.999Z", ["Weather"]))
        self.assertEqual(name, "WELLWestCampus_WeatherStation_20261101_20261101.csv")

    def test_sampling(self):
        name = default_export_filename(sampling("2025-05-01T04:00:00.000Z", "2026-04-01T03:59:59.999Z"))
        self.assertEqual(name, "well_export_sampling_20250501_20260331.csv")

    def test_naive_times_are_already_local(self):
        name = default_export_filename(sensor("2026-11-09T00:00:00", "2026-11-09T23:59:59", ["Quality"]))
        self.assertEqual(name, "WELLWestCampus_WaterQuality_20261109_20261109.csv")


if __name__ == "__main__":
    unittest.main()
