-- Two columns on vendor_status (0003_monitoring_alerts.sql), written by the 10-minute ingestion
-- (scripts/inject_from_api.py):
--
-- fetched_until: the end of the newest vendor request whose readings were all stored. LI-COR's next run starts a few
-- hours before it, so a sensor group that has gone silent (the water-level loggers pulled for winter, say) no
-- longer pulls every run back to the 14-day limit.
-- last_skipped: how many records of the latest answer couldn't be read (no or a garbled timestamp, a timestamp
-- without a UTC offset) and one example, or NULL when every record was read. The alert emails mention it, so a
-- sensor that looks silent because its records are unreadable isn't reported as "vendor OK, check the sensor".
--
-- Both are nullable with no default, so adding them only changes the catalog: no table rewrite, no long lock.
-- The new code reads and writes them, so apply this before starting it. db/models.py has the same columns.
ALTER TABLE vendor_status ADD COLUMN IF NOT EXISTS fetched_until timestamptz;
ALTER TABLE vendor_status ADD COLUMN IF NOT EXISTS last_skipped text;
