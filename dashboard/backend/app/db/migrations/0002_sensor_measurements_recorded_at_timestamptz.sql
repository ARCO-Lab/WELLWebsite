-- Store sensor_measurements.recorded_at as a real instant (timestamptz) instead of naive Toronto wall-clock time.
--
-- Why: when clocks fall back, 01:00-01:59 happens twice. As naive wall time both hours had the same recorded_at,
-- so the unique key (station_id, measurement_type, recorded_at) kept the first hour and dropped the second
-- (e.g. 2026-11-01 01:00 has 48 Logger rows, not 96). As instants the two hours differ and both can be stored.
--
-- How the existing naive values are converted (each value meant America/Toronto wall time):
--  * Ordinary times: the one instant they name.
--  * The repeated hour (01:00-01:59 on the fall-back night): the stored rows are the FIRST hour (EDT, UTC-4).
--    Ingestion inserted the EDT readings first and ON CONFLICT dropped the EST ones that came an hour later;
--    the stored values confirm it (on 2026-11-01 the water temperature runs smoothly from 00:50 to 01:50 and then
--    jumps at 02:00 EST, an hour of readings later). Plain `recorded_at AT TIME ZONE 'America/Toronto'` would
--    pick the SECOND hour: PostgreSQL gives an ambiguous time the offset in force just after the change (EST).
--    So each value is converted twice, as itself and as an hour earlier plus that hour, and the earlier instant
--    is kept. The two agree for every time except the repeated hour, where the second one is the EDT reading.
--  * The skipped hour (02:00-02:59 on the spring-forward night) can't hold a reading, and production has none.
--    Should one exist, PostgreSQL reads it with the offset before the change (02:30 -> 07:30 UTC = 03:30 EDT),
--    and so does LEAST here.
-- The site zone is named, so the result doesn't depend on the database's TimeZone setting.
--
-- The unique constraint and the indexes on recorded_at (the constraint's index and
-- ix_sensor_measurements_group_type_recorded_at from 0001) are rebuilt by the ALTER and keep their names.
--
-- Locking: ALTER ... TYPE rewrites the table and its indexes under an ACCESS EXCLUSIVE lock: nothing can read
-- or write sensor_measurements until it commits. Measured on a copy of production's size (1.45 M rows, 150 MB
-- table, PostgreSQL 13): see the pull request; it is seconds, not minutes. Stop the worker and the backend first
-- (the deploy steps say how), so nothing queues behind the lock; lock_timeout makes the migration fail rather
-- than wait if something still holds the table.
--
-- A database created after this change (db/init_db.py) already has timestamptz, so this does nothing there:
-- converting a timestamptz column with this USING expression would shift it.
--
-- Rollback: db/migrations/down/0002_sensor_measurements_recorded_at_timestamptz.sql (its comments say how).
SET LOCAL lock_timeout = '10s';

DO $$
BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'sensor_measurements'
          AND column_name = 'recorded_at') = 'timestamp without time zone' THEN
        ALTER TABLE sensor_measurements
            ALTER COLUMN recorded_at TYPE timestamptz
            USING LEAST(recorded_at AT TIME ZONE 'America/Toronto',
                        ((recorded_at - interval '1 hour') AT TIME ZONE 'America/Toronto') + interval '1 hour');
    END IF;
END
$$;
