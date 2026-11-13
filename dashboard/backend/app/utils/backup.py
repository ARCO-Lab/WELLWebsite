"""Helpers for the nightly database backup (scripts/backup_db.py) and its restore drill (scripts/restore_check.py).

They connect pg_dump, pg_restore and psql through libpq environment variables and a temporary password file, so
the database password never appears on a command line (where `ps` shows it) or in a log.
"""
import contextlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta

from sqlalchemy.engine import make_url

from db.database import CONNECT_ARGS

# Dumps this job writes, and the only files it ever deletes: welldb-YYYYmmdd-HHMM.dump (Toronto time).
DUMP_PREFIX = "welldb-"
DUMP_PATTERN = re.compile(r"^welldb-(\d{8})-(\d{4})\.dump$")
# A dump still being written (renamed to its final name once checked). One left behind by a run that was killed
# is deleted by the next run, which holds the backup lock, so it can't be another run's.
PARTIAL_PATTERN = re.compile(r"^\.welldb-\d{8}-\d{4}\.dump\.partial$")

# Temporary password files live in a folder of their own, so ones left by a process that was killed (SIGKILL
# skips every cleanup) can be found and deleted. Files older than PASSFILE_MAX_AGE_S are leftovers: libpq reads
# the file when it connects, at the start of a run.
PASSFILE_DIR_NAME = "welldb-pgpass"
PASSFILE_PREFIX = "pgpass-"
PASSFILE_MAX_AGE_S = 60 * 60
DUMP_TIME_FORMAT = "%Y%m%d-%H%M"
# Retention never deletes a dump younger than this (dumps_to_keep), whatever else was taken that day
RECENT_KEEP = timedelta(hours=24)
# Beside each dump, .<dump name> plus this: the source's row counts when the dump was taken (save_dump_counts)
COUNTS_SUFFIX = ".counts.json"

# Which tables to leave out (BACKUP_EXCLUDE_TABLES, read by exclusion_setting). "auto" (the default) leaves out
# only those the connecting role can't read, since pg_dump locks and reads every table it dumps and would fail on
# them; a role that can read everything (on the VM the app connects as postgres) dumps everything. A comma-separated
# list, or an empty value (exclude nothing), overrides it.
AUTO_EXCLUDE = "auto"
# Tables a dump must hold data for, or it counts as failed.
DEFAULT_EXPECT_TABLES = "sensor_measurements,sampling_measurements"

# The reference row counts of those tables, compared with the counts before each new dump (a dump of an emptied
# table still lists TABLE DATA for it, so the dump's own check can't see that rows went missing): the most rows each
# had at a good backup, so the reference only goes down with --accept-row-counts. The file sits in the backup folder,
# next to the dumps it describes, and also names the last good dump and the dumps written while the check was failing
# (the only ones the check itself ever deletes).
ROW_COUNTS_NAME = ".row-counts.json"
# A table with fewer rows than this many percent below its reference count fails the backup
# (BACKUP_MAX_SHRINK_PCT). These tables only grow: readings are added, and the only routine deletions are a handful
# of sentinel rows (scripts/clean_sentinels.py) or a sampling reload with about as many rows. Large tables are
# counted with the planner's estimate, taken from a sample and so off by a percent or so, so 5% stays clear of that
# noise and still catches the loss of a few weeks of data or more.
DEFAULT_MAX_SHRINK_PCT = 5
# Tables estimated below this many rows are counted exactly with count(*) (well under a second); larger ones are
# analyzed first (ANALYZE reads a fixed-size sample, a few seconds at most) and their fresh estimate is used
# (pg_class.reltuples), so the check stays cheap and still sees a recent DELETE that autovacuum hasn't caught up with.
EXACT_COUNT_LIMIT = 1_000_000
# How long ANALYZE may wait for its lock (e.g. behind an anti-wraparound VACUUM, which holds the same lock for a
# long time). If it can't get it, the older estimate is used, with a warning, rather than failing the backup.
ANALYZE_LOCK_TIMEOUT = "30s"

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
            fd, passfile = tempfile.mkstemp(prefix=PASSFILE_PREFIX, dir=passfile_dir())   # created 0600
            with os.fdopen(fd, "w") as f:
                f.write(pgpass_line(settings["password"]))
            env["PGPASSFILE"] = passfile
        yield env
    finally:
        if passfile:
            with contextlib.suppress(FileNotFoundError):
                os.remove(passfile)


