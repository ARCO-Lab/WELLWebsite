# app.py
from flask import Flask, jsonify   
from flask_cors import CORS
from routes import get_weather 
""", get_water_quality"""

app = Flask(__name__)
CORS(app)  # Enables CORS so frontend can access the API

# Register routes manually
app.add_url_rule("/api/weather", "get_weather", get_weather)
#app.add_url_rule("/api/water_quality", "get_water_quality", get_water_quality)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
