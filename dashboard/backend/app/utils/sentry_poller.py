"""The worker's Sentry check: new Sentry errors become GitHub issues within about a minute.

Every SENTRY_SYNC_INTERVAL_S (default 60 s) scripts/scheduler_temp.py calls SentryPoller.poll, which runs the same
code as the daily workflow (utils/sentry_github.py) for the unresolved Sentry issues seen in the last few minutes:
it opens the missing GitHub issues and comments on count jumps and on closed issues seen again, with the same
markers, label, text and redaction. Before opening an issue it looks for its <!-- sentry:ID --> marker among the
open and closed issues labelled "sentry", so it and the daily workflow (kept as a backup) never open one twice.

Settings (dashboard/backend/app/.env), all optional; without both tokens the check is off and the worker says so
once at start-up:
  SENTRY_API_TOKEN        Sentry auth token, read-only: org:read, project:read, event:read
  GITHUB_ISSUES_TOKEN     fine-grained GitHub token for this repository only, Issues: read and write, nothing else
  SENTRY_ORG              Sentry organization (default well-cs); every project in it is checked
  GITHUB_ISSUES_REPO      owner/name (default ARCO-Lab/WELLWebsite)
  SENTRY_SYNC_INTERVAL_S  seconds between polls (default 60, at least 30)
  SENTRY_API_URL, SENTRY_JUMP_FACTOR, SENTRY_JUMP_MIN   as for the daily workflow

A poll asks Sentry for one page of issues (lastSeen in the last LOOKBACK_MIN minutes, more after a gap), and GitHub
only about those whose count or last-seen time changed since a poll handled them. A rate limit (429) or server
error is retried within the poll (sentry_github.with_retries); a poll that still fails is logged, and the next ones
wait longer and longer (up to MAX_BACKOFF_S), with a wider look-back so nothing seen meanwhile is missed. A poll
never raises, so a failure can't stop the worker. The tokens are only sent in request headers, never logged.
"""
import math
import os
import time

from utils import sentry_github

DEFAULT_INTERVAL_S = 60
MIN_INTERVAL_S = 30   # well within Sentry's and GitHub's rate limits
DEFAULT_REPO = "ARCO-Lab/WELLWebsite"
# Each poll covers the issues seen in the last LOOKBACK_MIN minutes: a margin for a poll that runs late, and for
# Sentry taking a moment to update an issue's last-seen time. After a gap (failed polls, a restart) it covers the
# whole gap, up to MAX_LOOKBACK_MIN; the first poll after the worker starts covers MAX_LOOKBACK_MIN, and anything
# older is left to the daily workflow.
LOOKBACK_MIN = 10
MAX_LOOKBACK_MIN = 24 * 60
# After failed polls in a row, the next one waits interval * 2^(failures - 1), at most this long.
MAX_BACKOFF_S = 15 * 60
# This many failed polls in a row are reported to Sentry, once (e.g. an expired token).
REPORT_AFTER_FAILURES = 5
ANNOTATIONS = (("::error::", "[ERROR] "), ("::warning::", "[WARN] "))


def interval_setting(value):
    """SENTRY_SYNC_INTERVAL_S as whole seconds, at least MIN_INTERVAL_S; the default when unset or not a number."""
    try:
        return max(MIN_INTERVAL_S, int(str(value).strip()))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_S


