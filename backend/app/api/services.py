import requests, sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from config import Config
from datetime import datetime, timedelta, timezone

class WeatherService:
    def __init__(self, api_url, api_token, logger_ids):
        self.api_url = api_url
        self.api_token = api_token
        self.logger_ids = logger_ids.split(",")

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_token}"
        }

    def get_logger_id(self):
        return self.logger_ids[0]  # Extendable later

    def get_weather_data(self, start_time=None, end_time=None):
        if not start_time or not end_time:
            now = datetime.now(timezone.utc)
            # Temporary override: 
            # Current all time as of May 27,2025:
            # Start time is 2025-05-09 15:20:00
            # End time is 2025-05-21 12:15:00
            start_time = "2025-05-21 12:02:30"
            end_time = "2025-05-21 12:12:30"


        params = {
            "loggers": self.get_logger_id(),
            "start_date_time": start_time,
            "end_date_time": end_time,
        }

        try:
            response = requests.get(self.api_url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch weather data: {e}")
            return []

if __name__ == "__main__":
    service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
    data = service.get_weather_data()

    for entry in data:
        print(entry)


# Need to filter data based on data needed to be omit