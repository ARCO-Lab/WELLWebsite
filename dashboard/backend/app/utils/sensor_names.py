# Names for weather-station sensors that LI-COR reports generically (e.g. "Temperature", "RH").
# Used by every script that parses LI-COR data, so the names can't drift apart.
#
# 21948438 is the temperature / relative humidity / dew point sensor, so its temperature channel
# is the air temperature. 22154270 is a single temperature probe in the soil.
# Checked against the stored data in Nov 2026: 21948438-1 peaks mid-afternoon, swings about 10 °C
# a day and moves opposite to humidity; 22154270-1 lags into the evening and swings about 1 °C,
# which is how soil behaves. (Before Nov 2026 these two names were the wrong way round.)
WEATHER_SENSOR_NAMES = {
    "21948438-1": "Air Temperature",
    "21948438-2": "Relative Humidity",
    "22154270-1": "Soil Temperature",
}


def weather_measurement_name(sensor_sn, api_name):
    """The measurement name to store for a weather sensor: our name if we have one, else LI-COR's."""
    return WEATHER_SENSOR_NAMES.get(sensor_sn, api_name)
