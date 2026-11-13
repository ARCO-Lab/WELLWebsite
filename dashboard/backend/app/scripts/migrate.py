# Applies the numbered SQL files in db/migrations/ (0001_name.sql, 0002_name.sql, ...) that haven't run yet, in
# order, and records each one in the schema_migrations table so it never runs twice.
#   python scripts/migrate.py              apply pending migrations (DATABASE_URL from the environment)
#   python scripts/migrate.py --status     list applied and pending migrations; changes nothing
#   python scripts/migrate.py --dry-run    print the SQL that would run; changes nothing
#
# A file runs in one transaction, so a failure leaves nothing half-applied. On PostgreSQL that transaction waits at
# most LOCK_TIMEOUT for a lock: an ALTER TABLE queued behind a long export's read would otherwise block every query
# on that table behind it, so it fails instead and can be run again later. A file whose first line is
# "-- migrate: no-transaction" runs in autocommit instead; statements such as CREATE INDEX CONCURRENTLY require
# it. Such a file must hold a single statement, because PostgreSQL treats several as one transaction block.
# Dated one-off fixes (e.g. 2026-11-10_swap_air_soil_temperature.sql) aren't numbered, so they're left alone:
# they use psql commands and are run by hand with psql, as their own comments say.
# Never rename or renumber a file once it has been applied: the runner would see it as new and run it again.

import argparse
import os
import pathlib
import re
import sys

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from db.database import CONNECT_ARGS  # noqa: E402

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[1] / "db" / "migrations"
NUMBERED = re.compile(r"^(\d{4})_\w+\.sql$")
NO_TRANSACTION = "-- migrate: no-transaction"
LOCK_KEY = 4_206_190_001   # arbitrary pg_advisory_lock key, so two runs at once take turns instead of racing
LOCK_TIMEOUT = os.getenv("MIGRATE_LOCK_TIMEOUT", "5s")   # see the top of this file; "0" waits for ever


class MigrationError(Exception):
    pass


def migration_files(directory=MIGRATIONS_DIR):
    """The numbered migration files in order. Raises MigrationError if two share a number."""
    files = sorted(p for p in pathlib.Path(directory).iterdir() if NUMBERED.match(p.name))
    numbers = [NUMBERED.match(p.name).group(1) for p in files]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        raise MigrationError(f"two migration files share the number {', '.join(duplicates)}; renumber the new one")
    return files


def read(path):
    return path.read_text(encoding="utf-8-sig")   # -sig: a byte-order mark mustn't hide the marker line


def applied_versions(engine):
    if not inspect(engine).has_table("schema_migrations"):
        return set()
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}


def pending(engine, directory=MIGRATIONS_DIR):
    done = applied_versions(engine)
    return [p for p in migration_files(directory) if p.stem not in done]


def needs_autocommit(sql):
    lines = sql.strip().splitlines()
    return bool(lines) and lines[0].strip().lower() == NO_TRANSACTION


def mentions(sql, name):
    """Whether the SQL names this index, bare or after a schema prefix (public.ix_a), as a whole word."""
    return re.search(rf"(?<![\w$]){re.escape(name)}(?![\w$])", sql, re.IGNORECASE) is not None


def apply(engine, path, log=print):
    """Runs one migration file and records it in schema_migrations: in one transaction, or in autocommit when the
    file starts with the no-transaction marker (and then only after checking its indexes were built)."""
    sql = read(path)
    record = text("INSERT INTO schema_migrations (version) VALUES (:version)")
    if not needs_autocommit(sql):
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("SELECT set_config('lock_timeout', :timeout, true)"), {"timeout": LOCK_TIMEOUT})
            conn.exec_driver_sql(sql, execution_options={"no_parameters": True})   # "%" reaches the driver as is
            conn.execute(record, {"version": path.stem})
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql(sql, execution_options={"no_parameters": True})   # "%" reaches the driver as is
        # A CREATE INDEX CONCURRENTLY that failed earlier leaves an INVALID index, which IF NOT EXISTS then
        # skips with only a notice. Don't record the migration as done while an index it names is invalid;
        # other invalid indexes aren't this migration's doing, so they only get a warning.
        if engine.dialect.name == "postgresql":
            invalid = [r[0] for r in conn.execute(text(
                "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE NOT i.indisvalid ORDER BY 1"))]
            own = [name for name in invalid if mentions(sql, name)]
            if own:
                raise MigrationError(
                    f"{path.name} not recorded: its index {', '.join(own)} is INVALID, left by a failed concurrent "
                    f"build. Drop it with DROP INDEX CONCURRENTLY <name>; and run the migration again.")
            if invalid:
                log(f"[WARN] invalid index(es) {', '.join(invalid)} in the database, not from {path.name}; "
                    f"recording it anyway. Drop them with DROP INDEX CONCURRENTLY <name>; when convenient.")
        conn.execute(record, {"version": path.stem})


def migrate(engine, directory=MIGRATIONS_DIR, log=print):
    """Applies every pending migration in order, holding an advisory lock so two runs can't overlap. Returns the
    versions applied."""
    migration_files(directory)   # fail on duplicate numbers before touching the database
    postgres = engine.dialect.name == "postgresql"
    # A second run refuses to start rather than wait: a session waiting for the lock holds a snapshot, and
    # CREATE INDEX CONCURRENTLY in the first run would wait for that snapshot forever. The lock lives on its own
    # autocommit connection for the same reason (an open transaction there would block the build too).
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        if postgres and not lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar():
            raise MigrationError("another migrate.py run holds the lock; wait for it to finish")
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version varchar(255) PRIMARY KEY, "
                                  "applied_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
            todo = pending(engine, directory)   # read after taking the lock, so a run that just finished counts
            for path in todo:
                log(f"[INFO] applying {path.name}")
                apply(engine, path, log)
        finally:
            if postgres:
                try:
                    lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                except Exception:   # don't hide the original error; the lock goes with the session anyway
                    pass
    log(f"[INFO] {len(todo)} migration(s) applied" if todo else "[INFO] nothing to apply")
    return [p.stem for p in todo]


def main():
    parser = argparse.ArgumentParser(description="Apply pending database migrations from db/migrations/.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="list applied and pending migrations")
    mode.add_argument("--dry-run", action="store_true", help="print the SQL of pending migrations")
    args = parser.parse_args()

    url = os.environ["DATABASE_URL"]
    # The app's connect timeout and TCP keepalives, so an unreachable database fails in seconds instead of hanging.
    engine = create_engine(url, connect_args=dict(CONNECT_ARGS) if url.startswith("postgresql") else {})
    try:
        if args.status:
            done = applied_versions(engine)
            for path in migration_files():
                print(f"{'applied' if path.stem in done else 'pending'}  {path.name}")
        elif args.dry_run:
            for path in pending(engine):
                sql = read(path)
                print(f"-- {path.name} ({'autocommit' if needs_autocommit(sql) else 'one transaction'})\n{sql}")
        else:
            migrate(engine)
    except MigrationError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
