# This file initializes and configures the Flask application for the WELL backend.
# It sets up CORS, registers all API routes, and integrates the database.

from flask import Flask
from flask_cors import CORS
from api.routes import register_routes
from api.routes.health import register_health_routes
from db.database import db
from db.models import check_schema
from config import Config

def create_app():
    # Create and configure the Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    # Before serving anything: this code reads recorded_at as instants, so it must not run on the pre-0002
    # schema, where it would show every reading time 4-5 hours off. Raises (the process doesn't start) if so.
    check_schema(app.config.get("SQLALCHEMY_DATABASE_URI"), app.config.get("SQLALCHEMY_ENGINE_OPTIONS"),
                 log=app.logger.warning)
    db.init_app(app)
    CORS(app)
    register_routes(app)

    @app.route('/health')
    def health():
        return {"status": "ok", "message": "Backend is running"}, 200

    # Registered next to /health rather than in api/routes, since it is a health check, not data API.
    register_health_routes(app)

    return app

# Expose a module-level WSGI app for Gunicorn
app = create_app()

if __name__ == "__main__":
    # Run the Flask app in debug mode DEV ONLY
    app.run(debug=True, host="0.0.0.0", port=5000)