class SentryPoller:
    def __init__(self, env=None, http=None, log=print, warn=None, clock=time.monotonic, sleep=time.sleep):
        env = os.environ if env is None else env

        def setting(name):
            return (env.get(name) or "").strip()

        self.missing = [name for name in ("SENTRY_API_TOKEN", "GITHUB_ISSUES_TOKEN") if not setting(name)]
        self.enabled = not self.missing
        self.interval_s = interval_setting(setting("SENTRY_SYNC_INTERVAL_S") or DEFAULT_INTERVAL_S)
        # What sentry_github.run reads. The GitHub token has its own name here, so it can't be mistaken for (or
        # pick up) a GITHUB_TOKEN meant for something else.
        self.settings = {
            "SENTRY_API_TOKEN": setting("SENTRY_API_TOKEN"),
            "SENTRY_ORG": setting("SENTRY_ORG"),
            "SENTRY_API_URL": setting("SENTRY_API_URL"),
            "SENTRY_JUMP_FACTOR": setting("SENTRY_JUMP_FACTOR"),
            "SENTRY_JUMP_MIN": setting("SENTRY_JUMP_MIN"),
            "GITHUB_TOKEN": setting("GITHUB_ISSUES_TOKEN"),
            "GITHUB_REPOSITORY": setting("GITHUB_ISSUES_REPO") or DEFAULT_REPO,
        }
        self.log, self.warn, self.clock = log, warn, clock
        self.http = sentry_github.with_retries(http or sentry_github.http_request, sleep=sleep, log=self._log)
        self.last_success = None   # clock() when the last successful poll started
        self.failures = 0          # failed polls in a row
        self.wait_until = 0.0      # clock() before which polls are skipped, after failures
        # {short id: (count, last seen)} of each Sentry issue already handled: an issue still in the look-back window
        # but unchanged since is skipped, so it costs GitHub nothing (sentry_github.run)
        self.handled = {}

    def describe(self):
        """The start-up line: on, with how often, or off and why."""
        if not self.enabled:
            return (f"Sentry issues to GitHub: off ({' and '.join(self.missing)} not set); the daily workflow "
                    "still runs.")
        return (f"Sentry issues to GitHub: every {self.interval_s} s, into "
                f"{self.settings['GITHUB_REPOSITORY']} (logs/sentry_github.log).")

    def _log(self, line):
        # sentry_github writes GitHub Actions annotations; in the worker's log they read as the others do.
        for prefix, replacement in ANNOTATIONS:
            if line.startswith(prefix):
                line = replacement + line[len(prefix):]
        self.log(line)

    def lookback_minutes(self, now):
        if self.last_success is None:
            return MAX_LOOKBACK_MIN
        gap = math.ceil((now - self.last_success) / 60)
        return min(MAX_LOOKBACK_MIN, max(LOOKBACK_MIN, gap + LOOKBACK_MIN // 2))

    def poll(self):
        """One poll. Returns True when it worked, False when it failed, None when it was off or waiting after
        failures. Never raises."""
        if not self.enabled:
            return None
        now = self.clock()
        if now < self.wait_until:
            return None
        error, retry_after = None, None
        try:
            code = sentry_github.run(self.http, self.settings, seen_within_minutes=self.lookback_minutes(now),
                                     log=self._log, handled=self.handled)
            if code != 0:
                error = "Sentry could not be read, or a setting is wrong (see the line above)"
        except sentry_github.HttpError as err:
            error, retry_after = str(err), err.retry_after
        except Exception as err:   # a bug or an odd response must not stop the worker
            error = f"{type(err).__name__}: {err}"
        if error is None:
            if self.failures:
                self._log(f"Sentry issues to GitHub: working again after {self.failures} failed poll(s)")
            self.last_success, self.failures, self.wait_until = now, 0, 0.0
            return True
        self.failures += 1
        backoff = min(MAX_BACKOFF_S, self.interval_s * 2 ** (self.failures - 1))
        # Half an interval less, so the scheduled poll that falls due right at the end isn't skipped as early.
        # A server that asked for a longer pause (Retry-After) gets it.
        self.wait_until = now + max(backoff - self.interval_s / 2, retry_after or 0)
        self._log(f"[ERROR] Sentry issues to GitHub failed ({self.failures} in a row): {error}; next try in "
                  f"about {math.ceil(max(backoff, retry_after or 0))} s")
        if self.failures == REPORT_AFTER_FAILURES and self.warn:
            try:
                self.warn(f"Sentry issues to GitHub: {self.failures} polls in a row failed: {error}")
            except Exception as err:
                self._log(f"[ERROR] reporting the failed polls failed: {err}")
        return False
