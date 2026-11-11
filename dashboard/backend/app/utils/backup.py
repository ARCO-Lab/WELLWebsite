"""Helpers for the nightly database backup (scripts/backup_db.py) and its restore drill (scripts/restore_check.py).

They connect pg_dump, pg_restore and psql through libpq environment variables and a temporary password file, so
the database password never appears on a command line (where `ps` shows it) or in a log.
"""
import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime

from sqlalchemy.engine import make_url

# Dumps this job writes, and the only files it ever deletes: welldb-YYYYmmdd-HHMM.dump (Toronto time).
DUMP_PREFIX = "welldb-"
DUMP_PATTERN = re.compile(r"^welldb-(\d{8})-(\d{4})\.dump$")
DUMP_TIME_FORMAT = "%Y%m%d-%H%M"

# Tables the app role can't read: they are owned by the postgres role, and pg_dump locks every table it dumps,
# so a dump as the app role that includes them fails. Set BACKUP_EXCLUDE_TABLES to an empty value (and run as
# a role that can read them, e.g. postgres) to include them.
DEFAULT_EXCLUDE_TABLES = "export_jobs,data_fixes"
# Tables a dump must hold data for, or it counts as failed.
DEFAULT_EXPECT_TABLES = "sensor_measurements,sampling_measurements"

# pg_dump and pg_restore of the server's major version (13 on the VM), installed in the image from the PostgreSQL
# apt repository (Dockerfile). A newer pg_dump writes archives that an older pg_restore can't read, so the
# matching version is used when it is there, and whatever is on PATH otherwise (e.g. local development).
DEFAULT_PG_BIN_DIR = "/usr/lib/postgresql/13/bin"

# libpq settings that may come in a DATABASE_URL's query string, e.g. ?sslmode=require
_QUERY_ENV = {"sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT", "connect_timeout": "PGCONNECT_TIMEOUT",
              "application_name": "PGAPPNAME"}


def csv_setting(value):
    """Names from a comma-separated setting, without blanks."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def pg_tool(name, env=None):
    """Path of pg_dump, pg_restore or psql: from PG_BIN_DIR (default DEFAULT_PG_BIN_DIR) when it has it, else PATH."""
    env = os.environ if env is None else env
    bin_dir = (env.get("PG_BIN_DIR") or DEFAULT_PG_BIN_DIR).strip()
    candidate = os.path.join(bin_dir, name)
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} not found in {bin_dir} or on PATH (install postgresql-client-13)")
    return found


def parse_database_url(url):
    """The connection settings in a DATABASE_URL (postgresql:// or postgresql+psycopg2://) as a dict: host, port,
    user, password, database and libpq query options. ValueError if it isn't a PostgreSQL URL with a database."""
    if not url:
        raise ValueError("no database URL (set DATABASE_URL)")
    try:
        parsed = make_url(url)
    except Exception:
        # SQLAlchemy's message repeats the whole URL, password included, so it isn't passed on
        raise ValueError("the database URL could not be parsed") from None
    if parsed.get_backend_name() != "postgresql":
        raise ValueError(f"not a PostgreSQL URL (backend {parsed.get_backend_name()!r})")
    if not parsed.database:
        raise ValueError("the database URL names no database")
    return {"host": parsed.host, "port": parsed.port, "user": parsed.username, "password": parsed.password,
            "database": parsed.database, "query": dict(parsed.query)}


def with_database(settings, database):
    """`settings` (from parse_database_url) pointing at another database on the same server."""
    return {**settings, "database": database}


def pgpass_line(password):
    """A .pgpass line that gives `password` for any host, port, database and user (the environment already
    names exactly one of each). Backslashes and colons are escaped, as the file format requires."""
    escaped = password.replace("\\", "\\\\").replace(":", "\\:")
    return f"*:*:*:*:{escaped}\n"


@contextlib.contextmanager
def libpq_env(settings, base_env=None):
    """The environment for a libpq client connecting with `settings`: PGHOST, PGPORT, PGUSER and PGDATABASE, plus
    PGPASSFILE pointing at a temporary 0600 password file that is deleted afterwards. PGPASSWORD is removed, so
    only the file is used."""
    env = dict(os.environ if base_env is None else base_env)
    for key in ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGHOST", "PGHOSTADDR", "PGPORT", "PGUSER", "PGDATABASE"):
        env.pop(key, None)
    if settings.get("host"):
        env["PGHOST"] = settings["host"]
    if settings.get("port"):
        env["PGPORT"] = str(settings["port"])
    if settings.get("user"):
        env["PGUSER"] = settings["user"]
    env["PGDATABASE"] = settings["database"]
    for key, value in (settings.get("query") or {}).items():
        if key in _QUERY_ENV and isinstance(value, str):
            env[_QUERY_ENV[key]] = value
    passfile = None
    try:
        if settings.get("password"):
            fd, passfile = tempfile.mkstemp(prefix="pgpass-")   # mkstemp creates it 0600
            with os.fdopen(fd, "w") as f:
                f.write(pgpass_line(settings["password"]))
            env["PGPASSFILE"] = passfile
        yield env
    finally:
        if passfile:
            with contextlib.suppress(FileNotFoundError):
                os.remove(passfile)


def psycopg2_kwargs(settings):
    """Keyword arguments for psycopg2.connect (the password goes in as an argument, never in a printed DSN)."""
    kwargs = {"dbname": settings["database"]}
    for key in ("host", "port", "user", "password"):
        if settings.get(key):
            kwargs[key] = settings[key]
    for key, value in (settings.get("query") or {}).items():
        if key in _QUERY_ENV and isinstance(value, str):
            kwargs[key] = value
    return kwargs


# Sequences that belong to (are owned by) the given tables: serial and identity id columns.
OWNED_SEQUENCES_SQL = """
SELECT ns.nspname, s.relname
FROM pg_class s
JOIN pg_namespace ns ON ns.oid = s.relnamespace
JOIN pg_depend d ON d.classid = 'pg_class'::regclass AND d.objid = s.oid
                AND d.refclassid = 'pg_class'::regclass AND d.deptype IN ('a', 'i')
JOIN pg_class t ON t.oid = d.refobjid
JOIN pg_namespace nt ON nt.oid = t.relnamespace
WHERE s.relkind = 'S' AND (t.relname = ANY(%(tables)s) OR nt.nspname || '.' || t.relname = ANY(%(tables)s))
ORDER BY 1, 2
"""


def quoted_pattern(schema, name):
    """A pg_dump -t/-T pattern that matches exactly schema.name (quoted, so no wildcard or case folding applies)."""
    return '"{}"."{}"'.format(schema.replace('"', '""'), name.replace('"', '""'))


def owned_sequences(settings, tables):
    """pg_dump patterns for the sequences owned by `tables` (names or schema.name). pg_dump 13 still reads such a
    sequence when its table is excluded, so a sequence the role can't read must be excluded with it. Reads only
    the catalogs, which every role can."""
    if not tables:
        return []
    import psycopg2
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    try:
        with conn.cursor() as cur:
            cur.execute(OWNED_SEQUENCES_SQL, {"tables": list(tables)})
            return [quoted_pattern(schema, name) for schema, name in cur.fetchall()]
    finally:
        conn.close()


def dump_name(when):
    """File name of a dump made at `when` (site time): welldb-YYYYmmdd-HHMM.dump."""
    return f"{DUMP_PREFIX}{when.strftime(DUMP_TIME_FORMAT)}.dump"


def dump_time(name):
    """The time in a dump's file name, or None if `name` isn't one of this job's dumps."""
    match = DUMP_PATTERN.match(name)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)}-{match.group(2)}", DUMP_TIME_FORMAT)
    except ValueError:
        return None


