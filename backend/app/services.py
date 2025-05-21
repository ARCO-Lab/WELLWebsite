import requests
from config import Config
from datetime import datetime, timedelta, timezone

api_url = Config.API_URL
api_token = Config.API_TOKEN
loggers = Config.LOGGERS

def get_weather_data(start_time=None, end_time=None):
    """
    Fetch weather data from the API.
    """
    if not start_time or not end_time:
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        end_time=now.strftime("%Y-%m-%d %H:%M:%S")

    weather_logger = loggers.split(",")[0]

    headers = {
        "Authorization": f"Bearer {api_token}"
    }

    params = {
        "loggers": weather_logger,
        "start_date_time": start_time,
        "end_date_time": end_time,
    }

    try:
        response = requests.get(api_url,headers=headers, params=params)
        response.raise_for_status()
        data= response.json()

        return data.get("data",[])
    
    except requests.exceptions.RequestException as e:
        print (f"[ERROR] Failed to fetch weather data: {e}")
        return []

if __name__ == "__main__":
    weather_data = get_weather_data()
    for entry in weather_data:
        print(entry)