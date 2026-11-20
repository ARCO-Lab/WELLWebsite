-- Undoes 0002_sensor_measurements_recorded_at_timestamptz.sql: recorded_at back to naive America/Toronto
-- wall-clock time (timestamp without time zone). scripts/migrate.py never runs this file (it only runs numbered
-- files in db/migrations/ itself). Run it by hand, in one transaction, with the worker and backend stopped and the
-- previous backend image (code from before the change) ready to start, because the old code expects naive times:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -1 -f db/migrations/down/0002_sensor_measurements_recorded_at_timestamptz.sql
--
-- Naive wall time can't hold both copies of the hour repeated when clocks fall back, so the second copy (EST) of
-- each reading that has a first copy (EDT) is deleted first, or the unique key would refuse the conversion. These
-- are the readings this change made it possible to store; nothing that existed before it is lost. The deleted
-- rows are saved to sensor_measurements_dst_rollback first, in case they are wanted later.
SET LOCAL lock_timeout = '10s';

-- Only while the column is timestamptz, so running this a second time changes nothing.
DO $$
BEGIN
    IF (SELECT a.atttypid::regtype::text FROM pg_attribute a
        WHERE a.attrelid = to_regclass('sensor_measurements') AND a.attname = 'recorded_at' AND NOT a.attisdropped)
       = 'timestamp with time zone' THEN
        LOCK TABLE sensor_measurements IN ACCESS EXCLUSIVE MODE;
        -- Kept across rollbacks: a later rollback adds its rows to the same table.
        CREATE TABLE IF NOT EXISTS sensor_measurements_dst_rollback (LIKE sensor_measurements);
        -- A reading is a second copy when the instant an hour before it shows the same wall time (only in the
        -- repeated hour), and the series has a reading at that instant.
        INSERT INTO sensor_measurements_dst_rollback
        SELECT b.* FROM sensor_measurements b
        WHERE (b.recorded_at AT TIME ZONE 'America/Toronto')
              = ((b.recorded_at - interval '1 hour') AT TIME ZONE 'America/Toronto')
          AND EXISTS (SELECT 1 FROM sensor_measurements a
                      WHERE a.station_id = b.station_id AND a.measurement_type = b.measurement_type
                        AND a.recorded_at = b.recorded_at - interval '1 hour');
        DELETE FROM sensor_measurements b
        WHERE (b.recorded_at AT TIME ZONE 'America/Toronto')
              = ((b.recorded_at - interval '1 hour') AT TIME ZONE 'America/Toronto')
          AND EXISTS (SELECT 1 FROM sensor_measurements a
                      WHERE a.station_id = b.station_id AND a.measurement_type = b.measurement_type
                        AND a.recorded_at = b.recorded_at - interval '1 hour');
        ALTER TABLE sensor_measurements
            ALTER COLUMN recorded_at TYPE timestamp USING recorded_at AT TIME ZONE 'America/Toronto';
    END IF;
END
$$;

-- The column is naive now, so 0002 must count as not applied (migrate.py would apply it again).
DELETE FROM schema_migrations WHERE version = '0002_sensor_measurements_recorded_at_timestamptz';
