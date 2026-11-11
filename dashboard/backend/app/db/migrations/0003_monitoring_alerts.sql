-- State for the worker's email alerts (scripts/check_alerts.py; the README's Monitoring section says what they are).
--
-- vendor_status: the outcome of the latest LI-COR and WQData call, one row per source, written by every ingestion
-- run. It lets an alert tell "the vendor API is down" apart from "the vendor answers, but a sensor sent nothing".
-- alert_incidents: one row per alert condition, from when it is first seen until it clears, so each condition is
-- emailed once (then reminded about at most once a day) and its recovery once. At most one open row per key.
--
-- Both tables are new, so nothing else is touched or locked. db/models.py defines the same tables, for databases
-- built by db.create_all(); IF NOT EXISTS makes this a no-op there.
CREATE TABLE IF NOT EXISTS vendor_status (
    source               varchar(32) PRIMARY KEY,
    last_attempt_at      timestamptz NOT NULL,
    last_success_at      timestamptz,
    last_failure_at      timestamptz,
    failing_since        timestamptz,
    consecutive_failures integer NOT NULL DEFAULT 0,
    last_error_kind      varchar(32),
    last_http_status     integer,
    last_error           text
);

CREATE TABLE IF NOT EXISTS alert_incidents (
    id                   serial PRIMARY KEY,
    incident_key         varchar(255) NOT NULL,
    kind                 varchar(32) NOT NULL,
    title                text NOT NULL,
    detail               text NOT NULL,
    started_at           timestamptz NOT NULL,
    opened_at            timestamptz NOT NULL,
    last_seen_at         timestamptz NOT NULL,
    last_notified_at     timestamptz,
    notifications        integer NOT NULL DEFAULT 0,
    resolved_at          timestamptz,
    close_reason         varchar(16),
    reopened_at          timestamptz,
    back_again_at        timestamptz,
    recovery_notified_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_incidents_open_key ON alert_incidents (incident_key)
    WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_alert_incidents_resolved_at ON alert_incidents (resolved_at);