def passfile_dir():
    """The folder for temporary password files (created 0700 under the system temp folder)."""
    path = os.path.join(tempfile.gettempdir(), PASSFILE_DIR_NAME)
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def remove_stale_passfiles(max_age_s=PASSFILE_MAX_AGE_S, now=None):
    """Delete password files that a killed run left behind (older than `max_age_s`). Returns how many."""
    directory, now, removed = passfile_dir(), now or time.time(), 0
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        with contextlib.suppress(FileNotFoundError):
            if name.startswith(PASSFILE_PREFIX) and now - os.path.getmtime(path) > max_age_s:
                os.remove(path)
                removed += 1
    return removed


def stale_partials(names):
    """The unfinished dumps (.welldb-*.dump.partial) among `names`."""
    return sorted(name for name in names if PARTIAL_PATTERN.match(name))


def psycopg2_kwargs(settings):
    """Keyword arguments for psycopg2.connect (the password goes in as an argument, never in a printed DSN), with the
    app's connect timeout and TCP keepalives (db/database.py); a connect_timeout in the URL wins."""
    kwargs = {"dbname": settings["database"], **CONNECT_ARGS}
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


# Tables (plain and partitioned) and sequences outside the system schemas that the connecting role may not read.
# pg_dump reads both (a sequence's last value too), so each would make the dump fail.
UNREADABLE_SQL = """
SELECT n.nspname, c.relname, c.relkind
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'S')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg\\_%'
  AND NOT CASE WHEN c.relkind = 'S' THEN has_sequence_privilege(c.oid, 'SELECT')
               ELSE has_table_privilege(c.oid, 'SELECT') END
ORDER BY 1, 2
"""


def exclusion_setting(env=None):
    """BACKUP_EXCLUDE_TABLES as a list of names, or AUTO_EXCLUDE when it is unset or "auto"."""
    env = os.environ if env is None else env
    raw = env.get("BACKUP_EXCLUDE_TABLES")
    if raw is None or raw.strip().lower() == AUTO_EXCLUDE:
        return AUTO_EXCLUDE
    return csv_setting(raw)


