# This file defines the QualityService class for fetching water quality data from an external API.
# It handles API authentication, paginated data retrieval, and time range management.

import requests, sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
from config import Config
from datetime import datetime, timezone


def describe_request_error(e):
    """A short description of a failed request that is safe to log: the error type and HTTP status only.
    WQData takes its key as the apiKey query parameter, and requests' own error text includes the full
    URL, so printing the exception itself would write the key into the logs."""
    status = getattr(getattr(e, "response", None), "status_code", None)
    return f"{type(e).__name__} (HTTP {status})" if status else type(e).__name__

def merge_point(points, point):
    """Add a WQData point to  (timestamp -> point). A timestamp seen before (a point split across two
    pages) gets the values it didn't have yet, by parameterId, instead of a second entry."""
    ts = point.get("timestamp")
    seen = points.get(ts)
    if seen is None:
        points[ts] = {**point, "values": list(point.get("values") or [])}
        return
    have = {v.get("parameterId") for v in seen["values"]}
    seen["values"].extend(v for v in point.get("values") or [] if v.get("parameterId") not in have)


class QualityService:
    MAX_PAGES = 100        # about 500,000 values; a catch-up longer than that finishes on later runs
    PAGE_PAUSE_S = 3.5     # seconds between page requests

    def __init__(self, api_url, api_key, device_id):
        # Initialize with API URL, key, and device ID
        self.api_url = api_url
        self.api_key = api_key
        self.device_id = device_id
        self.sleep = time.sleep

    def get_headers(self):
        # WQData uses apiKey in query params, not headers
        return {}  

    def get_default_time_range(self):
        # Returns a default time range for data queries
        now = datetime.now(timezone.utc)
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")
        # Adjust this to fit your project-specific time range
        start_time = "2025-05-08 11:00:00" # start_time = "2025-05-08 11:00:00"
        return start_time, end_time

    def get_quality_data(self, start_time=None, end_time=None):
        """Every WQData point from start_time to end_time (UTC, "%Y-%m-%d %H:%M:%S"), following WQData's paging.

        A response cut off part-way gives the time of its last point (info.lastDataPointTimestamp), and the next
        request starts at that point, not after it, so a point whose values were split between two pages is read
        whole: repeats of a timestamp are merged. info.more isn't reliable on its own (a 14-day request said
        more=false on its 4th page with count 6,963 of total 12,591), so paging stops only once a response holds
        every value it says its range has (info.count >= info.total). A failed request ends the paging with what
        was read so far, as does hitting MAX_PAGES; both are logged.
        """
        if not start_time or not end_time:
            start_time, end_time = self.get_default_time_range()

        url = f"{self.api_url}/devices/{self.device_id}/parameters/data"
        points = {}   # timestamp -> point, in the order received
        current_start = start_time

        for page in range(self.MAX_PAGES):
            if page:
                self.sleep(self.PAGE_PAUSE_S)   # WQData throttles bursts of requests
            params = {"apiKey": self.api_key, "from": current_start, "to": end_time}
            try:
                response = requests.get(url, params=params, timeout=(10, 120))
                response.raise_for_status()
                body = response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                print(f"[ERROR] Failed to fetch quality data from {current_start} UTC: {describe_request_error(e)}")
                break

            for point in body.get("data") or []:
                merge_point(points, point)

            info = body.get("info") or {}
            count, total = info.get("count"), info.get("total")
            if not info.get("more") and (count is None or total is None or count >= total):
                break
            last = info.get("lastDataPointTimestamp")
            if not last or last <= current_start:   # same fixed format, so string order is time order
                print(f"[ERROR] WQData paging didn't advance past {current_start} UTC "
                      f"(count {count}, total {total}); stopping with what was read")
                break
            current_start = last
        else:
            print(f"[WARN] WQData: stopped after {self.MAX_PAGES} pages at {current_start} UTC; "
                  "the rest of the range is fetched next run")

        return list(points.values())

if __name__ == "__main__":
    # Example usage for testing: fetch and print water quality data
    service = QualityService(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)

    data = service.get_quality_data()

    for entry in data:
        print(entry)