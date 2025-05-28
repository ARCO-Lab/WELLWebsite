from flask import jsonify
from api.services import WeatherService
from config import Config

weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)

def register_routes(app):
    app.add_url_rule("/api/weather", "get_weather", lambda: jsonify(weather_service.get_weather_data()))
