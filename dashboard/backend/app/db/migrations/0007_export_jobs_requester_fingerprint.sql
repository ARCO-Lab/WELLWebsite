-- export_jobs.requester_fingerprint: a hash of the address that asked for each background export, which the API
-- reads on every new export job (the per-visitor limits in api/routes/exports.py). The table and the column were
-- only ever created by db.create_all() (db/models.py), which creates missing tables but never adds a column to one
-- that exists; a database whose export_jobs predates the column would answer every new export job with a 500.
--
-- Idempotent: a no-op where the column exists (every database built from the current models), and where there is no
-- export_jobs table yet (db.create_all() makes it, with the column). The column is nullable with no default, so
-- adding it rewrites nothing and holds the table's lock only for a moment.
ALTER TABLE IF EXISTS export_jobs ADD COLUMN IF NOT EXISTS requester_fingerprint varchar(128);
