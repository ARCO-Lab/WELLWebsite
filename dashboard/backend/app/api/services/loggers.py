# This file defines the LoggerService class for fetching logger data from an external API.
# It handles authentication, parameter formatting, and filtering of logger data.

import requests, sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
from config import Config
from datetime import datetime, timezone

class LoggerService:
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
        return self.logger_ids[0]  # Using the same logger group as weather

    def get_logger_data(self, start_time=None, end_time=None):
        # Fetch logger data from the API, optionally for a time range
        if not start_time or not end_time:
            now = datetime.now(timezone.utc)
            start_time = "2025-07-18 13:40:00" # "2025-07-18 13:40:00"
            end_time = now.strftime("%Y-%m-%d %H:%M:%S") # now.strftime("%Y-%m-%d %H:%M:%S")

        params = {
            "loggers": self.get_logger_id(),
            "start_date_time": start_time,
            "end_date_time": end_time,
        }

        try:
            response = requests.get(self.api_url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            all_data = response.json().get("data", [])
            # Filter for data where sensor_sn starts with '2216865'
            filtered_data = [
                entry for entry in all_data 
                if str(entry.get("sensor_sn", "")).startswith("2216865")
            ]
            return filtered_data
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch logger data: {e}")
            return []

if __name__ == "__main__":
    # Example usage for testing: fetch and print logger data
    service = LoggerService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
    data = service.get_logger_data()

    for entry in data:
        print(entry)