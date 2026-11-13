-- Synthetic sensor readings for the load test (.github/workflows/load-test.yml), never run against production.
--
-- The layout is the real one (utils/parsers.py): the weather station's 11 measurements, 8 water-quality
-- measurements, and 5 water-level loggers with an elevation and a water temperature each: 29 series, one reading
-- every 10 minutes, as ingestion stores them (naive America/Toronto wall-clock time, in time order).
-- `years` of history up to now: 29 series x 52,560 readings a year = about 1.52M rows a year, so the default 4
-- years is about 6.1M rows, more than the site holds (its data starts in May 2025): a pessimistic table size.
-- The values follow plausible seasonal and daily cycles plus noise; their exact shape doesn't matter for load.
--
-- psql -v years=4 -f seed.sql

\set ON_ERROR_STOP on
\timing on

SET work_mem = '512MB';  -- the ORDER BY below sorts in memory

CREATE TEMP TABLE layout (
    group_type text, station_id text, measurement_type text, unit text,
    base float8, seasonal float8, diurnal float8, noise float8
);

-- Weather: the station id is the LI-COR logger id (HOBOLINK_LOGGERS); this one is made up, as in dashboard/e2e.
INSERT INTO layout VALUES
    ('Weather', '22051538', 'Air Temperature',   '°C',     8,    12,   5,    1),
    ('Weather', '22051538', 'Soil Temperature',  '°C',     9,    9,    1,    0.2),
    ('Weather', '22051538', 'Dew Point',         '°C',     3,    10,   2,    1),
    ('Weather', '22051538', 'Relative Humidity', '%',      72,   8,    15,   6),
    ('Weather', '22051538', 'Pressure',          'mbar',   1013, 3,    1,    4),
    ('Weather', '22051538', 'Rain',              'mm',     0,    0,    0,    0),
    ('Weather', '22051538', 'Solar Radiation',   'W/m²',   750,  0,    0,    0),
    ('Weather', '22051538', 'Water Content',     'm³/m³',  0.3,  0.05, 0,    0.01),
    ('Weather', '22051538', 'Wind Speed',        'm/s',    3,    1,    1,    2),
    ('Weather', '22051538', 'Gust Speed',        'm/s',    5,    1.5,  1.5,  3),
    ('Weather', '22051538', 'Wind Direction',    '°',      0,    0,    0,    0),
-- Water quality: the station id is the WQData device id (WQ_DEVICE_ID); made up too.
    ('Quality', '4501', 'Water Temperature', '°C',    11,   9,    1,    0.3),
    ('Quality', '4501', 'Conductivity',      'uS/cm', 900,  150,  10,   40),
    ('Quality', '4501', 'Salinity',          'PPT',   0.45, 0.08, 0,    0.02),
    ('Quality', '4501', 'TDS',               'g/L',   0.58, 0.1,  0,    0.03),
    ('Quality', '4501', 'ODO',               'mg/L',  10,   2,    0.8,  0.4),
    ('Quality', '4501', 'ODOSat',            '%',     95,   5,    6,    3),
    ('Quality', '4501', 'Turbidity',         'NTU',   8,    4,    0,    5),
    ('Quality', '4501', 'TSS',               'mg/L',  12,   5,    0,    6);

-- Water-level loggers (LOGGER_CONFIG in utils/parsers.py).
INSERT INTO layout
SELECT 'Logger', s::text, m.measurement_type, m.unit, m.base, m.seasonal, m.diurnal, m.noise
FROM generate_series(2577531, 2577535) AS s
CROSS JOIN (VALUES ('Water Surface Elevation', 'm asl', 39.9, 0.15, 0.01, 0.05),
                   ('Water Temperature',       '°C',    10,   8,    1,    0.4))
    AS m(measurement_type, unit, base, seasonal, diurnal, noise);

INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, unit, recorded_at)
SELECT l.station_id, l.group_type, l.measurement_type,
       CASE l.measurement_type
           WHEN 'Rain' THEN CASE WHEN random() < 0.03 THEN round((random() * 2)::numeric, 2)::float8 ELSE 0 END
           WHEN 'Wind Direction' THEN floor(random() * 360)
           WHEN 'Solar Radiation'
               THEN greatest(0, l.base * sin(pi() * (extract(hour FROM t) + extract(minute FROM t) / 60 - 6) / 12))
           ELSE l.base
                - l.seasonal * cos(2 * pi() * (extract(doy FROM t) - 20) / 365.25)
                + l.diurnal * sin(2 * pi() * (extract(hour FROM t) - 9) / 24)
                + l.noise * (random() - 0.5)
       END,
       l.unit, t
FROM generate_series(
         date_trunc('day', now() AT TIME ZONE 'America/Toronto') - make_interval(years => :years),
         date_trunc('minute', now() AT TIME ZONE 'America/Toronto')
             - make_interval(mins => (extract(minute FROM now() AT TIME ZONE 'America/Toronto'))::int % 10),
         interval '10 minutes') AS t
CROSS JOIN layout AS l
ORDER BY t, l.station_id, l.measurement_type;

-- Statistics and the visibility map, as autovacuum would have them on a long-lived table (index-only scans
-- for /api/latest depend on the latter).
VACUUM (ANALYZE) sensor_measurements;

SELECT count(*) AS rows, min(recorded_at) AS first_reading, max(recorded_at) AS last_reading,
       pg_size_pretty(pg_total_relation_size('sensor_measurements')) AS table_and_indexes
FROM sensor_measurements;
