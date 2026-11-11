"""Tests for utils/parsers.py and utils/sensor_names.py, using records shaped like the real API responses.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils import parsers  # noqa: E402
from utils.sensor_names import weather_measurement_name  # noqa: E402

UTC = dt.timezone.utc
STATION = "22051538"


def licor(sn, value, ts="2026-11-10 04:00:00Z", kind="Temperature", unit="°C"):
    return {"logger_sn": STATION, "sensor_sn": sn, "sensor_measurement_type": kind, "timestamp": ts, "unit": unit, "value": value}


def ny():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:
        raise unittest.SkipTest("no time zone database on this machine")


class SensorNames(unittest.TestCase):
    def test_air_and_soil_are_not_swapped(self):
        # 21948438 is the temperature/RH/dew-point sensor (air); 22154270 is the soil probe.
        self.assertEqual(weather_measurement_name("21948438-1", "Temperature"), "Air Temperature")
        self.assertEqual(weather_measurement_name("22154270-1", "Temperature"), "Soil Temperature")
        self.assertEqual(weather_measurement_name("21948438-2", "RH"), "Relative Humidity")

    def test_other_sensors_keep_the_api_name(self):
        self.assertEqual(weather_measurement_name("21948438-3", "Dew Point"), "Dew Point")
        self.assertEqual(weather_measurement_name("22154091-1", "Solar Radiation"), "Solar Radiation")


class Weather(unittest.TestCase):
    def test_parse(self):
        m = parsers.parse_weather_entry(licor("21948438-1", 6.25), STATION)
        self.assertEqual((m.group_type, m.measurement_type, m.value, m.unit, m.station_id),
                         ("Weather", "Air Temperature", 6.25, "°C", STATION))
        self.assertEqual(m.recorded_at, dt.datetime(2026, 11, 10, 4, tzinfo=UTC))   # LI-COR times are UTC ("Z")

    def test_battery_skipped(self):
        self.assertIsNone(parsers.parse_weather_entry(licor("22051538-B", 12.9, kind="Battery", unit="V"), STATION))


class Logger(unittest.TestCase):
    def test_depth_becomes_water_surface_elevation(self):
        cfg = parsers.LOGGER_CONFIG["22168653"]
        m = parsers.parse_logger_entry(licor("22168653-1", 0.5, kind="Sensor Depth", unit="m"))
        expected = cfg["z"] - cfg["L"] * math.cos(math.radians(cfg["theta"])) + 0.5
        self.assertEqual((m.station_id, m.measurement_type, m.unit), (2577531, "Water Surface Elevation", "m asl"))
        self.assertAlmostEqual(m.value, expected, places=12)

    def test_water_temperature(self):
        m = parsers.parse_logger_entry(licor("22168654-3", 4.4, kind="Water Temperature"))
        self.assertEqual((m.station_id, m.measurement_type, m.value, m.unit), (2577532, "Water Temperature", 4.4, "°C"))

    def test_channels_we_dont_store_are_skipped(self):
        for sn in ("22168653-2", "22168657-4", "22168653-B", "22168658-1", "22168653"):   # diff pressure, baro, battery, unknown logger, bad serial
            self.assertIsNone(parsers.parse_logger_entry(licor(sn, 1.0)), sn)


class Quality(unittest.TestCase):
    entry = {"timestamp": "2026-11-09 02:00:00", "values": [
        {"parameterId": 125001, "value": "8.5"},      # water temperature
        {"parameterId": 115219, "value": "10.4"},     # device power: not stored
        {"parameterId": 125002, "value": "N/A"},      # unparseable: skipped
    ]}

    def test_parse(self):
        rows = parsers.parse_quality_entry(self.entry, "4501")
        self.assertEqual([(r.measurement_type, r.value, r.unit) for r in rows], [("Water Temperature", 8.5, "°C")])
        self.assertEqual(rows[0].recorded_at, dt.datetime(2026, 11, 9, 2, tzinfo=UTC))   # WQData times are UTC

    def test_rows_are_stored_in_local_time(self):
        rows = parsers.quality_rows([self.entry, self.entry], "4501", ny())
        self.assertEqual(list(rows), [("4501", "Water Temperature", dt.datetime(2026, 11, 8, 21))])


class LicorRows(unittest.TestCase):
    records = [licor("21948438-1", 6.25), licor("21948438-1", 6.25),               # duplicate in the response
               licor("22154270-1", 9.1), licor("22051538-B", 12.9),
               licor("22168653-3", 4.4, kind="Water Temperature"), licor("22168657-4", 99.0)]

    def test_groups_and_local_time(self):
        tz = ny()
        both = parsers.licor_rows(self.records, {"Weather", "Logger"}, STATION, tz)
        self.assertEqual(sorted(both), [
            ("22051538", "Air Temperature", dt.datetime(2026, 11, 9, 23)),
            ("22051538", "Soil Temperature", dt.datetime(2026, 11, 9, 23)),
            ("2577531", "Water Temperature", dt.datetime(2026, 11, 9, 23)),
        ])
        self.assertEqual(len(parsers.licor_rows(self.records, {"Logger"}, STATION, tz)), 1)
        self.assertEqual(len(parsers.licor_rows(self.records, {"Weather"}, STATION, tz)), 2)


if __name__ == "__main__":
    unittest.main()
