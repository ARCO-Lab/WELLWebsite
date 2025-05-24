# app.py
from flask import Flask
from flask_cors import CORS
from routes import register_routes

def create_app():
    app = Flask(__name__)
    CORS(app)
    register_routes(app)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
