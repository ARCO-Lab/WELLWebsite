# This file defines the WeatherService class for fetching readings from the LI-COR Cloud (formerly HOBOlink) API:
# the weather station and the water-level loggers. It handles the token, one request per time window, and retries;
# utils/fetching.fetch_range splits longer periods into windows. LI-COR times are UTC.

import requests, sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
from utils.fetching import MAX_RECORDS, BadVendorResponse
from datetime import timedelta, timezone

def page_records(body):
    """(records, capped) from a LI-COR reply. A reply without a "data" list (not a JSON object, "data" missing,
    null or not a list) raises BadVendorResponse instead of reading as an empty page, so an error body that comes
    back with HTTP 200, or a changed format, fails the run (and is reported, and the alerts say "vendor problem"
    rather than "vendor OK, check the sensor") rather than looking like a quiet period with no readings.
    A reply of MAX_RECORDS or more counts as capped even without the "max_results" flag, so a renamed or dropped
    flag can't make a truncated reply look complete."""
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        keys = sorted(body)[:10] if isinstance(body, dict) else type(body).__name__   # field names only, never values
        raise BadVendorResponse(f"LI-COR reply has no 'data' list (got {keys})")
    return body["data"], bool(body.get("max_results")) or len(body["data"]) >= MAX_RECORDS


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
        # The station serial sent as LI-COR's "loggers" parameter: the first in HOBOLINK_LOGGERS. One request
        # returns the weather sensors and the water-level loggers together.
        return self.logger_ids[0]

    def get_page(self, start, end):
        """One request for [start, end) (aware datetimes): (all records, whether LI-COR capped the response).

        It returns every sensor (weather and loggers), reports the cap
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
