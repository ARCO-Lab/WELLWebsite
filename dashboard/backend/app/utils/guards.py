"""Safety checks for scripts that delete data. Pure: no database."""
import os

BACKUP_ADVICE = "Take a backup first (pg_dump), then run it again with ALLOW_WIPE=1 set for that run."


def require_wipe_permission(what, env=None, advice=BACKUP_ADVICE):
    """Stop (SystemExit) unless the caller set ALLOW_WIPE=1 for this run.

    Call it before any statement that deletes every row of a table, so the destructive scripts can't be
    run by accident, from shell history, or by a scheduler. `advice` follows the refusal; pass your own
    when backing up and running it again isn't a safe next step for that script.
    """
    env = os.environ if env is None else env
    if env.get("ALLOW_WIPE") != "1":
        raise SystemExit(f"Refusing to delete {what}: this permanently deletes every row it covers. {advice}")
