from flask import jsonify
from services import get_weather_data
#, get_water_quality_data

def get_weather():
    data = get_weather_data()
    return jsonify(data)
"""
def get_water_quality():
    data = get_water_quality_data()
    return jsonify(data)
"""