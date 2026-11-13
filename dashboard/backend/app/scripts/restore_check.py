# Restore drill: restores a backup (by default the newest dump in BACKUP_DIR) into a throwaway database, compares
# each table's row count with the counts recorded when the dump was taken and with the live database, then drops the
# throwaway database. It shows that the dumps can actually be restored, which the nightly check of the archive alone
# can't. scripts/scheduler_temp.py runs it once a month (RESTORE_CHECK_DAY, default the 2nd, at 05:30 Toronto time,
# after the night's backup) and pings HEALTHCHECK_URL_RESTORE; it can also be run by hand:
#
#   docker compose exec worker python scripts/restore_check.py
#   docker compose exec worker python scripts/restore_check.py --file /app/backups/welldb-20261111-0315.dump
#   docker compose exec worker python scripts/restore_check.py --drop-leftovers   only drop databases left behind
#
# Creating a database needs the CREATEDB privilege. On the VM the app connects as postgres, which has it. A role
# without it can be granted it once (as postgres: ALTER ROLE <role> CREATEDB;), or RESTORE_CHECK_DATABASE_URL can
# point at a role that has it, such as a dedicated well_restore role with CREATEDB where the database has one; that
# role creates, restores into and drops the throwaway database, and the live counts are still read with
# DATABASE_URL, in a read-only session.
#
# The throwaway database is a full copy of the live one, so it must not outlive the drill. It is dropped with
# DROP DATABASE ... WITH (FORCE), which also ends a session still connected to it (a pg_restore stopped by SIGTERM),
# and every count(*) is stopped after 20 minutes. A drill killed outright (SIGKILL, out of memory) can't drop it: the
# worker drops any welldb_restore_check* database left behind at start-up, after a failed drill and before each
# nightly backup, and the daily digest lists any still there. A running drill holds a lock (in the temporary folder)
# so its own database is never taken for a leftover, and only one drill runs at a time.
#
# The live database keeps changing (new readings every 10 minutes), so counts that grew since the dump are
# expected and reported, not failures. It fails (exit 1) if the restore fails, a table the live database has is
# missing from the restore, a table restored empty while the live one has rows, or a table restored with fewer rows
# than its source had when the dump was taken. Those counts are recorded beside each dump by the backup
# (.<dump>.counts.json, for the BACKUP_EXPECT_TABLES tables): an exact count must come back in full, and an estimate
# (large tables) within RESTORE_CHECK_TOLERANCE_PCT percent (default 2). For a dump without that record (one taken
# before it was kept), those tables must instead have at least 95% of their live rows. A missing table isn't a
# failure when BACKUP_EXCLUDE_TABLES lists it, or (by default, "auto") when the role can't read it, which is why the
# backup left it out.
#
# It never touches the live database's data: the live counts are read in a read-only session, and the restore goes
# into a database of its own. That database is dropped first if it exists (left by an interrupted drill), so its name
# must start with welldb_restore_check, and it may never be the database DATABASE_URL or RESTORE_CHECK_DATABASE_URL
# names. The restore takes about as much disk as the live database: the drill refuses to start
# unless the backup folder's disk (assumed to be the database's, as on the VM) has the live database's size plus
# BACKUP_MIN_FREE_MB (default 2048) free. --no-space-check skips that when the database is on another disk.

import argparse
import os
import pathlib
import shutil
import signal
import subprocess
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402

from utils.backup import (  # noqa: E402
    AUTO_EXCLUDE, DEFAULT_EXPECT_TABLES, RESTORE_DATABASE_PATTERN, csv_setting, drop_leftover_restore_databases,
    drop_restore_database, dumps_in, exclusion_setting, human_size, libpq_env, load_dump_counts, pg_tool,
    psycopg2_kwargs, restore_lock, restore_settings, run_tool, with_database,
)

# How far below its recorded count an estimated count (a large table's, from the planner) may restore: the estimate
# comes from a sample and is off by a percent or so either way. Exact counts must come back in full.
DEFAULT_TOLERANCE_PCT = 2
# Without a recorded count, the BACKUP_EXPECT_TABLES tables must restore at least this share of their live rows (the
# newest dump is at most a day old, and these tables only grow by well under a percent a day)
LIVE_SHORTFALL_PCT = 5

# The only names the drill restores into (and so drops first) match RESTORE_DATABASE_PATTERN (utils/backup.py):
# welldb_restore_check, optionally with a suffix
DEFAULT_RESTORE_DATABASE = "welldb_restore_check"
RESTORE_TIMEOUT_S = 3 * 60 * 60
# Each count(*) is stopped after this long, so a count that hangs (a lock, a slow disk) ends the drill, and with it
# the throwaway database, instead of holding it until the scheduler kills the drill
COUNT_STATEMENT_TIMEOUT = "20min"

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
            cur.execute("SET statement_timeout = %s", (COUNT_STATEMENT_TIMEOUT,))
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


def matches(key, table):
    """Whether (schema, name) `key` is `table`, given as name or schema.name (as in BACKUP_EXPECT_TABLES)."""
    return table in (key[1], f"{key[0]}.{key[1]}")


