# This file defines GET /health/data: whether every live series is still receiving readings, for an external
# uptime monitor. 200 when they all are, 503 with the stale series otherwise (the rules and their env settings
# are in utils/monitoring.py). It reuses /api/latest's per-series index walk, so it costs one index probe or
# two per series and can be polled every few minutes. It also lists the open email alerts and the latest vendor API
# outcomes (scripts/check_alerts.py) under "alerts", so the dashboard can show them; they don't change the status code.

from datetime import datetime, timezone

from flask import jsonify

from api.routes.latest import latest_rows
from db.database import db
from utils.alert_state import alerts_report
from utils.monitoring import assess_freshness


def register_health_routes(app):
    @app.route("/health/data", methods=["GET"])
    def health_data():
        now = datetime.now(timezone.utc)
        try:
            report = assess_freshness(latest_rows(), now)   # aware instants, so the repeated fall-back hour reads right
        except ValueError as e:   # a bad HEALTH_* setting; red, so someone looks
            return jsonify({"status": "error", "error": f"bad monitoring setting: {e}"}), 503
        except Exception as e:    # database unreachable, etc.; the type only, never connection details
            app.logger.exception("/health/data failed")
            return jsonify({"status": "error", "error": f"could not read the data: {type(e).__name__}"}), 503
        try:
            report["alerts"] = alerts_report()
        except Exception as e:   # e.g. the alert tables' migration hasn't run yet; the freshness report still counts
            db.session.rollback()
            report["alerts"] = {"error": f"could not read the alerts: {type(e).__name__}"}
        response = jsonify(report)
        response.status_code = 200 if report["status"] == "ok" else 503
        response.headers["Cache-Control"] = "no-store"
        return response
