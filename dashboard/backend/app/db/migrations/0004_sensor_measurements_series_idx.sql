-- migrate: no-transaction
-- Covering index for /api/series when a chart asks for its own series only (series=, station_id=,
-- measurement_type=): the scan goes straight to those series' readings in the time range, and INCLUDE (value) lets
-- PostgreSQL answer from the index alone (an index-only scan, once the table is vacuumed) instead of visiting each
-- row. A chart's tile is ~360 buckets of a few series, so this keeps each request to a small slice of the table.
--
-- CONCURRENTLY builds the index without blocking inserts or reads; it can't run inside a transaction, hence the
-- first line. If the build fails part way, PostgreSQL leaves an INVALID index behind that IF NOT EXISTS would then
-- skip: drop it with DROP INDEX CONCURRENTLY ix_sensor_measurements_series_time; and run the migration again.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sensor_measurements_series_time
    ON sensor_measurements (group_type, station_id, measurement_type, recorded_at) INCLUDE (value);
