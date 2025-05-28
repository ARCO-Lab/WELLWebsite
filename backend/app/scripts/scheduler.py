from inject_from_api import inject_weather_data

if __name__ == "__main__":
    print("[INFO] Starting weather data injection...")
    try:
        inject_weather_data()
    except Exception as e:
        print(f'[ERROR] An error occurred during injection: {e}')