def dumps_in(names):
    """(time, name) of this job's dumps among `names`, newest first. Other files are left out."""
    found = [(dump_time(name), name) for name in names]
    return sorted(((t, n) for t, n in found if t is not None), reverse=True)


def dumps_to_keep(names, keep_daily, keep_weekly):
    """The dumps among `names` that retention keeps: the newest dump of each of the `keep_daily` most recent days
    that have one, and the newest of each of the `keep_weekly` most recent ISO weeks that have one. Files that
    aren't this job's dumps are never in the result, nor in dumps_to_prune."""
    keep, days, weeks = set(), set(), set()
    for when, name in dumps_in(names):
        day = when.date()
        week = tuple(when.isocalendar())[:2]
        if day not in days and len(days) < keep_daily:
            days.add(day)
            keep.add(name)
        if week not in weeks and len(weeks) < keep_weekly:
            weeks.add(week)
            keep.add(name)
    return keep


def dumps_to_prune(names, keep_daily, keep_weekly):
    """This job's dumps among `names` that retention deletes, oldest first."""
    keep = dumps_to_keep(names, keep_daily, keep_weekly)
    return [name for _, name in reversed(dumps_in(names)) if name not in keep]


# A data entry in `pg_restore --list` output, e.g. "3021; 0 16390 TABLE DATA public sensor_measurements welluser"
_TABLE_DATA = re.compile(r"^\s*\d+;\s+\d+\s+\d+\s+TABLE DATA\s+(\S+)\s+(\S+)(?:\s|$)")


def table_data_entries(listing):
    """(schema, table) of each TABLE DATA entry in `pg_restore --list` output, in order."""
    entries = []
    for line in (listing or "").splitlines():
        if line.lstrip().startswith(";"):
            continue   # a comment line of the listing's header
        match = _TABLE_DATA.match(line)
        if match:
            entries.append((match.group(1), match.group(2)))
    return entries


def missing_tables(listing, expected):
    """The `expected` tables (names, or schema.name) that have no TABLE DATA entry in the listing."""
    entries = table_data_entries(listing)
    names = {table for _, table in entries} | {f"{schema}.{table}" for schema, table in entries}
    return [table for table in expected if table not in names]


def run_tool(cmd, env, timeout):
    """Run a PostgreSQL client tool; CalledProcessError (with its stderr) if it fails."""
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, timeout=timeout)


def human_size(size):
    """A byte count for a log line, e.g. 7.9 KB or 1.2 GB."""
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size / 1024:.1f} GB"
