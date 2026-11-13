# Restore drill: restores a backup (by default the newest dump in BACKUP_DIR) into a throwaway database, compares
# each table's row count with the live database, then drops the throwaway database. It shows that the dumps can
# actually be restored, which the nightly check of the archive alone can't. Optional, and run by hand, e.g. monthly:
#
#   docker compose exec worker python scripts/restore_check.py
#   docker compose exec worker python scripts/restore_check.py --file /app/backups/welldb-20261111-0315.dump
#
# Creating a database needs the CREATEDB privilege, which the app's role well_app (db/roles.sql) doesn't keep. Grant
# it for the drill (as postgres: ALTER ROLE well_app CREATEDB; and NOCREATEDB after), or point
# RESTORE_CHECK_DATABASE_URL at a role that has it; that role creates, restores into and drops the throwaway
# database, and the live counts are still read with DATABASE_URL, in a read-only session.
#
# The live database keeps changing (new readings every 10 minutes), so counts that grew since the dump are
# expected and reported, not failures. It fails (exit 1) if the restore fails, a table the live database has is
# missing from the restore, or a table restored empty while the live one has rows. A missing table isn't a failure
# when BACKUP_EXCLUDE_TABLES lists it, or (by default, "auto") when the role can't read it, which is why the
# backup left it out.
#
# The throwaway database is dropped first if it exists (left by an interrupted drill), so its name must start with
# welldb_restore_check. The restore takes about as much disk as the live database: the drill refuses to start
# unless the backup folder's disk (assumed to be the database's, as on the VM) has the live database's size plus
# BACKUP_MIN_FREE_MB (default 2048) free. --no-space-check skips that when the database is on another disk.

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402

from utils.backup import (  # noqa: E402
    AUTO_EXCLUDE, dumps_in, exclusion_setting, human_size, libpq_env, parse_database_url, pg_tool, psycopg2_kwargs,
    run_tool, with_database,
)

DEFAULT_RESTORE_DATABASE = "welldb_restore_check"
# The only names the drill restores into (and so drops first): welldb_restore_check, optionally with a suffix
RESTORE_DATABASE_PATTERN = re.compile(r"^welldb_restore_check[a-z0-9_]*$")
RESTORE_TIMEOUT_S = 3 * 60 * 60

# Every table outside the system schemas, and whether this role may read it (run without parameters, so % is literal)
TABLES_SQL = """
SELECT schemaname, tablename, has_table_privilege(format('%I.%I', schemaname, tablename), 'SELECT')
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND schemaname NOT LIKE 'pg\\_%'
ORDER BY 1, 2
"""
UNREADABLE = "not readable"


class RestoreCheckError(Exception):
    pass


def latest_dump(directory):
    # The newest welldb-*.dump in the backup folder (dumps_in() lists them newest first).
    dumps = dumps_in(os.listdir(directory))
    if not dumps:
        raise RestoreCheckError(f"no welldb-*.dump files in {directory}")
    return pathlib.Path(directory) / dumps[0][1]


def row_counts(settings, read_only=False):
    """{(schema, table): rows} for the tables in the database `settings` points at; UNREADABLE for a table this role
    may not read."""
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    try:
        if read_only:
            conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute(TABLES_SQL)
            tables = cur.fetchall()
            counts = {}
            for schema, table, readable in tables:
                if not readable:
                    counts[(schema, table)] = UNREADABLE
                    continue
                cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table)))
                counts[(schema, table)] = cur.fetchone()[0]
        conn.rollback()
        return counts
    finally:
        conn.close()


def check_free_space(directory, live, min_free_mb):
    """Refuse to restore unless `directory`'s disk has the live database's size plus `min_free_mb` free."""
    conn = psycopg2.connect(**psycopg2_kwargs(live))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            size = cur.fetchone()[0]
    finally:
        conn.close()
    free = shutil.disk_usage(directory).free
    needed = size + min_free_mb * 1024 * 1024
    if free < needed:
        raise RestoreCheckError(f"not enough disk space: the restore needs about the live database's size "
                                f"({human_size(size)}) plus BACKUP_MIN_FREE_MB={min_free_mb}, {human_size(needed)} in "
                                f"all, and {directory}'s disk has {human_size(free)} free (use --no-space-check if the "
                                f"database is on another disk)")
    print(f"Disk space: {human_size(free)} free, about {human_size(size)} needed for the restore.")


def admin_execute(settings, statement):
    """Run CREATE/DROP DATABASE (which can't run in a transaction) on the server `settings` points at."""
    conn = psycopg2.connect(**psycopg2_kwargs(settings))
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(statement)
    finally:
        conn.close()


