# Applies the numbered SQL files in db/migrations/ (0001_name.sql, 0002_name.sql, ...) that haven't run yet, in
# order, and records each one in the schema_migrations table so it never runs twice.
#   python scripts/migrate.py              apply pending migrations (DATABASE_URL from the environment)
#   python scripts/migrate.py --status     list applied and pending migrations; changes nothing
#   python scripts/migrate.py --dry-run    print the SQL that would run; changes nothing
#
# A file runs in one transaction, so a failure leaves nothing half-applied. A file whose first line is
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

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[1] / "db" / "migrations"
NUMBERED = re.compile(r"^(\d{4})_\w+\.sql$")
NO_TRANSACTION = "-- migrate: no-transaction"
LOCK_KEY = 4_206_190_001   # arbitrary pg_advisory_lock key, so two runs at once take turns instead of racing


class MigrationError(Exception):
    pass


def migration_files(directory=MIGRATIONS_DIR):
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


def apply(engine, path):
    sql = read(path)
    record = text("INSERT INTO schema_migrations (version) VALUES (:version)")
    if not needs_autocommit(sql):
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
            conn.execute(record, {"version": path.stem})
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql(sql)
        # A CREATE INDEX CONCURRENTLY that failed earlier leaves an INVALID index, which IF NOT EXISTS then
        # skips with only a notice. Don't record the migration as done while such an index exists.
        if engine.dialect.name == "postgresql":
            invalid = [r[0] for r in conn.execute(text(
                "SELECT indexrelid::regclass::text FROM pg_index WHERE NOT indisvalid ORDER BY 1"))]
            if invalid:
                raise MigrationError(
                    f"{path.name} not recorded: invalid index(es) {', '.join(invalid)}, left by a failed concurrent "
                    f"build. Drop each with DROP INDEX CONCURRENTLY <name>; and run the migration again.")
        conn.execute(record, {"version": path.stem})


def migrate(engine, directory=MIGRATIONS_DIR, log=print):
    migration_files(directory)   # fail on duplicate numbers before touching the database
    postgres = engine.dialect.name == "postgresql"
    # The lock lives on its own autocommit connection: an open transaction here would make CREATE INDEX
    # CONCURRENTLY wait for it forever.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        if postgres:
            lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version varchar(255) PRIMARY KEY, "
                                  "applied_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
            todo = pending(engine, directory)   # read after taking the lock, so a run that just finished counts
            for path in todo:
                log(f"[INFO] applying {path.name}")
                apply(engine, path)
        finally:
            if postgres:
                lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
    log(f"[INFO] {len(todo)} migration(s) applied" if todo else "[INFO] nothing to apply")
    return [p.stem for p in todo]


def main():
    parser = argparse.ArgumentParser(description="Apply pending database migrations from db/migrations/.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="list applied and pending migrations")
    mode.add_argument("--dry-run", action="store_true", help="print the SQL of pending migrations")
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
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
