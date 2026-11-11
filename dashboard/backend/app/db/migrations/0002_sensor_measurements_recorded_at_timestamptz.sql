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
--  * The skipped hour (02:00-02:59 on the spring-forward night) never appeared on the wall clock, so no reading
--    can have been stored there, and production has none. A row there would be bad data, and converting it
--    could collide with a real reading an hour later, so the migration refuses to run while one exists and
--    names how many; nothing is changed then. (PostgreSQL would read 02:30 as 07:30 UTC, i.e. 03:30 EDT.)
-- The site zone is named, so the result doesn't depend on the database's TimeZone setting.
--
-- The unique constraint and the indexes on recorded_at (the constraint's index and
-- ix_sensor_measurements_group_type_recorded_at from 0001) are rebuilt by the ALTER and keep their names.
--
-- Locking: ALTER ... TYPE rewrites the table and its indexes under an ACCESS EXCLUSIVE lock: nothing can read
-- or write sensor_measurements until it commits. On a table of production's size (1.46 M rows, 131 MB plus its three
-- indexes, PostgreSQL 13 on the production VM) it took 9.4 seconds, so expect 10-15 s. Stop the worker and the
-- backend first (the deploy steps say how), so nothing queues behind the lock; lock_timeout makes the migration
-- fail rather than wait if something still holds the table.
--
-- A database created after this change (db/init_db.py) already has timestamptz, so this does nothing there:
-- converting a timestamptz column with this USING expression would shift it. Any other type (or no such column)
-- stops it with an error, changing nothing.
--
-- Rollback: db/migrations/down/0002_sensor_measurements_recorded_at_timestamptz.sql (its comments say how).
SET LOCAL lock_timeout = '10s';

DO $$
DECLARE
    skipped bigint;
    kind text;
BEGIN
    -- The table the unqualified name resolves to (as the ALTER below), found through the search_path.
    SELECT a.atttypid::regtype::text INTO kind FROM pg_attribute a
    WHERE a.attrelid = to_regclass('sensor_measurements') AND a.attname = 'recorded_at' AND NOT a.attisdropped;
    IF kind IS DISTINCT FROM 'timestamp without time zone' AND kind IS DISTINCT FROM 'timestamp with time zone' THEN
        RAISE EXCEPTION 'sensor_measurements.recorded_at is %, expected timestamp or timestamptz; nothing was changed',
            coalesce(kind, 'missing (no such table or column)');
    END IF;
    IF kind = 'timestamp without time zone' THEN
        LOCK TABLE sensor_measurements IN ACCESS EXCLUSIVE MODE;
        -- A wall time that doesn't survive the round trip to an instant and back is in a skipped hour.
        SELECT count(*) INTO skipped FROM sensor_measurements
        WHERE (recorded_at AT TIME ZONE 'America/Toronto') AT TIME ZONE 'America/Toronto' <> recorded_at;
        IF skipped > 0 THEN
            RAISE EXCEPTION '% sensor_measurements rows have a recorded_at in an hour skipped when clocks sprang '
                'forward (a wall time that never existed in America/Toronto); nothing was changed. Find them with: '
                'SELECT * FROM sensor_measurements WHERE (recorded_at AT TIME ZONE ''America/Toronto'') '
                'AT TIME ZONE ''America/Toronto'' <> recorded_at;', skipped;
        END IF;
        ALTER TABLE sensor_measurements
            ALTER COLUMN recorded_at TYPE timestamptz
            USING LEAST(recorded_at AT TIME ZONE 'America/Toronto',
                        ((recorded_at - interval '1 hour') AT TIME ZONE 'America/Toronto') + interval '1 hour');
    END IF;
END
$$;
