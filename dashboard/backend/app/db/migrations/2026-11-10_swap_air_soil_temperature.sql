-- One-off data fix (2026-11-10): "Air Temperature" and "Soil Temperature" were stored the wrong way round.
--
-- Until this date the ingestion named sensor 21948438-1 (the temperature / humidity / dew point sensor,
-- i.e. air) "Soil Temperature", and 22154270-1 (the soil probe) "Air Temperature". The parser is fixed in
-- the same change (utils/sensor_names.py); this script swaps the rows already stored. The data showed it
-- plainly: the series stored as "Soil" peaked mid-afternoon with a ~10 °C daily swing and moved opposite
-- to humidity, while the one stored as "Air" lagged into the evening with a ~1 °C swing.
-- Exports made before this date (including any uploaded to Borealis) carry the old, swapped names.
--
-- Run it once, with the worker stopped, right before starting the worker with the fixed parser, so no
-- rows with the old names arrive afterwards:
--   docker compose stop worker
--   psql "<database url>" -f 2026-11-10_swap_air_soil_temperature.sql
--   docker compose up -d --build worker
-- The data_fixes table makes a second run fail instead of swapping the rows back.

\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE IF NOT EXISTS data_fixes (
    name       text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO data_fixes (name) VALUES ('2026-11-10 swap air and soil temperature');   -- fails if already applied

-- The unique key is (station_id, measurement_type, recorded_at), so swap through a temporary name.
UPDATE sensor_measurements SET measurement_type = 'Air Temperature (swapping)'
 WHERE group_type = 'Weather' AND station_id = '22051538' AND measurement_type = 'Air Temperature';
UPDATE sensor_measurements SET measurement_type = 'Air Temperature'
 WHERE group_type = 'Weather' AND station_id = '22051538' AND measurement_type = 'Soil Temperature';
UPDATE sensor_measurements SET measurement_type = 'Soil Temperature'
 WHERE group_type = 'Weather' AND station_id = '22051538' AND measurement_type = 'Air Temperature (swapping)';

-- Check: the two counts are swapped and nothing is left under the temporary name.
SELECT measurement_type, count(*) AS rows, min(recorded_at) AS first, max(recorded_at) AS last
  FROM sensor_measurements
 WHERE group_type = 'Weather'
   AND measurement_type IN ('Air Temperature', 'Soil Temperature', 'Air Temperature (swapping)')
 GROUP BY 1 ORDER BY 1;

COMMIT;
