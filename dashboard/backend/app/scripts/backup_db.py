# Backs up the PostgreSQL database with pg_dump (custom format, compressed) into BACKUP_DIR, checks that the dump
# can be read back and holds the main tables' data, then deletes old dumps. scripts/scheduler_temp.py runs it every
# night at 03:15 Toronto time; it can also be run by hand in the worker container.
#
#   python scripts/backup_db.py                   back up now, then apply retention
#   python scripts/backup_db.py --no-prune        back up, delete nothing
#   python scripts/backup_db.py --prune-only      apply retention to the existing dumps only
#
# Settings (environment):
#   DATABASE_URL            the database to dump (the app's own URL; the password goes to pg_dump through a
#                           temporary 0600 password file, never on its command line)
#   BACKUP_DIR              where dumps go (default /app/backups, a bind mount of ./backups on the host)
#   BACKUP_KEEP_DAILY       how many days keep their newest dump (default 7)
#   BACKUP_KEEP_WEEKLY      how many ISO weeks keep their newest dump (default 8)
#   BACKUP_EXCLUDE_TABLES   tables left out, with the sequences they own. Default "auto": every table the role can
#                           read is dumped, and any it can't are left out and named in a WARNING: line (on the VM
#                           the app connects as postgres, which reads everything). A comma-separated list leaves
#                           out exactly those; an empty value leaves out nothing.
#   BACKUP_EXPECT_TABLES    tables the dump must hold data for (default sensor_measurements,sampling_measurements)
#   BACKUP_MIN_FREE_MB      free space to leave on the disk after a dump the size of the last one (default 2048):
#                           the database usually shares the disk, and must never be the one to run out
#   PG_BIN_DIR              where pg_dump and pg_restore are (default /usr/lib/postgresql/13/bin, else PATH)
#
# Dumps are named welldb-YYYYmmdd-HHMM.dump (Toronto time). Only files with that name are ever deleted. A dump is
# written as .welldb-*.partial and renamed once it is complete and checked, so a failed run leaves no file that
# looks like a backup; one left by a run that was killed is deleted by the next run. Only one run at a time: a run
# holds a lock (.backup.lock in BACKUP_DIR) and another one refuses to start.
# Exit code 0 means a checked dump was written (tables left out because the role can't read them, and a failure of
# the retention step after it, are printed as WARNING: lines); 1 means it wasn't, and the reason is printed.

import argparse
import fcntl
import os
import pathlib
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from utils.backup import (  # noqa: E402
    AUTO_EXCLUDE, DEFAULT_EXPECT_TABLES, csv_setting, dump_name, dumps_in, dumps_to_prune, exclusion_setting,
    human_size, libpq_env, missing_tables, owned_sequences, parse_database_url, pg_tool, quoted_pattern,
    remove_stale_passfiles, run_tool, stale_partials, table_data_entries, unreadable_relations,
)

SITE_TZ = ZoneInfo("America/Toronto")
# Limits for each step. Together (105 min) they stay under the scheduler's 2 h limit for the whole run
# (BACKUP_TIMEOUT_S in scripts/scheduler_temp.py), so a slow step fails here, with its own message and cleanup,
# before the scheduler has to stop the run.
DUMP_TIMEOUT_S = 80 * 60
LIST_TIMEOUT_S = 10 * 60
READ_BACK_TIMEOUT_S = 15 * 60
LOCK_NAME = ".backup.lock"


class BackupError(Exception):
    """A backup that failed for a reason worth reporting as is (no traceback needed)."""


def int_setting(name, default, minimum=0):
    # A whole-number setting from the environment; a bad value stops the backup rather than being guessed.
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    if not raw.isdigit() or int(raw) < minimum:
        raise BackupError(f"{name} must be a whole number of at least {minimum}, got {raw!r}")
    return int(raw)


def tool_error(what, error):
    """A BackupError for a failed pg_dump or pg_restore run, with the end of its stderr (which names the cause,
    e.g. a permission or version problem, and never the password, which it doesn't know)."""
    if isinstance(error, subprocess.TimeoutExpired):
        return BackupError(f"{what} was stopped after {error.timeout // 60:.0f} min without finishing")
    stderr = (error.stderr or "").strip()[-1500:]
    return BackupError(f"{what} failed with exit code {error.returncode}: {stderr or '(no output)'}")