def shortfalls(restored, live, recorded, expected, tolerance_pct=DEFAULT_TOLERANCE_PCT):
    """Problems for tables restored with too few rows. `recorded` is the dump's own record, ({table: rows at dump
    time}, {tables counted exactly}) from load_dump_counts, or None when it has none: then each `expected` table must
    restore at least (100 - LIVE_SHORTFALL_PCT)% of its live rows instead."""
    problems = []
    if recorded is not None:
        counts, exact = recorded
        for table, before in sorted(counts.items()):
            r = next((rows for key, rows in restored.items() if matches(key, table)), None)
            if not isinstance(r, int):
                continue   # missing from the restore (compare reports it) or not readable
            floor = before if table in exact else before * (1 - tolerance_pct / 100)
            if r < floor:
                problems.append(f"{table} restored {r:,} rows, but had {before:,} "
                                f"{'' if table in exact else '(estimated) '}when the dump was taken")
        return problems
    for table in expected:
        for key, r in restored.items():
            lv = live.get(key)
            if not (matches(key, table) and isinstance(r, int) and isinstance(lv, int)):
                continue
            if r < lv * (1 - LIVE_SHORTFALL_PCT / 100):
                problems.append(f"{table} restored {r:,} rows, more than {LIVE_SHORTFALL_PCT}% fewer than the "
                                f"{lv:,} live (the dump has no record of its own counts to compare with)")
    return problems


def compare(restored, live, excluded, recorded=None, expected=(), tolerance_pct=DEFAULT_TOLERANCE_PCT):
    """Lines describing each table, and the problems that make the check fail. `excluded` is BACKUP_EXCLUDE_TABLES
    (exclusion_setting): a list of tables left out on purpose, or AUTO_EXCLUDE, under which the backup leaves out
    the tables its role can't read, so a table missing from the backup is expected when the live role can't read it
    either (the drill reads the live counts with the same DATABASE_URL as the backup). `recorded`, `expected` and
    `tolerance_pct`: see shortfalls."""
    lines, problems = [], shortfalls(restored, live, recorded, expected, tolerance_pct)
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
    parser.add_argument("--keep", action="store_true", help="leave the throwaway database in place afterwards (the "
                        "next worker start or nightly backup drops it)")
    parser.add_argument("--drop-leftovers", action="store_true",
                        help="only drop restore drill databases left by drills that didn't finish, then exit")
    args = parser.parse_args(argv)
    if args.drop_leftovers:
        try:
            dropped = drop_leftover_restore_databases()
        except (ValueError, psycopg2.Error) as e:
            print(f"ERROR: could not drop the leftover restore drill databases: {str(e).strip()}", file=sys.stderr)
            return 1
        print(f"Leftover restore drill databases dropped: {', '.join(dropped) or 'none'}.")
        return 0
    with restore_lock() as free:
        if not free:
            print("ERROR: restore check failed: another restore drill is running", file=sys.stderr)
            return 1
        return drill(args)


def drill(args):
    """The drill itself, run while holding restore_lock (see main)."""
    # The scheduler stops a drill that runs too long with SIGTERM: ending through SystemExit still runs the finally
    # below, which drops the throwaway database.
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))

    created = False
    admin = None
    try:
        admin, live = restore_settings()
        if not RESTORE_DATABASE_PATTERN.match(args.database):
            raise RestoreCheckError(f"refusing to restore into {args.database}: the throwaway database's name must "
                                    f"start with welldb_restore_check (lowercase letters, digits and _ after it)")
        if args.database in (live["database"], admin["database"]):
            raise RestoreCheckError(f"refusing to restore into {args.database}: that is a live database")
        dump = pathlib.Path(args.file) if args.file else latest_dump(args.dir)
        expected = csv_setting(os.getenv("BACKUP_EXPECT_TABLES", DEFAULT_EXPECT_TABLES))
        tolerance = (os.getenv("RESTORE_CHECK_TOLERANCE_PCT") or str(DEFAULT_TOLERANCE_PCT)).strip()
        if not tolerance.isdigit() or int(tolerance) > 50:
            raise RestoreCheckError(f"RESTORE_CHECK_TOLERANCE_PCT must be a whole number from 0 to 50, got "
                                    f"{tolerance!r}")
        tolerance = int(tolerance)
        recorded = load_dump_counts(dump)   # ValueError if the record is damaged: that fails the drill too
        if recorded is None:
            print(f"{dump.name} has no record of its source's row counts; comparing {', '.join(expected)} with "
                  f"the live counts instead")
        else:
            print(f"Row counts when {dump.name} was taken: "
                  + ", ".join(f"{table} {rows:,}{'' if table in recorded[1] else ' (estimated)'}"
                              for table, rows in sorted(recorded[0].items())))
        if not args.no_space_check:
            min_free = (os.getenv("BACKUP_MIN_FREE_MB") or "2048").strip()
            if not min_free.isdigit():
                raise RestoreCheckError(f"BACKUP_MIN_FREE_MB must be a whole number, got {min_free!r}")
            check_free_space(dump.parent, live, int(min_free))
        print(f"Restoring {dump} into a new database {args.database}")

        # Only a database of this exact name, left over from an earlier drill that was interrupted, is dropped.
        protected = (live["database"], admin["database"])
        drop_restore_database(admin, args.database, protected)
        admin_execute(admin, sql.SQL("CREATE DATABASE {}").format(sql.Identifier(args.database)))
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
        lines, problems = compare(restored, current, exclusion_setting(), recorded, expected, tolerance)
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
                # FORCE: a pg_restore stopped by SIGTERM may still have its session open
                drop_restore_database(admin, args.database, (live["database"], admin["database"]))
                print(f"Dropped the throwaway database {args.database}.")
            except (psycopg2.Error, ValueError) as e:
                print(f"ERROR: could not drop {args.database}; drop it by hand: {str(e).strip()}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
