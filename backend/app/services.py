import requests
from config import Config
from datetime import datetime, timedelta, timezone

hobo_api_url = Config.HOBO_API_URL
hobo_api_token = Config.HOBO_API_TOKEN
hobo_loggers = Config.HOBO_LOGGERS

def get_weather_data(start_time=None, end_time=None):
    """
    Fetch weather data from the API.
    """
    if not start_time or not end_time:
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        end_time=now.strftime("%Y-%m-%d %H:%M:%S")
        # weather station down so current all time start:"2025-05-09 15:20:00" all time end: "2025-05-21 12:15:00"
        start_time = "2025-05-21 00:15:00" #12 hours less than last input
        end_time = "2025-05-21 12:15:00"
    weather_logger = hobo_loggers.split(",")[0]

    headers = {
        "Authorization": f"Bearer {hobo_api_token}"
    }

    params = {
        "loggers": weather_logger,
        "start_date_time": start_time,
        "end_date_time": end_time,
    }

    try:
        response = requests.get(hobo_api_url,headers=headers, params=params)
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


# Need to filter data based on data needed to be omit