def unreadable_relations(settings):
    """(tables, sequences) the role in `settings` can't read, each as schema.name. Reads only the catalogs."""
    import psycopg2
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    try:
        with conn.cursor() as cur:
            cur.execute(UNREADABLE_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()
    tables = [f"{schema}.{name}" for schema, name, kind in rows if kind != "S"]
    sequences = [f"{schema}.{name}" for schema, name, kind in rows if kind == "S"]
    return tables, sequences


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


def dumps_to_keep(names, keep_daily, keep_weekly, now=None, protect=()):
    """The dumps among `names` that retention keeps: the newest dump of each of the `keep_daily` most recent days
    that have one, and the newest of each of the `keep_weekly` most recent ISO weeks that have one. With `now`
    (naive site time, like the names), also every dump younger than RECENT_KEEP, so a dump taken by hand before a
    risky change (say at 01:00) isn't deleted that night for not being its day's newest. Every name in `protect`
    (the newest good dump) is kept too. Files that aren't this job's dumps are never in the result, nor in
    dumps_to_prune."""
    keep, days, weeks = {name for name in protect if dump_time(name)}, set(), set()
    for when, name in dumps_in(names):
        if now is not None and when > now - RECENT_KEEP:
            keep.add(name)
        day = when.date()
        week = tuple(when.isocalendar())[:2]
        if day not in days and len(days) < keep_daily:
            days.add(day)
            keep.add(name)
        if week not in weeks and len(weeks) < keep_weekly:
            weeks.add(week)
            keep.add(name)
    return keep


def dumps_to_prune(names, keep_daily, keep_weekly, now=None, protect=()):
    """This job's dumps among `names` that retention deletes, oldest first (dumps_to_keep keeps the others)."""
    keep = dumps_to_keep(names, keep_daily, keep_weekly, now, protect)
    return [name for _, name in reversed(dumps_in(names)) if name not in keep]


def counts_name(dump):
    """The name of the file beside `dump` that records its source's row counts when it was taken (.<dump>.counts.json:
    hidden, and not a dump name, so nothing mistakes it for a backup)."""
    return f".{dump}{COUNTS_SUFFIX}"


def orphan_counts_files(names):
    """The row count files among `names` whose dump is gone (deleted by retention or by hand)."""
    dumps = set(names)
    return sorted(name for name in names
                  if name.startswith(".") and name.endswith(COUNTS_SUFFIX)
                  and DUMP_PATTERN.match(name[1:-len(COUNTS_SUFFIX)]) and name[1:-len(COUNTS_SUFFIX)] not in dumps)


def save_dump_counts(directory, dump, counts, exact, when):
    """Record beside `dump` the row counts of its source tables taken just before it ({table: rows}, from
    count_rows), and which of them were exact rather than the planner's estimate. The restore drill
    (scripts/restore_check.py) compares what it restores with these."""
    record = {"dump": dump, "counted_at": when.isoformat(timespec="seconds"),
              "counts": {table: rows for table, rows in counts.items() if rows is not None},
              "exact": sorted(table for table in exact if counts.get(table) is not None)}
    write_json_atomically(os.path.join(directory, counts_name(dump)), record)


def load_dump_counts(path):
    """The row counts recorded beside the dump at `path` (save_dump_counts): ({table: rows}, {exact tables}), or
    None when there is no such record (a dump taken before they were recorded, or when counting failed).
    ValueError if the record can't be read."""
    path = pathlib.Path(path)
    record_path = path.parent / counts_name(path.name)
    try:
        with open(record_path, encoding="utf-8") as f:
            record = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise ValueError(f"{record_path} can't be read ({e})") from None
    counts = record.get("counts") if isinstance(record, dict) else None
    exact = record.get("exact", []) if isinstance(record, dict) else None
    if not isinstance(counts, dict) or not all(isinstance(v, int) and not isinstance(v, bool) for v in counts.values()) \
            or not isinstance(exact, list):
        raise ValueError(f"{record_path} doesn't hold row counts")
    return counts, set(exact)


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


# The planner's row estimate and the exact name of a table given as name or schema.name (None if there is none)
_TABLE_ESTIMATE_SQL = """
SELECT n.nspname, c.relname, c.reltuples::bigint
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.oid = to_regclass(%s)
"""


def count_rows(settings, tables, exact_limit=EXACT_COUNT_LIMIT, warn=None, analyze_lock_timeout=ANALYZE_LOCK_TIMEOUT,
               exact=None):
    """{table: rows} for `tables` (names or schema.name): exact (count(*)) for tables the planner estimates under
    `exact_limit` rows, the estimate just after an ANALYZE for larger ones, and always exactly 0 for a table with no
    row at all. None for a table that doesn't exist. Changes no data (ANALYZE only refreshes planner statistics).
    Each table is named in SQL by the schema and name PostgreSQL resolved it to, quoted as identifiers. If ANALYZE
    can't get its lock within `analyze_lock_timeout` (or fails otherwise), the older estimate is used and
    `warn(message)` is called. `exact`, a set if given, gets the tables whose count is exact (not an estimate)."""
    import psycopg2
    from psycopg2 import sql
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    counts = {}
    try:
        conn.set_session(autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5min'")
            for table in tables:
                cur.execute(_TABLE_ESTIMATE_SQL, (table,))
                found = cur.fetchone()
                if found is None:
                    counts[table] = None
                    continue
                schema, name, estimate = found
                relation = sql.Identifier(schema, name)
                cur.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM {})").format(relation))
                if not cur.fetchone()[0]:
                    counts[table] = 0
                    if exact is not None:
                        exact.add(table)
                elif estimate < exact_limit:
                    cur.execute(sql.SQL("SELECT count(*) FROM {}").format(relation))
                    counts[table] = cur.fetchone()[0]
                    if exact is not None:
                        exact.add(table)
                else:
                    # reltuples is only as fresh as the last (auto)vacuum or ANALYZE; a role that doesn't own the
                    # table gets a warning from ANALYZE and the older estimate
                    try:
                        cur.execute("BEGIN")
                        cur.execute("SET LOCAL lock_timeout = %s", (analyze_lock_timeout,))
                        cur.execute(sql.SQL("ANALYZE {}").format(relation))
                        cur.execute("COMMIT")
                    except psycopg2.Error as e:
                        cur.execute("ROLLBACK")
                        if warn:
                            warn(f"ANALYZE {schema}.{name} failed ({str(e).strip()}), so its row count is the "
                                 f"planner's older estimate ({int(estimate):,})")
                    cur.execute(_TABLE_ESTIMATE_SQL, (table,))
                    counts[table] = int(cur.fetchone()[2])
    finally:
        conn.close()
    return counts


def row_count_problems(counts, previous, max_shrink_pct):
    """What is wrong with `counts` (from count_rows) compared with `previous`, the reference counts (the most rows
    each table had at a good backup, save_row_counts; {} if none): a table that doesn't exist, one that is empty
    (unless it was empty then too), or one with more than `max_shrink_pct` percent fewer rows than that. One message
    per table; [] when all is well."""
    problems = []
    for table, rows in counts.items():
        before = previous.get(table)
        if rows is None:
            problems.append(f"{table} does not exist")
        elif rows == 0 and before != 0:
            problems.append(f"{table} is empty" + (f" (it had {before:,} rows at a good backup)" if before else ""))
        elif before and rows < before * (1 - max_shrink_pct / 100):
            problems.append(f"{table} has {rows:,} rows, {100 * (before - rows) / before:.0f}% fewer than the "
                            f"{before:,} it had at a good backup")
    return problems


def load_record(directory):
    """The row counts record in `directory`: {"dump": the last good dump, "recorded_at", "counts": {table: the most
    rows it had at a good backup}, "failing_dumps": [dumps written while the check failed]}, with empty values when
    there is no record yet. ValueError if the file can't be read as such."""
    path = os.path.join(directory, ROW_COUNTS_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except FileNotFoundError:
        record = {}
    except (OSError, ValueError) as e:
        raise ValueError(f"{path} can't be read ({e})") from None
    if not isinstance(record, dict):
        raise ValueError(f"{path} doesn't hold row counts")
    record = {"dump": None, "recorded_at": None, "counts": {}, "failing_dumps": [], **record}
    counts, failing = record["counts"], record["failing_dumps"]
    if not isinstance(counts, dict) or not all(isinstance(v, int) and not isinstance(v, bool)
                                               for v in counts.values()) \
            or not isinstance(failing, list) or not all(isinstance(n, str) for n in failing):
        raise ValueError(f"{path} doesn't hold row counts")
    return record


def load_row_counts(directory):
    """The reference counts in `directory`: the most rows each table had at a good backup ({} if none were
    recorded). ValueError if the file can't be read as such."""
    return load_record(directory)["counts"]


def write_json_atomically(path, data):
    """Write `data` as JSON to `path` through a temporary file that is flushed to disk before it is renamed over
    `path`, so a crash or a power cut leaves the old file or the new one, never an empty or partial one."""
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(path + ".tmp", path)
    with contextlib.suppress(OSError):   # and the rename itself (the folder's entry)
        fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def save_record(directory, record):
    """Write the row counts record (load_record), atomically (write_json_atomically)."""
    write_json_atomically(os.path.join(directory, ROW_COUNTS_NAME), record)


def save_row_counts(directory, counts, dump, when, lower=False):
    """Record `dump` (a file name) made at `when` as the last good backup. Each table's reference count becomes the
    larger of its recorded one and its count in `counts`, so the reference never goes down: a loss under
    BACKUP_MAX_SHRINK_PCT passes, but the next one is still measured from the higher count, so small losses can't add
    up night after night unnoticed. With `lower` (--accept-row-counts) the reference becomes `counts` as they are.
    `counts` None (nothing was counted) keeps the recorded ones. No dump is failing any more."""
    try:
        record = load_record(directory)
    except ValueError:   # an unreadable record is replaced
        record = {"counts": {}}
    record.update(dump=dump, recorded_at=when.isoformat(timespec="seconds"), failing_dumps=[])
    if counts is not None:
        before = {} if lower else record["counts"]
        record["counts"] = {table: max(rows, before.get(table, rows)) for table, rows in counts.items()
                            if rows is not None}
    save_record(directory, record)


def mark_failing(directory, dump, prune, log=print):
    """Add `dump` to the dumps written while the row count check fails. With `prune`, first delete the ones marked
    earlier (only files named as this job's dumps), so the newest failing dump is kept next to the good ones and
    failing nights don't pile up dumps; no unmarked dump is ever deleted here. The record's counts stay."""
    record = load_record(directory)
    keep = []
    for name in record["failing_dumps"]:
        path = os.path.join(directory, name)
        if prune and name != dump and DUMP_PATTERN.match(name) and os.path.exists(path):
            os.remove(path)
            with contextlib.suppress(FileNotFoundError):
                os.remove(os.path.join(directory, counts_name(name)))
            log(f"Deleted {name}, an earlier dump taken while the row counts were failing")
        elif not prune and name != dump:
            keep.append(name)
    record["failing_dumps"] = keep + [dump]
    save_record(directory, record)


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


# The restore drill's throwaway databases (scripts/restore_check.py): the only databases anything here ever drops.
# Each is a full copy of the live database, so one left behind (the drill killed, or the worker out of memory) is
# dropped at worker start-up, after a failed drill and before each nightly backup, and listed in the daily digest.
RESTORE_DATABASE_PREFIX = "welldb_restore_check"
RESTORE_DATABASE_PATTERN = re.compile(r"^welldb_restore_check[a-z0-9_]*$")
# Held by a running drill, so its database isn't taken for a leftover. In the temporary folder: the scheduled drill,
# one run by hand with docker compose exec, and the backup all run in the worker container.
RESTORE_LOCK_NAME = "welldb-restore-check.lock"
# How long one DROP DATABASE of a drill database may take (it removes files the size of the live database)
DROP_STATEMENT_TIMEOUT = "5min"


def restore_lock_path():
    return os.path.join(tempfile.gettempdir(), RESTORE_LOCK_NAME)


@contextlib.contextmanager
def restore_lock():
    """Hold the restore drill's lock for the block: yields True if it was taken, False if a drill holds it."""
    import fcntl
    fd = os.open(restore_lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        os.close(fd)   # closing the file releases the lock


def restore_settings(env=None):
    """(admin, live): the settings the drill creates and drops its database with (RESTORE_CHECK_DATABASE_URL, else
    DATABASE_URL), and the live database's (DATABASE_URL). ValueError if a URL is unusable."""
    env = os.environ if env is None else env
    live = parse_database_url((env.get("DATABASE_URL") or "").strip())
    admin = parse_database_url((env.get("RESTORE_CHECK_DATABASE_URL") or "").strip()
                               or (env.get("DATABASE_URL") or "").strip())
    return admin, live


def leftover_restore_databases(names, protected):
    """The names among `names` that are restore drill databases (RESTORE_DATABASE_PATTERN), leaving out those in
    `protected` (the live and admin databases, which a drill may never use)."""
    return sorted(name for name in names if RESTORE_DATABASE_PATTERN.match(name) and name not in set(protected))


def list_databases(settings):
    """Every database name on the server `settings` points at."""
    import psycopg2
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '1min'")
            cur.execute("SELECT datname FROM pg_database")
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def drop_restore_database(settings, name, protected=()):
    """DROP DATABASE IF EXISTS `name` WITH (FORCE) on the server `settings` points at (PostgreSQL 13+): FORCE ends the
    sessions still connected to it, such as the backend of a pg_restore that was stopped. Refuses any name that isn't
    a restore drill database, or is in `protected`."""
    import psycopg2
    from psycopg2 import sql
    if not RESTORE_DATABASE_PATTERN.match(name) or name in set(protected):
        raise ValueError(f"refusing to drop {name}: only a restore drill database ({RESTORE_DATABASE_PREFIX}...) "
                         f"that no live setting names is ever dropped")
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Bounded, so a drop that waits (on a busy catalog, say) can't hold up the backup or the worker
            cur.execute("SET statement_timeout = %s", (DROP_STATEMENT_TIMEOUT,))
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    finally:
        conn.close()


def drop_leftover_restore_databases(log=print, env=None):
    """Drop every restore drill database left on the server, unless a drill is running now (it holds restore_lock).
    Returns the names dropped. psycopg2.Error or ValueError if listing or dropping fails."""
    with restore_lock() as free:
        if not free:
            log("A restore drill is running; its database isn't a leftover, so nothing was dropped.")
            return []
        admin, live = restore_settings(env)
        protected = {admin["database"], live["database"]}
        dropped = []
        for name in leftover_restore_databases(list_databases(admin), protected):
            drop_restore_database(admin, name, protected)
            log(f"Dropped {name}, a restore drill database left behind by a drill that didn't finish")
            dropped.append(name)
        return dropped
