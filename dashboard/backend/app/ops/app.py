"""welldash²'s Flask app: five read-only pages behind one login. gunicorn runs create_app() (docker-compose.yml).

The pages: / (overview), /uptime, /traffic, /system and /visitors, all GET. /login and /logout are the only
routes that accept POST, and the only ones besides /static that work without a session (ops/auth.py).
"""
import logging
import sys
from datetime import datetime, timezone

from flask import Flask, render_template, request
from sqlalchemy import create_engine

from db.database import engine_options
from ops import data, external
from ops.auth import install_auth
from ops.charts import bar_chart, line_chart, responsive
from ops.probe import TARGET_LABELS, Prober
from ops.settings import SESSION_LIFETIME, ConfigError, load_settings
from utils.timezone import EST_TZ
from utils.traffic import fmt_bytes

log = logging.getLogger("ops")

STATEMENT_TIMEOUT_MS = 20000
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'none'; object-src 'none'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def site_time(ts, with_date=True):
    if ts is None:
        return "never"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    ts = ts if ts.tzinfo else ts.replace(tzinfo=EST_TZ)   # naive times in this database are site time
    return f"{ts.astimezone(EST_TZ):%Y-%m-%d %H:%M}" if with_date else f"{ts.astimezone(EST_TZ):%H:%M}"


def ago(ts, now=None):
    if ts is None:
        return "never"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    ts = ts if ts.tzinfo else ts.replace(tzinfo=EST_TZ)
    minutes = int(((now or datetime.now(timezone.utc)) - ts).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 120:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h ago"
    return f"{minutes / 1440:.1f} days ago"


def pct(value):
    # A no-break space, so a narrow table cell doesn't put the % on a line of its own
    return "n/a" if value is None else f"{value:.2f}\u00a0%" if value < 100 else "100\u00a0%"


def ms(value):
    if value is None:
        return "n/a"
    return f"{value:.0f} ms" if value < 1000 else f"{value / 1000:.1f} s"


def create_app(env=None, engine=None, start_background=True):
    """The app. Raises ConfigError (after logging why) when the password hash, secret key or database is missing,
    so gunicorn exits instead of serving an unprotected dashboard."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout)
    try:
        settings = load_settings(env)
    except ConfigError as e:
        log.critical("welldash² not started: %s", e)
        raise
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_NAME="welldash2_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        PERMANENT_SESSION_LIFETIME=SESSION_LIFETIME,
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=16 * 1024,   # the login form is all that is ever posted
    )
    # Every statement is cut off after 20 s (engine_options), so a slow page can't hold a connection for long.
    engine = engine or create_engine(settings.database_url, pool_size=3, max_overflow=2,
                                     **engine_options(settings.database_url, STATEMENT_TIMEOUT_MS))
    app.extensions["ops_engine"] = engine
    app.extensions["ops_settings"] = settings
    install_auth(app, settings)
    app.jinja_env.filters.update(site_time=site_time, ago=ago, pct=pct, ms=ms, bytes=fmt_bytes)
    app.jinja_env.globals["target_labels"] = TARGET_LABELS
    started_at = datetime.now(timezone.utc)

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    def page(template, **context):
        return render_template(template, now=datetime.now(timezone.utc), active=request.endpoint, **context)

    @app.route("/")
    def overview():
        now = datetime.now(timezone.utc)
        return page("overview.html",
                    probes=data.section(engine, data.latest_probes),
                    freshness=data.section(engine, data.freshness, now),
                    alerts=data.section(engine, data.alerts, now),
                    vendors=data.section(engine, data.vendors),
                    deploys=data.deploys(settings.logs_dir),
                    ci=external.github_ci(settings),
                    sentry=external.sentry_issues(settings),
                    healthchecks=external.healthchecks(settings))

    @app.route("/uptime")
    def uptime():
        now = datetime.now(timezone.utc)
        range_name = data.pick_range(request.args.get("range", ""))
        latency = data.section(engine, data.latency_series, now, range_name)
        chart = None
        if "error" not in latency:
            series = [{"name": target, "cls": f"s{i}", "points": [(t, avg) for t, avg, _, _ in points]}
                      for i, (target, points) in enumerate(sorted(latency["series"].items()))]
            chart = responsive(line_chart, series, latency["start"], latency["end"], ms, "Average response time",
                               wide=True)
            failed = [(t, n - ok) for points in latency["series"].values() for t, _, n, ok in points if n - ok]
            latency["failed_checks"] = sum(f for _, f in failed)
        return page("uptime.html", range_name=range_name, ranges=data.RANGES,
                    availability=data.section(engine, data.availability, now),
                    latency=latency, latency_chart=chart,
                    incidents=data.section(engine, data.incidents, now))

    @app.route("/traffic")
    def traffic():
        now = datetime.now(timezone.utc)
        range_name = data.pick_range(request.args.get("range", ""))
        summary = data.section(engine, data.traffic_summary, now, range_name)
        series = data.section(engine, data.traffic_series, now, range_name)
        charts = {}
        if "error" not in series:
            pts, start, end, step = series["points"], series["start"], series["end"], series["step"]
            count = lambda v: f"{v:,.0f}"   # noqa: E731
            def bars(key, fmt, label, cls="bar"):
                return responsive(bar_chart, [(p["t"], p[key]) for p in pts], start, end, step, fmt, label, cls)
            charts = {
                "requests": bars("requests", count, "Requests"),
                "errors": bars("errors", count, "Server errors", "bar bad"),
                "p95": responsive(line_chart, [{"name": "p95", "cls": "s0",
                                                "points": [(p["t"], p["p95_ms"]) for p in pts]}],
                                  start, end, ms, "p95 response time"),
                "bytes": bars("bytes_out", fmt_bytes, "Data sent"),
                "peak": bars("peak", count, "Busiest minute (requests per minute)"),
                "downloads": bars("downloads", count, "CSV downloads"),
            }
        return page("traffic.html", range_name=range_name, ranges=data.RANGES, summary=summary, series=series,
                    charts=charts, step=data.RANGES[range_name][2],
                    exports=data.section(engine, data.export_jobs, now, range_name))

    @app.route("/system")
    def system():
        return page("system.html",
                    database=data.section(engine, data.database),
                    migrations=data.section(engine, data.migrations),
                    logs=data.log_files(settings.logs_dir),
                    probes=data.section(engine, data.latest_probes),
                    started_at=started_at, settings=settings)

    @app.route("/visitors")
    def visitors():
        return page("visitors.html", goatcounter=external.goatcounter(settings))

    if start_background:
        Prober(engine, settings).start()
    return app