def check_free_space(directory, previous_size, min_free_mb):
    """Refuse to start if a dump the size of the last one would leave less than `min_free_mb` free."""
    free = shutil.disk_usage(directory).free
    needed = previous_size + min_free_mb * 1024 * 1024
    if free < needed:
        raise BackupError(f"not enough disk space in {directory}: {human_size(free)} free, but a dump like the last "
                          f"one ({human_size(previous_size)}) plus BACKUP_MIN_FREE_MB={min_free_mb} needs "
                          f"{human_size(needed)}. Free space or lower BACKUP_KEEP_DAILY/BACKUP_KEEP_WEEKLY.")


def verify_dump(path, expected, env, log=print):
    """Read the dump back with pg_restore: its table of contents must list data for every `expected` table, and
    the whole archive must decompress (pg_restore to /dev/null), so a truncated or damaged file fails here."""
    pg_restore = pg_tool("pg_restore")
    try:
        listing = run_tool([pg_restore, "--list", str(path)], env, LIST_TIMEOUT_S).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise tool_error("pg_restore --list", e)
    entries = table_data_entries(listing)
    missing = missing_tables(listing, expected)
    if missing:
        raise BackupError(f"the dump has no data for {', '.join(missing)} ({len(entries)} tables with data)")
    try:
        run_tool([pg_restore, "--file", os.devnull, str(path)], env, READ_BACK_TIMEOUT_S)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise tool_error("reading the whole dump back (pg_restore)", e)
    log(f"Checked: {len(entries)} tables with data, including {', '.join(expected)}; the archive reads back in full.")
    return entries


def prune(directory, keep_daily, keep_weekly, log=print):
    """Delete this job's dumps that retention doesn't keep. Returns the names deleted."""
    names = os.listdir(directory)
    doomed = dumps_to_prune(names, keep_daily, keep_weekly)
    for name in doomed:
        os.remove(os.path.join(directory, name))
        log(f"Deleted old dump {name}")
    kept = len(dumps_in(names)) - len(doomed)
    log(f"Retention: {kept} dumps kept (newest per day for {keep_daily} days, per week for {keep_weekly} weeks), "
        f"{len(doomed)} deleted.")
    return doomed


def prepare_dir(directory):
    """Create the backup directory (0700) if needed; from here on, files are created readable by their owner only."""
    os.umask(0o077)   # dumps hold all the data
    os.makedirs(directory, exist_ok=True)
    os.chmod(directory, 0o700)


