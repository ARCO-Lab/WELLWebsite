-- Checks what roles.sql sets up, in the WELL database; changes nothing. Run it as a superuser:
--   sudo -u postgres env PGOPTIONS='-c search_path=pg_catalog' \
--     psql -d <database> -v ON_ERROR_STOP=1 < dashboard/backend/app/db/roles_check.sql
-- It ends with "roles check passed", or fails with every problem it found.

\set ON_ERROR_STOP on
-- Only pg_catalog, so nothing well_app created in public (e.g. a function named like a built-in) runs here as the
-- superuser; see roles.sql.
SET search_path = pg_catalog, pg_temp;
DO $$
DECLARE
    problems text[] := '{}';
    r record;
BEGIN
    FOR r IN SELECT wanted.name AS rolname FROM unnest(ARRAY['well_app', 'well_ops', 'well_restore']) AS wanted(name)
             WHERE NOT EXISTS (SELECT FROM pg_roles p WHERE p.rolname = wanted.name)
    LOOP
        problems := problems || format('role %s does not exist (run roles.sql)', r.rolname);
    END LOOP;
    IF cardinality(problems) > 0 THEN
        RAISE EXCEPTION 'roles check failed: %', array_to_string(problems, '; ');
    END IF;

    FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('well_app', 'well_ops')
             AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR NOT rolcanlogin)
    LOOP
        problems := problems || format('%s has an attribute it must not have (or cannot log in): see \du %s',
                                       r.rolname, r.rolname);
    END LOOP;
    -- well_restore needs CREATEDB for the restore drill, and nothing more
    FOR r IN SELECT rolname FROM pg_roles WHERE rolname = 'well_restore'
             AND (rolsuper OR rolcreaterole OR NOT rolcreatedb OR rolreplication OR rolbypassrls OR NOT rolcanlogin)
    LOOP
        problems := problems || format('%s must have CREATEDB and LOGIN and nothing more: see \du %s',
                                       r.rolname, r.rolname);
    END LOOP;
    FOR r IN SELECT g.rolname AS granted, u.rolname AS member
             FROM pg_auth_members a JOIN pg_roles g ON g.oid = a.roleid JOIN pg_roles u ON u.oid = a.member
             WHERE u.rolname IN ('well_app', 'well_ops', 'well_restore')
    LOOP
        problems := problems || format('%s is a member of %s', r.member, r.granted);
    END LOOP;

    FOR r IN SELECT c.oid::regclass AS name, pg_get_userbyid(c.relowner) AS owner
             FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
               AND c.relowner <> 'well_app'::regrole
               AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                                                         AND d.deptype = 'e')
    LOOP
        problems := problems || format('%s is owned by %s, not well_app', r.name, r.owner);
    END LOOP;

    IF NOT has_schema_privilege('well_app', 'public', 'CREATE') THEN
        problems := problems || 'well_app cannot create in schema public'::text;
    END IF;
    IF has_schema_privilege('well_ops', 'public', 'CREATE') THEN
        problems := problems || 'well_ops can create in schema public (PUBLIC still has CREATE on it?)'::text;
    END IF;

    -- well_ops: SELECT on every table, and no write beyond its uptime checks and the 90-day cleanup.
    -- well_restore: nothing on any table.
    FOR r IN SELECT c.oid, c.oid::regclass AS name, c.relname
             FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    LOOP
        IF has_table_privilege('well_restore', r.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')
        THEN
            problems := problems || format('well_restore has a privilege on %s (run roles.sql again)', r.name);
        END IF;
        IF NOT has_table_privilege('well_ops', r.oid, 'SELECT') THEN
            problems := problems || format('well_ops cannot read %s', r.name);
        END IF;
        IF has_table_privilege('well_ops', r.oid, 'UPDATE') OR has_table_privilege('well_ops', r.oid, 'TRUNCATE')
           OR (has_table_privilege('well_ops', r.oid, 'INSERT') AND r.relname <> 'uptime_probes')
           OR (has_table_privilege('well_ops', r.oid, 'DELETE') AND r.relname NOT IN ('uptime_probes', 'request_metrics'))
        THEN
            problems := problems || format('well_ops may write to %s', r.name);
        END IF;
    END LOOP;
    IF to_regclass('public.uptime_probes') IS NOT NULL
       AND NOT (has_table_privilege('well_ops', 'public.uptime_probes', 'INSERT')
                AND has_table_privilege('well_ops', 'public.uptime_probes', 'DELETE')
                AND has_sequence_privilege('well_ops', pg_get_serial_sequence('public.uptime_probes', 'id'), 'USAGE'))
    THEN
        problems := problems || 'well_ops cannot record its uptime checks (run roles.sql again)'::text;
    END IF;
    IF to_regclass('public.request_metrics') IS NOT NULL
       AND NOT has_table_privilege('well_ops', 'public.request_metrics', 'DELETE') THEN
        problems := problems || 'well_ops cannot clean up request_metrics (run roles.sql again)'::text;
    END IF;

    IF cardinality(problems) > 0 THEN
        RAISE EXCEPTION 'roles check failed: %', array_to_string(problems, '; ');
    END IF;
    RAISE NOTICE 'roles check passed';
END $$;