def compare(restored, live, excluded):
    """Lines describing each table, and the problems that make the check fail. `excluded` is BACKUP_EXCLUDE_TABLES
    (exclusion_setting): a list of tables left out on purpose, or AUTO_EXCLUDE, under which the backup leaves out
    the tables its role can't read, so a table missing from the backup is expected when the live role can't read it
    either (the drill reads the live counts with the same DATABASE_URL as the backup)."""
    lines, problems = [], []
    auto = excluded == AUTO_EXCLUDE
    excluded = set() if auto else set(excluded)
    for key in sorted(set(restored) | set(live)):
        name = f"{key[0]}.{key[1]}"
        r, lv = restored.get(key), live.get(key)
        if r is None:
            if auto and lv == UNREADABLE:
                lines.append(f"  {name:<40} not in the backup (this role can't read it; the backup log warned)")
            elif key[1] in excluded or name in excluded:
                lines.append(f"  {name:<40} not in the backup (excluded on purpose)")
            else:
                lines.append(f"  {name:<40} MISSING from the backup (live: {lv})")
                problems.append(f"{name} is missing from the backup")
            continue
        if lv is None or lv == UNREADABLE:
            lines.append(f"  {name:<40} restored {r:>12}  live: {'not readable' if lv else 'gone'}")
            continue
        if r == 0 and lv > 0:
            problems.append(f"{name} restored empty, but the live table has {lv} rows")
        note = "same" if r == lv else (f"+{lv - r} live since the dump" if lv > r else f"{r - lv} fewer live now")
        lines.append(f"  {name:<40} restored {r:>12}  live {lv:>12}  ({note})")
    return lines, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Restore a backup into a throwaway database and compare row counts.")
    parser.add_argument("--file", help="the dump to restore (default: the newest in --dir)")
    parser.add_argument("--dir", default=os.getenv("BACKUP_DIR", "/app/backups"), help="backup directory")
    parser.add_argument("--database", default=DEFAULT_RESTORE_DATABASE,
                        help="name of the throwaway database (must start with welldb_restore_check)")
    parser.add_argument("--no-space-check", action="store_true",
                        help="don't check free disk space first (the database is on another disk)")
    parser.add_argument("--keep", action="store_true", help="leave the throwaway database in place afterwards")
    args = parser.parse_args(argv)

    created = False
    admin = None
    try:
        live = parse_database_url(os.getenv("DATABASE_URL", "").strip())
        admin = parse_database_url((os.getenv("RESTORE_CHECK_DATABASE_URL") or "").strip()
                                   or os.getenv("DATABASE_URL", "").strip())
        if not RESTORE_DATABASE_PATTERN.match(args.database):
            raise RestoreCheckError(f"refusing to restore into {args.database}: the throwaway database's name must "
                                    f"start with welldb_restore_check (lowercase letters, digits and _ after it)")
        if args.database in (live["database"], admin["database"]):
            raise RestoreCheckError(f"refusing to restore into {args.database}: that is a live database")
        dump = pathlib.Path(args.file) if args.file else latest_dump(args.dir)
        if not args.no_space_check:
            min_free = (os.getenv("BACKUP_MIN_FREE_MB") or "2048").strip()
            if not min_free.isdigit():
                raise RestoreCheckError(f"BACKUP_MIN_FREE_MB must be a whole number, got {min_free!r}")
            check_free_space(dump.parent, live, int(min_free))
        print(f"Restoring {dump} into a new database {args.database}")

        # Only a database of this exact name, left over from an earlier drill that was interrupted, is dropped.
        name = sql.Identifier(args.database)
        admin_execute(admin, sql.SQL("DROP DATABASE IF EXISTS {}").format(name))
        admin_execute(admin, sql.SQL("CREATE DATABASE {}").format(name))
        created = True
        target = with_database(admin, args.database)
        with libpq_env(target) as env:
            try:
                run_tool([pg_tool("pg_restore"), "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction",
                          f"--dbname={args.database}", str(dump)], env, RESTORE_TIMEOUT_S)
            except subprocess.CalledProcessError as e:
                raise RestoreCheckError(f"pg_restore failed: {(e.stderr or '').strip()[-1500:]}")
            except subprocess.TimeoutExpired:
                raise RestoreCheckError(f"pg_restore was stopped after {RESTORE_TIMEOUT_S // 60} min")
        print("Restored. Counting rows (restored vs live)...")
        restored = row_counts(target)
        current = row_counts(live, read_only=True)
        lines, problems = compare(restored, current, exclusion_setting())
        print("\n".join(lines))
        if problems:
            raise RestoreCheckError("; ".join(problems))
        print(f"Restore check passed: {len(restored)} tables restored from {dump.name}.")
        return 0
    except (RestoreCheckError, ValueError, RuntimeError, OSError, psycopg2.Error) as e:
        hint = ""
        if isinstance(e, psycopg2.Error) and getattr(e, "pgcode", None) == "42501":
            hint = (" (permission denied: creating a database needs CREATEDB; grant it to the app role or set "
                    "RESTORE_CHECK_DATABASE_URL to a role that has it)")
        print(f"ERROR: restore check failed: {str(e).strip()}{hint}", file=sys.stderr)
        return 1
    finally:
        if created and not args.keep:
            try:
                admin_execute(admin, sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(args.database)))
                print(f"Dropped the throwaway database {args.database}.")
            except psycopg2.Error as e:
                print(f"ERROR: could not drop {args.database}; drop it by hand: {str(e).strip()}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
