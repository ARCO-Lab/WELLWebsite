"""Export file names must use the days the user picked (site time), not UTC.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
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


class ExportRangeForEachTable(unittest.TestCase):
    """Sensor readings are stored as instants, so a sensor range is kept as UTC instants (a bound without an offset
    is Toronto time); sampling times are naive Toronto time, so a sampling range becomes Toronto wall-clock time.
    Either way the range doesn't depend on the database session's time zone."""

    def test_aware_bounds_stay_instants(self):
        filters = sensor("2026-10-31T04:00:00.000Z", "2026-11-02T04:59:59.999Z")
        self.assertEqual(filters["start"], "2026-10-31T04:00:00+00:00")
        self.assertEqual(filters["end"], "2026-11-02T04:59:59.999000+00:00")

    def test_mixed_aware_and_naive_bounds_are_compared_as_instants(self):
        # 21:00 on Nov 9 in Toronto is 02:00Z on Nov 10, before the aware end; compared as given this raised TypeError
        filters = sensor("2026-11-09T21:00:00", "2026-11-10T03:00:00Z")
        self.assertEqual((filters["start"], filters["end"]), ("2026-11-10T02:00:00+00:00", "2026-11-10T03:00:00+00:00"))
        with self.assertRaisesRegex(ValueError, "start must be before end"):
            sensor("2026-11-09T23:00:00", "2026-11-10T03:00:00Z")

    def test_naive_bounds_are_kept(self):
        filters = sampling("2026-11-09T00:00:00", "2026-11-09T23:59:59")
        self.assertEqual((filters["start"], filters["end"]), ("2026-11-09T00:00:00", "2026-11-09T23:59:59"))

    def test_aware_sampling_bounds_become_toronto_wall_clock(self):
        filters = sampling("2026-10-31T04:00:00.000Z", "2026-11-02T04:59:59.999Z")
        self.assertEqual((filters["start"], filters["end"]), ("2026-10-31T00:00:00", "2026-11-01T23:59:59.999000"))


if __name__ == "__main__":
    unittest.main()
