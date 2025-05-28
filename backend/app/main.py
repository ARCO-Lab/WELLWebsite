from flask import Flask
from flask_cors import CORS
from api.routes import register_routes
from db.database import db
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    CORS(app)
    register_routes(app)
    return app
