# This file defines the shared Flask-SQLAlchemy instance (db), bound to the app in server.py, and the engine options
# every process uses. The 'db' object is used throughout the project for ORM operations.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# libpq settings for every PostgreSQL connection. A database that drops packets (as when the VM's firewall rule for
# Docker lost its port 5432 rule in October 2026) otherwise holds each connection attempt for about two minutes of
# TCP retries, and an established connection for far longer: every API thread blocks and /health stalls behind
# them. With these an attempt fails after 5 s, and a connection whose peer stopped answering after about a minute
# (30 s idle, then 3 probes 10 s apart).
CONNECT_ARGS = {"connect_timeout": 5, "keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10,
                "keepalives_count": 3}


def engine_options(uri, statement_timeout_ms=0, application_name=None):
    """SQLALCHEMY_ENGINE_OPTIONS for a database URI.

    pool_pre_ping checks a pooled connection before use, so one that PostgreSQL closed (a restart, an idle
    timeout) is replaced instead of failing a request. PostgreSQL connections get CONNECT_ARGS (a connect timeout
    and TCP keepalives). A positive statement_timeout_ms is passed to PostgreSQL when each connection opens, so it
    applies to every statement of this engine; SQLite (tests) has no such setting and gets none of these.
    application_name names the connections in PostgreSQL (pg_stat_activity), so it shows which container holds
    them."""
    options = {"pool_pre_ping": True}
    if not (uri or "").startswith("postgresql"):
        return options
    connect_args = dict(CONNECT_ARGS)
    if statement_timeout_ms > 0:
        connect_args["options"] = f"-c statement_timeout={int(statement_timeout_ms)}"
    if application_name:
        connect_args["application_name"] = application_name
    options["connect_args"] = connect_args
    return options
