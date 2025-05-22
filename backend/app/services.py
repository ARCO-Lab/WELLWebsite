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

def get_water_quality_data(start_time=None, end_time=None):
    """
    Fetch water quality data from the WQData LIVE API.
    """

    # Step 1: Default time range = last 12 hours
    if not start_time or not end_time:
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    # Step 2: Prepare API URL and parameters
    device_id = Config.WQDATA_DEVICE_ID
    api_key = Config.WQDATA_API_KEY
    base_url = Config.WQDATA_BASE_URL

    # For now, fetch all parameters
    url = f"{base_url}/devices/{device_id}/parameters/data"
    params = {
        "apiKey": api_key,
        "from": start_time,
        "to": end_time
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch water quality data: {e}")
        return []

if __name__ == "__main__":
    weather_data = get_weather_data()
    for entry in weather_data:
        print(entry)
    water_data = get_water_quality_data()
    for row in water_data:
        print(row)

# Need to filter data based on data needed to be omit