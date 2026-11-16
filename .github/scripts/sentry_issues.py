#!/usr/bin/env python3
"""Opens a GitHub issue for each unresolved Sentry issue (.github/workflows/sentry-issues.yml, once a day).

The daily backup of the worker's minute-by-minute check: both run the same code, in
dashboard/backend/app/utils/sentry_github.py (what is opened, commented and left out is described there), so they
write the same issues, and each finds the other's by the <!-- sentry:ID --> marker instead of opening a second one.
This file only loads that module, by its path (the workflow checks out these two folders and nothing is installed),
and runs it with the workflow's settings.

Environment: SENTRY_API_TOKEN (read-only: org:read, project:read, event:read), SENTRY_ORG, GITHUB_TOKEN,
GITHUB_REPOSITORY (owner/name), and optionally SENTRY_STATS_PERIOD (default 14d), SENTRY_JUMP_FACTOR (2),
SENTRY_JUMP_MIN (20) and SENTRY_API_URL. With no SENTRY_API_TOKEN it prints a warning and exits 0.
    python3 .github/scripts/sentry_issues.py [--dry-run]
--dry-run reads Sentry and GitHub and prints what it would do, without writing to GitHub.
"""

import argparse
import importlib.util
import os
import pathlib
import sys

SHARED = pathlib.Path(__file__).resolve().parents[2] / "dashboard" / "backend" / "app" / "utils" / "sentry_github.py"
# Every file this script loads from outside .github/scripts. The workflow's sparse checkout must include each one
# (test_sentry_issues.py checks it does).
LOADED_FILES = (SHARED,)
_spec = importlib.util.spec_from_file_location("sentry_github", SHARED)
sentry_github = importlib.util.module_from_spec(_spec)
sys.modules["sentry_github"] = sentry_github
_spec.loader.exec_module(sentry_github)

# Re-exported for the maintainer's scripts and the tests, which import them from here.
from sentry_github import (  # noqa: E402
    MARKER, UNTRUSTED_NOTE, HttpError, http_request, run, safe_exception_type, scrub, with_retries,
)

__all__ = ["LOADED_FILES", "MARKER", "UNTRUSTED_NOTE", "HttpError", "http_request", "run", "safe_exception_type",
           "scrub", "with_retries", "main"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="read only; print what would be written to GitHub")
    args = parser.parse_args()
    try:
        return run(with_retries(http_request), os.environ, dry_run=args.dry_run)
    except HttpError as err:
        print(f"::error::{err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
