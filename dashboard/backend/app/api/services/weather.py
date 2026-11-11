# This file defines the WeatherService class for fetching weather station data from an external API.
# It handles authentication, logger selection, and filtering of weather data.

import requests, sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
from config import Config
from utils.fetching import BadVendorResponse
from datetime import datetime, timedelta, timezone

def page_records(body):
    """(records, capped) from a LI-COR reply. A reply without a "data" list (not a JSON object, "data" missing,
    null or not a list) raises BadVendorResponse instead of reading as an empty page, so an error body that comes
    back with HTTP 200, or a changed format, fails the run (and is reported, and the alerts say "vendor problem"
    rather than "vendor OK, check the sensor") rather than looking like a quiet period with no readings."""
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        keys = sorted(body)[:10] if isinstance(body, dict) else type(body).__name__   # field names only, never values
        raise BadVendorResponse(f"LI-COR reply has no 'data' list (got {keys})")
    return body["data"], bool(body.get("max_results"))


class WeatherService:
    def __init__(self, api_url, api_token, logger_ids):
        # Initialize with API URL, token, and logger IDs
        self.api_url = api_url
        self.api_token = api_token
        self.logger_ids = logger_ids.split(",")

    def get_headers(self):
        # Prepare authorization headers for API requests
        return {
            "Authorization": f"Bearer {self.api_token}"
        }

    def get_logger_id(self):
        # Return the first logger ID (used for group queries)
        return self.logger_ids[0]  # Extendable later

    def get_page(self, start, end):
        """One request for [start, end) (aware datetimes): (all records, whether LI-COR capped the response).

        Unlike get_weather_data this returns every sensor (weather and loggers), reports the cap
        ("max_results": true at 100,000 records) instead of hiding it, retries briefly on rate limits and
        server errors, and raises on any other HTTP error, or a reply without a "data" list (BadVendorResponse), so a
        failed fetch can't look like "no data".
        Use utils.fetching.fetch_range to read longer periods.
        """
        fmt = "%Y-%m-%d %H:%M:%S"
        params = {
            "loggers": self.get_logger_id(),
            "start_date_time": start.astimezone(timezone.utc).strftime(fmt),
            "end_date_time": (end - timedelta(seconds=1)).astimezone(timezone.utc).strftime(fmt),
        }
        for attempt in range(4):
            response = requests.get(self.api_url, headers=self.get_headers(), params=params, timeout=120)
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(10 * (attempt + 1))
        response.raise_for_status()
        return page_records(response.json())

    def get_weather_data(self, start_time=None, end_time=None):
        # Fetch weather data from the API, optionally for a time range
        if not start_time or not end_time:
            now = datetime.now(timezone.utc)
            start_time = "2025-05-09 11:20:00" # "2025-05-09 11:20:00"
            end_time = now.strftime("%Y-%m-%d %H:%M:%S")  # now.strftime("%Y-%m-%d %H:%M:%S")


        params = {
            "loggers": self.get_logger_id(),
            "start_date_time": start_time,
            "end_date_time": end_time,
        }

        try:
            response = requests.get(self.api_url, headers=self.get_headers(), params=params, timeout=120)
            response.raise_for_status()
            all_data = response.json().get("data", [])
            # Filter out logger data (keep only weather data)
            filtered_data = [
                entry for entry in all_data 
                if not str(entry.get("sensor_sn", "")).startswith("2216865")
            ]
            return filtered_data
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch weather data: {e}")
            return []

if __name__ == "__main__":
    # Example usage for testing: fetch and print weather data
    service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
    data = service.get_weather_data()

    for entry in data:
        print(entry)