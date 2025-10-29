# This file initializes and configures the Flask application for the WELL backend.
# It sets up CORS, registers all API routes, and integrates the database.

from flask import Flask
from flask_cors import CORS
from api.routes import register_routes
from db.database import db
from config import Config

def create_app():
    # Create and configure the Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    CORS(app)
    register_routes(app)

    @app.route('/health')
    def health():
        return {"status": "ok", "message": "Backend is running"}, 200

    return app

# Expose a module-level WSGI app for Gunicorn
app = create_app()

if __name__ == "__main__":
    # Run the Flask app in debug mode DEV ONLY
    app.run(debug=True, host="0.0.0.0", port=5000)