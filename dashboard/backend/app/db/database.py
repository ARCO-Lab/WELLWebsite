# This file initializes the SQLAlchemy database instance for use with Flask.
# The 'db' object is used throughout the project for ORM operations.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def engine_options(uri, statement_timeout_ms=0):
    """SQLALCHEMY_ENGINE_OPTIONS for a database URI.

    pool_pre_ping checks a pooled connection before use, so one that PostgreSQL closed (a restart, an idle
    timeout) is replaced instead of failing a request. A positive statement_timeout_ms is passed to PostgreSQL
    when each connection opens, so it applies to every statement of this engine; SQLite (tests) has no such
    setting and gets none."""
    options = {"pool_pre_ping": True}
    if statement_timeout_ms > 0 and (uri or "").startswith("postgresql"):
        options["connect_args"] = {"options": f"-c statement_timeout={int(statement_timeout_ms)}"}
    return options
