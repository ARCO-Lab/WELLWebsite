# This file defines the shared Flask-SQLAlchemy instance (db), bound to the app in server.py, and the engine options
# every process uses. The 'db' object is used throughout the project for ORM operations.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def engine_options(uri, statement_timeout_ms=0, application_name=None):
    """SQLALCHEMY_ENGINE_OPTIONS for a database URI.

    pool_pre_ping checks a pooled connection before use, so one that PostgreSQL closed (a restart, an idle
    timeout) is replaced instead of failing a request. A positive statement_timeout_ms is passed to PostgreSQL
    when each connection opens, so it applies to every statement of this engine; SQLite (tests) has no such
    setting and gets none. application_name names the connections in PostgreSQL (pg_stat_activity), so it shows
    which container holds them."""
    options = {"pool_pre_ping": True}
    if not (uri or "").startswith("postgresql"):
        return options
    connect_args = {}
    if statement_timeout_ms > 0:
        connect_args["options"] = f"-c statement_timeout={int(statement_timeout_ms)}"
    if application_name:
        connect_args["application_name"] = application_name
    if connect_args:
        options["connect_args"] = connect_args
    return options
