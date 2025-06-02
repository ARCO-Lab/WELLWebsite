import requests, sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))
from config import Config
from datetime import datetime, timezone, timedelta

class QualityService:
    def __init__(self, api_url, api_key, device_id):
        self.api_url = api_url
        self.api_key = api_key
        self.device_id = device_id

    def get_headers(self):
        return {}  # WQData uses apiKey in query params, not headers

    def get_default_time_range(self):
        now = datetime.now(timezone.utc)
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")
        # Adjust this to fit your project-specific time range
        start_time = "2025-05-08 11:00:00"
        return start_time, end_time

    def get_quality_data(self, start_time=None, end_time=None):
        if not start_time or not end_time:
            start_time, end_time = self.get_default_time_range()

        url = f"{self.api_url}/devices/{self.device_id}/parameters/data"
        all_data = []
        current_start = start_time

        iteration = 0
        max_iterations = 100
        last_ts = None

        while iteration < max_iterations:
            params = {
                "apiKey": self.api_key,
                "from": current_start,
                "to": end_time
            }

            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                json_data = response.json()

                data_batch = json_data.get("data", [])
                if not data_batch:
                    break

                all_data.extend(data_batch)

                info = json_data.get("info", {})
                last_ts_str = info.get("lastDataPointTimestamp")
                if last_ts_str:
                    last_ts = datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S")

                if not info.get("more"):
                    break

                # Prepare for next iteration
                current_start = (last_ts + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Failed to fetch quality data: {e}")
                break

            iteration += 1

        # ✅ Final tail-fetch to capture any leftovers
        if last_ts:
            final_params = {
                "apiKey": self.api_key,
                "from": (last_ts + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"),
                "to": end_time
            }
            try:
                tail_response = requests.get(url, params=final_params)
                tail_response.raise_for_status()
                final_data = tail_response.json().get("data", [])
                all_data.extend(final_data)
            except Exception as e:
                print(f"[WARN] Tail fetch failed: {e}")

        return all_data

if __name__ == "__main__":
    service = QualityService(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)

    data = service.get_quality_data()

    for entry in data:
        print(entry)