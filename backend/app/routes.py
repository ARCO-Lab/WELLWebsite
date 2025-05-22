@app.route("/api/weather")
def get_weather():
    data = get_weather_data()  # from services.py
    return jsonify(data)

@app.route("/api/water_quality")
def get_water_quality():
    data = get_water_quality_data()  # from services.py
    return jsonify(data)            