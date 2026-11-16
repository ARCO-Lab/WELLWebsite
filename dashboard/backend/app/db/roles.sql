-- The WELL database's own roles, so nothing in Docker connects as the superuser `postgres`. A superuser can run
-- COPY ... FROM PROGRAM (a shell on the VM as the postgres OS user), read every database on the server and create
-- roles; these roles can't.
--
--   well_app  the API (backend), the worker and the export worker, and scripts/migrate.py. Owns the tables,
--             sequences and indexes in the public schema, so migrations (ALTER TABLE, CREATE INDEX CONCURRENTLY),
--             the backup's pg_dump and its ANALYZE all work as it. NOSUPERUSER, NOCREATEDB, NOCREATEROLE, and a
--             member of no other role.
--   well_ops  welldash² (dashboard/backend/app/ops/). SELECT on every table; its only writes are its uptime checks
--             (INSERT into uptime_probes) and the 90-day cleanup (DELETE on uptime_probes and request_metrics).
--             Can't create anything.
--   well_restore  the monthly restore drill (scripts/restore_check.py, through RESTORE_CHECK_DATABASE_URL), which
--             restores a dump into a throwaway database and drops it (its URL names the postgres maintenance
--             database). CREATEDB and CONNECT on this database, and nothing else: no privilege on any table here,
--             so it can't read or change the live data.
--
-- Run it as a superuser, in the WELL database (the README's "Database roles" section has every step):
--   sudo -u postgres env PGOPTIONS='-c search_path=pg_catalog' \
--     psql -d <database> -v ON_ERROR_STOP=1 < dashboard/backend/app/db/roles.sql
-- It sets no password (set them with \password afterwards), so it holds no secret. It is safe to run again, and
-- should be: after a migration that creates a table welldash² writes to, and whenever a table was created by hand
-- as postgres (it hands such tables to well_app). Each run takes a short exclusive lock on each table whose owner
-- changes; it gives up after 10 s instead of stalling the API behind a long query, so then just run it again.

\set ON_ERROR_STOP on
BEGIN;
-- well_app may create functions and operators in public. With public on the search path, one named like a built-in
-- this file calls (e.g. public.format(text, name), a closer match than pg_catalog's format(text, VARIADIC "any"))
-- would run here as the superuser. So only pg_catalog is searched, and every object here is named public.<name>.
SET LOCAL search_path = pg_catalog, pg_temp;
SET LOCAL lock_timeout = '10s';

-- The roles, created without a password: one that has none can't sign in with a password at all.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'well_app') THEN
        CREATE ROLE well_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'well_ops') THEN
        CREATE ROLE well_ops LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'well_restore') THEN
        CREATE ROLE well_restore LOGIN;
    END IF;
END $$;
-- Repeated on every run, so a privilege added by hand (e.g. CREATEDB on well_app) is taken away again.
ALTER ROLE well_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;
ALTER ROLE well_ops LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;
ALTER ROLE well_restore LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT;

-- No role membership either: pg_execute_server_program, pg_read_server_files and pg_write_server_files would each
-- give back part of what a superuser has.
DO $$
DECLARE m record;
BEGIN
    FOR m IN SELECT g.rolname AS granted, u.rolname AS member
             FROM pg_auth_members a JOIN pg_roles g ON g.oid = a.roleid JOIN pg_roles u ON u.oid = a.member
             WHERE u.rolname IN ('well_app', 'well_ops', 'well_restore')
    LOOP
        EXECUTE format('REVOKE %I FROM %I', m.granted, m.member);
        RAISE NOTICE 'revoked membership of % from %', m.granted, m.member;
    END LOOP;
END $$;

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO well_app, well_ops, well_restore', current_database());
END $$;

-- well_restore needs nothing on this database's objects; take back anything granted to it by hand.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM well_restore;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM well_restore;
REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM well_restore;
REVOKE ALL ON SCHEMA public FROM well_restore;

-- Only well_app creates objects. On PostgreSQL 13 every role may create in public by default, well_ops included.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO well_app;
GRANT USAGE ON SCHEMA public TO well_ops;

-- Hand every table, view and sequence in public to well_app (indexes and a serial column's sequence follow their
-- table), and the types and functions created there too. Objects that belong to an extension are left alone.
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT c.oid::regclass AS name, c.relkind
             FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND c.relowner <> 'well_app'::regrole
               AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                                                         AND d.deptype = 'e')
             ORDER BY 1
    LOOP
        EXECUTE format('ALTER %s %s OWNER TO well_app',
                       CASE r.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                                      WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END, r.name);
        RAISE NOTICE 'owner of % is now well_app', r.name;
    END LOOP;
    -- Sequences on their own (a sequence linked to a column changed with its table above, and can't be changed alone)
    FOR r IN SELECT c.oid::regclass AS name
             FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'S' AND c.relowner <> 'well_app'::regrole
               AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                                                         AND d.deptype IN ('a', 'i', 'e'))
             ORDER BY 1
    LOOP
        EXECUTE format('ALTER SEQUENCE %s OWNER TO well_app', r.name);
        RAISE NOTICE 'owner of sequence % is now well_app', r.name;
    END LOOP;
    -- Enums, domains and ranges (a table's own row type follows the table)
    FOR r IN SELECT t.oid::regtype AS name, t.typtype
             FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd', 'r') AND t.typowner <> 'well_app'::regrole
               AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid
                                                         AND d.deptype = 'e')
    LOOP
        EXECUTE format('ALTER %s %s OWNER TO well_app', CASE r.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END, r.name);
        RAISE NOTICE 'owner of type % is now well_app', r.name;
    END LOOP;
    FOR r IN SELECT p.oid::regprocedure AS name
             FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public' AND p.proowner <> 'well_app'::regrole
               AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid
                                                         AND d.deptype = 'e')
    LOOP
        EXECUTE format('ALTER ROUTINE %s OWNER TO well_app', r.name);
        RAISE NOTICE 'owner of routine % is now well_app', r.name;
    END LOOP;
END $$;

-- welldash² reads every table (each page summarises a few of them; none holds anything that isn't shown on the
-- public dashboard or welldash² already).
GRANT SELECT ON ALL TABLES IN SCHEMA public TO well_ops;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO well_ops;

-- welldash²'s writes, on tables that migration 0005 creates (so on a new database they exist only once migrate.py
-- has run: run this file again then).
DO $$
BEGIN
    IF to_regclass('public.uptime_probes') IS NOT NULL THEN
        GRANT INSERT, DELETE ON public.uptime_probes TO well_ops;
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO well_ops', pg_get_serial_sequence('public.uptime_probes', 'id'));
    END IF;
    IF to_regclass('public.request_metrics') IS NOT NULL THEN
        GRANT DELETE ON public.request_metrics TO well_ops;
    END IF;
END $$;

-- Tables made later keep working without another run of this file: welldash² can read what well_app creates (a
-- migration, db.create_all()), and well_app can use what this superuser creates by hand (e.g. a one-off fix run with
-- sudo -u postgres psql), until the next run hands it over.
ALTER DEFAULT PRIVILEGES FOR ROLE well_app IN SCHEMA public GRANT SELECT ON TABLES TO well_ops;
ALTER DEFAULT PRIVILEGES FOR ROLE well_app IN SCHEMA public GRANT SELECT ON SEQUENCES TO well_ops;
DO $$
BEGIN
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT ALL ON TABLES TO well_app', current_user);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT ALL ON SEQUENCES TO well_app', current_user);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON TABLES TO well_ops', current_user);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT ON SEQUENCES TO well_ops', current_user);
END $$;

COMMIT;
