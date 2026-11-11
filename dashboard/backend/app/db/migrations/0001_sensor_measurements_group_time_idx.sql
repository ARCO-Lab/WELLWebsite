-- migrate: no-transaction
-- Index for the queries that filter sensor_measurements by group_type and a recorded_at range: the ingestion's
-- newest reading per group (every 10 minutes), /api/data's count and rows, and exports. Without it each of them
-- scans the whole table, because its only index is the unique key (station_id, measurement_type, recorded_at).
--
-- CONCURRENTLY builds the index without blocking inserts or reads, so nothing has to stop while it runs; it
-- can't run inside a transaction, hence the first line. If the build fails part way, PostgreSQL leaves an
-- INVALID index behind that IF NOT EXISTS would then skip: drop it with
-- DROP INDEX CONCURRENTLY ix_sensor_measurements_group_type_recorded_at; and run the migration again.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sensor_measurements_group_type_recorded_at
    ON sensor_measurements (group_type, recorded_at);
