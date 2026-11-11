# This file initializes and configures the Flask application for the WELL backend.
# It sets up CORS, registers all API routes, and integrates the database.

from config import Config  # loads .env, so SENTRY_DSN is set before init_sentry reads it
from utils.sentry import capture_job_error, init_sentry

# Report errors to Sentry when SENTRY_DSN is set (utils/sentry.py); before the app and its routes are created.
# Tagged "backend" unless SENTRY_COMPONENT says otherwise (docker-compose.yml sets it for worker and export_worker,
# whose scripts import this module).
init_sentry("backend")

from flask import Flask, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from api.routes import register_routes  # noqa: E402
from api.routes.health import register_health_routes  # noqa: E402
from db.database import db, engine_options  # noqa: E402
from utils.traffic import init_request_metrics  # noqa: E402

# PostgreSQL's error code for a statement it cancelled, here because it ran past DB_STATEMENT_TIMEOUT_MS.
QUERY_CANCELED = "57014"
TOO_MANY_CONNECTIONS = "53300"


def is_connection_error(exc):
    """Whether a database error means the database couldn't be reached: the connection was lost, it failed
    before PostgreSQL sent an error code, a connection-class (08xxx) error, or too many connections."""
    code = getattr(exc.orig, "pgcode", None)
    return bool(exc.connection_invalidated) or code is None or code.startswith("08") or code == TOO_MANY_CONNECTIONS


def create_app():
    # Create and configure the Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options(
        app.config["SQLALCHEMY_DATABASE_URI"], app.config["DB_STATEMENT_TIMEOUT_MS"])
    db.init_app(app)
    CORS(app)
    register_routes(app)
    # Per-minute request counts for welldash² and the daily digest (utils/traffic.py); route patterns only, no
    # addresses or query strings. On by default with PostgreSQL; REQUEST_METRICS=0 turns it off.
    init_request_metrics(app)

    # Database errors answer with a short JSON error the dashboard can show, instead of a 500 and a traceback.
    # A query cut off by the statement timeout (a slow range) or a lost connection (a database restart) isn't a
    # bug, so it is only logged. Anything else, such as a deadlock or a full disk, also goes to Sentry, throttled
    # like the worker's job errors.
    @app.errorhandler(OperationalError)
    def database_error(exc):
        code = getattr(exc.orig, "pgcode", None)
        where = f"{request.method} {request.path}"
        if code == QUERY_CANCELED:
            app.logger.warning("%s: query cancelled by the statement timeout", where)
            return jsonify({"error": "The database took too long to answer. Pick a shorter range or fewer sensor "
                                     "groups, or try again in a minute."}), 504
        if is_connection_error(exc):
            app.logger.warning("%s: database unreachable: %s", where, type(exc.orig).__name__)
            return jsonify({"error": "The data service can't reach its database right now. Please try again "
                                     "shortly."}), 503
        app.logger.error("%s: database error %s (%s)", where, code, type(exc.orig).__name__)
        capture_job_error(exc, source="api")
        return jsonify({"error": "The data service hit a database error. Please try again shortly."}), 503

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