-- Tables for welldash², the VPN-only operations dashboard (dashboard/backend/app/ops/; the README's "welldash²" section).
--
-- request_metrics: the API's traffic per minute, per (route pattern, method, status class), written by the backend
-- (utils/traffic.py). The route pattern, never the path's values, query string, client address or user agent.
-- latency_buckets counts requests per latency range (bounds in utils/traffic.py, LATENCY_BUCKETS_MS), so a p95 can
-- be estimated over any period.
-- uptime_probes: one row per check of the dashboard and the WordPress site by the ops service, once a minute.
--
-- The ops service deletes rows older than 90 days from both (OPS_RETENTION_DAYS), once a day. Both tables are new,
-- so nothing else is touched or locked. They are created only here, not by db.create_all() (db/models.py), since
-- the integer[] column is PostgreSQL's.
CREATE TABLE IF NOT EXISTS request_metrics (
    minute          timestamptz NOT NULL,
    endpoint        varchar(128) NOT NULL,
    method          varchar(8) NOT NULL,
    status_class    smallint NOT NULL,        -- 2 for 2xx, 3, 4, 5
    requests        integer NOT NULL,
    total_ms        double precision NOT NULL,
    max_ms          double precision NOT NULL,
    latency_buckets integer[] NOT NULL,
    bytes_out       bigint NOT NULL,
    PRIMARY KEY (minute, endpoint, method, status_class)
);

CREATE TABLE IF NOT EXISTS uptime_probes (
    id          bigserial PRIMARY KEY,
    checked_at  timestamptz NOT NULL,
    target      varchar(32) NOT NULL,         -- "dashboard" or "wordpress"
    ok          boolean NOT NULL,
    status      integer,                      -- HTTP status; NULL when there was no answer
    latency_ms  double precision,
    error       varchar(64)                   -- the exception type when there was no answer
);

CREATE INDEX IF NOT EXISTS ix_uptime_probes_target_checked_at ON uptime_probes (target, checked_at);
CREATE INDEX IF NOT EXISTS ix_uptime_probes_checked_at ON uptime_probes (checked_at);