def take_lock(directory):
    """Hold the backup lock for the rest of this process (the OS releases it when the process ends, however it
    ends). BackupError if another run holds it."""
    handle = open(os.path.join(directory, LOCK_NAME), "a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise BackupError(f"another backup is running (it holds {os.path.join(directory, LOCK_NAME)})")
    return handle


def remove_leftovers(directory, log=print):
    """Delete what a killed run left behind: unfinished dumps in `directory` and old temporary password files."""
    for name in stale_partials(os.listdir(directory)):
        os.remove(os.path.join(directory, name))
        log(f"Deleted {name}, left unfinished by an earlier run that was stopped")
    if remove_stale_passfiles():
        log("Deleted temporary password files left by an earlier run that was stopped")


def warn_stderr(message):
    print(f"WARNING: {message}", file=sys.stderr)


def exclusions(settings, exclude, warn=warn_stderr):
    """(tables left out, pg_dump --exclude-table patterns) for `exclude`: a list of tables, or AUTO_EXCLUDE for
    those the role can't read. With AUTO_EXCLUDE, any such table or sequence is named in a warning (the scheduler
    sends WARNING: lines to Sentry), since the backup is then incomplete."""
    if exclude == AUTO_EXCLUDE:
        tables, sequences = unreadable_relations(settings)
        left_out = tables + sequences
        if left_out:
            warn(f"the database role can't read {', '.join(left_out)}, so the backup leaves "
                 f"{'it' if len(left_out) == 1 else 'them'} out. To back up everything, grant it SELECT or connect "
                 f"as a role that can read everything (or list them in BACKUP_EXCLUDE_TABLES to leave them out on "
                 f"purpose).")
        patterns = [quoted_pattern(*name.split(".", 1)) for name in left_out]
        exclude = tables
    else:
        patterns = list(exclude)
    patterns += [p for p in owned_sequences(settings, exclude) if p not in patterns]
    return exclude, patterns


def back_up(directory, settings, exclude, expected, min_free_mb, now=None, log=print, warn=warn_stderr):
    """Dump the database into `directory` and check the dump. Returns the path of the new dump. `exclude` is a list
    of tables or AUTO_EXCLUDE (see exclusions). The caller holds the backup lock (take_lock)."""
    remove_leftovers(directory, log)
    existing = dumps_in(os.listdir(directory))
    previous_size = os.path.getsize(os.path.join(directory, existing[0][1])) if existing else 0
    check_free_space(directory, previous_size, min_free_mb)

    now = now or datetime.now(SITE_TZ)
    final = pathlib.Path(directory) / dump_name(now)
    partial = pathlib.Path(directory) / f".{final.name}.partial"
    cmd = [pg_tool("pg_dump"), "--format=custom", "--no-password", "--lock-wait-timeout=300000",
           f"--file={partial}"]
    try:
        exclude, patterns = exclusions(settings, exclude, warn)
    except psycopg2.Error as e:
        raise BackupError(f"could not connect to look up which tables to leave out: {str(e).strip()}")
    cmd += [f"--exclude-table={pattern}" for pattern in patterns]
    log(f"Dumping database {settings['database']} on {settings.get('host') or 'the local socket'} to {final.name}"
        + (f", without {', '.join(exclude)} and their sequences" if exclude else ", every table"))
    try:
        with libpq_env(settings) as env:
            try:
                run_tool(cmd, env, DUMP_TIMEOUT_S)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                raise tool_error("pg_dump", e)
            verify_dump(partial, expected, env, log)
        os.replace(partial, final)
    finally:
        if partial.exists():
            partial.unlink()
    log(f"Backup written: {final} ({human_size(final.stat().st_size)})")
    return final


def stop_on_sigterm(signum, frame):
    """SIGTERM (the scheduler stopping a run that passed its time limit) ends the run through SystemExit, so the
    cleanup in back_up and libpq_env still runs: the unfinished dump and the password file are deleted, and pg_dump
    is stopped. `docker stop` doesn't reach this process (the scheduler starts it in a session of its own), so the
    container stopping kills it outright; the next run then deletes what it left behind (remove_leftovers)."""
    raise SystemExit(128 + signum)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Back up the database with pg_dump and keep N daily + M weekly dumps.")
    parser.add_argument("--dir", default=os.getenv("BACKUP_DIR", "/app/backups"), help="backup directory")
    parser.add_argument("--no-prune", action="store_true", help="don't delete old dumps")
    parser.add_argument("--prune-only", action="store_true", help="only apply retention to the existing dumps")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        keep_daily = int_setting("BACKUP_KEEP_DAILY", 7, minimum=1)
        keep_weekly = int_setting("BACKUP_KEEP_WEEKLY", 8)
        prepare_dir(args.dir)
        lock = take_lock(args.dir)
    except (BackupError, OSError) as e:
        print(f"ERROR: backup failed: {e}", file=sys.stderr)
        return 1
    with lock:   # held for the whole run, retention included
        return run(args, keep_daily, keep_weekly)


def run(args, keep_daily, keep_weekly):
    """The backup (unless --prune-only), then retention (unless --no-prune). The exit code."""
    try:
        if not args.prune_only:
            settings = parse_database_url(os.getenv("DATABASE_URL", "").strip())
            exclude = exclusion_setting()
            expected = csv_setting(os.getenv("BACKUP_EXPECT_TABLES", DEFAULT_EXPECT_TABLES))
            back_up(args.dir, settings, exclude, expected, int_setting("BACKUP_MIN_FREE_MB", 2048))
    except (BackupError, ValueError, RuntimeError, OSError) as e:
        print(f"ERROR: backup failed: {e}", file=sys.stderr)
        return 1
    if not args.no_prune:
        try:
            prune(args.dir, keep_daily, keep_weekly)
        except OSError as e:
            if args.prune_only:
                print(f"ERROR: deleting old dumps failed: {e}", file=sys.stderr)
                return 1
            # The new dump is written and checked; the next run's retention tries the old ones again.
            print(f"WARNING: the backup is fine, but deleting old dumps failed: {e}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
