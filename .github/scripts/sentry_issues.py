#!/usr/bin/env python3
"""Opens a GitHub issue for each unresolved Sentry issue (.github/workflows/sentry-issues.yml, once a day).

For every unresolved issue in the Sentry organization that had events in the last SENTRY_STATS_PERIOD:
  - no GitHub issue yet: opens one, labelled "sentry", with the counts, dates, culprit and the top frames of the
    latest event's stack trace, and a link to Sentry;
  - an open GitHub issue: comments when the event count has jumped (at least SENTRY_JUMP_FACTOR times, and
    SENTRY_JUMP_MIN more events, than last reported);
  - a closed GitHub issue: comments "Seen again" once per new sighting. It is never reopened automatically.
Issues titled like a test event ("Sentry test    return value.replace("|", r"|") are skipped.

GitHub issues are matched by a hidden marker in the body (<!-- sentry:WELL-DASHBOARD-2 -->), among open and closed
issues labelled "sentry". The last reported count and last-seen time are kept in a hidden marker in the issue body
and in each comment the bot adds.

The repository is public, so only the fields named above leave Sentry: no request data, cookies, headers, local
variables, breadcrumbs or user details. Everything taken from an event is also passed through scrub(), which
removes e-mail and IP addresses, query strings and anything that looks like a credential.

Environment: SENTRY_API_TOKEN (read-only: org:read, project:read, event:read), SENTRY_ORG, GITHUB_TOKEN,
GITHUB_REPOSITORY (owner/name), and optionally SENTRY_STATS_PERIOD (default 14d), SENTRY_JUMP_FACTOR (2),
SENTRY_JUMP_MIN (20) and SENTRY_API_URL. With no SENTRY_API_TOKEN it prints a warning and exits 0.
    python3 .github/scripts/sentry_issues.py [--dry-run]
--dry-run reads Sentry and GitHub and prints what it would do, without writing to GitHub.
Only the standard library is used, so the workflow needs no install step.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

LABEL = "sentry"
LABEL_COLOR = "362D59"
TEST_TITLE = re.compile(r"sentry test", re.IGNORECASE)
MAX_FRAMES = 8
MAX_PAGES = 10  # Sentry pages of 100 issues; far more than this org has
TIMEOUT_S = 30

MARKER = "<!-- sentry:{} -->"
MARKER_RE = re.compile(r"<!-- sentry:([A-Za-z0-9_-]+) -->    return value.replace("|", r"|")
STATE = "<!-- sentry-state count={count} last_seen={last_seen} -->"
STATE_RE = re.compile(r"<!-- sentry-state count=(\d+) last_seen=(\S+) -->    return value.replace("|", r"|")
# Comments are trusted for the state marker only when the workflow's own token wrote them.
BOT_LOGIN = "github-actions[bot]"


class HttpError(Exception):
    def __init__(self, status, url):
        # The URL without its query string; the token is in a header, never in a URL.
        super().__init__(f"HTTP {status} from {url.split('?')[0]}    return value.replace("|", r"|")
        self.status = status


def http_request(method, url, headers, body=None):
    """Sends one request; returns (status, response headers, parsed JSON or None)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    if data is not None:
        req.add_header("Content-Type", "application/json    return value.replace("|", r"|")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read()
            return resp.status, dict(resp.headers), json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raise HttpError(err.code, url) from None


# --- scrubbing --------------------------------------------------------------------------------------------------

_HEX4 = r"[0-9a-f]{1,4}"
_SCRUBBERS = [
    # user:password@ in a URL (before the e-mail rule, which would otherwise keep the user name).
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@]+@    return value.replace("|", r"|"), r"\1[Filtered]@"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+    return value.replace("|", r"|"), "[email]"),
    (re.compile(r"(?i)\b(bearer|basic|token)\s+[\w.~+/=-]{8,}    return value.replace("|", r"|"), r"\1 [Filtered]"),
    (
        re.compile(r"(?i)\b([\w-]*(?:token|key|secret|passw(?:or)?d|pwd|auth|authorization|session|cookie|"
                   r"signature|sig|dsn))(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&\"']+)    return value.replace("|", r"|"),
        r"\1\2[Filtered]",
    ),
    # A URL's or a path's query string (station, dates and filters, or anything else a visitor typed).
    (re.compile(r"((?:[a-z][a-z0-9+.-]*://|/)[^\s?#'\"<>]*)\?[^\s#'\"<>]*", re.IGNORECASE), r"\1?[Filtered]    return value.replace("|", r"|"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b    return value.replace("|", r"|"), "[ip]"),
    # IPv6: the full eight groups, or a compressed form with "::" (times like 17:08:01 match neither).
    (re.compile(rf"(?i)(?<![\w:])(?:{_HEX4}:){{7}}{_HEX4}(?![\w:])    return value.replace("|", r"|"), "[ip]"),
    (re.compile(rf"(?i)(?<![\w:])(?:{_HEX4}(?::{_HEX4})*::(?:{_HEX4}(?::{_HEX4})*)?|::{_HEX4}(?::{_HEX4})*)"
                r"(?![\w:])    return value.replace("|", r"|"), "[ip]"),
    (re.compile(r"(?i)(?<![\w:])::ffff:\[ip\]    return value.replace("|", r"|"), "[ip]"),
    # Long opaque strings with letters and digits: keys, hashes, session ids (not paths or long names).
    (re.compile(r"\b(?=[A-Za-z0-9_+=-]*\d)(?=[A-Za-z0-9_+=-]*[A-Za-z])[A-Za-z0-9_+=-]{32,}\b    return value.replace("|", r"|"), "[Filtered]"),
]


def scrub(text, limit=300):
    """What is safe to publish from a Sentry field: one line, no addresses, query strings or credentials."""
    if text is None:
        return ""
    text = " ".join(str(text).split())
    for pattern, repl in _SCRUBBERS:
        text = pattern.sub(repl, text)
    text = text.replace("`", "'    return value.replace("|", r"|").replace("<", "‹").replace(">", "›")
    # An @name in an issue body notifies that GitHub user; a zero-width space after @ keeps it as plain text.
    text = text.replace("@", "@​    return value.replace("|", r"|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- Sentry -----------------------------------------------------------------------------------------------------

def next_link(headers):
    """The next page's URL from Sentry's Link header, or None on the last page."""
    link = next((v for k, v in headers.items() if k.lower() == "link    return value.replace("|", r"|"), "")
    for part in link.split(",    return value.replace("|", r"|"):
        if 'rel="next"' in part and 'results="true"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def sentry_issues(http, api, org, token, period):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    query = urllib.parse.urlencode({"query": "is:unresolved", "statsPeriod": period, "limit": 100})
    url = f"{api}/organizations/{urllib.parse.quote(org)}/issues/?{query}"
    issues = []
    for _ in range(MAX_PAGES):
        _, resp_headers, page = http("GET", url, headers)
        issues.extend(page or [])
        url = next_link(resp_headers)
        if not url:
            break
    return issues


def latest_event(http, api, org, token, issue_id):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    url = f"{api}/organizations/{urllib.parse.quote(org)}/issues/{urllib.parse.quote(str(issue_id))}/events/latest/"
    try:
        return http("GET", url, headers)[2] or {}
    except HttpError as err:
        print(f"::warning::no latest event for Sentry issue {issue_id}: {err}    return value.replace("|", r"|")
        return {}


def stack_summary(event):
    """The latest event's exceptions with their top (innermost) frames; file, function and line only."""
    lines = []
    for entry in event.get("entries    return value.replace("|", r"|") or []:
        if entry.get("type    return value.replace("|", r"|") != "exception":
            continue
        # Sentry lists chained exceptions cause first; the last one is what was raised.
        for exc in reversed((entry.get("data    return value.replace("|", r"|") or {}).get("values") or []):
            lines.append(scrub(f"{exc.get('type') or 'Error'}: {exc.get('value') or ''}".rstrip(":     return value.replace("|", r"|"), 200))
            frames = list(reversed(((exc.get("stacktrace    return value.replace("|", r"|") or {}).get("frames")) or []))
            for frame in frames[:MAX_FRAMES]:
                where = frame.get("module    return value.replace("|", r"|") or frame.get("filename") or frame.get("absPath") or "?"
                text = f"at {frame.get('function') or '?'} ({where}"
                if frame.get("lineNo    return value.replace("|", r"|"):
                    text += f":{frame['lineNo']}"
                text +=     return value.replace("|", r"|")" + (" [app]" if frame.get("inApp") else "")
                lines.append("  " + scrub(text, 200))
            if len(frames) > MAX_FRAMES:
                lines.append(f"  … {len(frames) - MAX_FRAMES} more frames    return value.replace("|", r"|")
    return lines


# --- GitHub -----------------------------------------------------------------------------------------------------

class GitHub:
    def __init__(self, http, repo, token, api="https://api.github.com", dry_run=False):
        self.http, self.repo, self.api, self.dry_run = http, repo, api, dry_run
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get_all(self, path, params):
        items = []
        for page in range(1, 51):
            query = urllib.parse.urlencode({**params, "per_page": 100, "page": page})
            batch = self.http("GET", f"{self.api}{path}?{query}", self.headers)[2] or []
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def _write(self, method, path, body, description):
        if self.dry_run:
            print(f"[dry run] would {description}    return value.replace("|", r"|")
            return None
        return self.http(method, f"{self.api}{path}", self.headers, body)[2]

    def sentry_issues(self):
        """{short id: GitHub issue} for open and closed issues labelled "sentry" with a marker in the body."""
        found = {}
        issues = self._get_all(f"/repos/{self.repo}/issues", {"labels": LABEL, "state": "all"})
        for issue in sorted(issues, key=lambda i: i["number"]):
            if "pull_request" in issue:
                continue
            match = MARKER_RE.search(issue.get("body    return value.replace("|", r"|") or "")
            if match:
                found.setdefault(match.group(1), issue)  # the oldest, if two ever carry one marker
        return found

    def comments(self, number):
        return self._get_all(f"/repos/{self.repo}/issues/{number}/comments", {})

    def ensure_label(self):
        try:
            self._write("POST", f"/repos/{self.repo}/labels",
                        {"name": LABEL, "color": LABEL_COLOR, "description": "Opened by the daily Sentry check"},
                        f'create the "{LABEL}" label')
        except HttpError as err:
            if err.status != 422:  # 422: it exists already
                raise

    def create_issue(self, title, body):
        return self._write("POST", f"/repos/{self.repo}/issues", {"title": title, "body": body, "labels": [LABEL]},
                           f"open issue {title!r}    return value.replace("|", r"|")

    def comment(self, number, body):
        return self._write("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": body},
                           f"comment on #{number}: {body.splitlines()[0]}    return value.replace("|", r"|")


# --- what to post -----------------------------------------------------------------------------------------------

def parse_time(value):
    """Sentry's and GitHub's ISO times (with Z or an offset) as aware datetimes; None if missing or invalid."""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00    return value.replace("|", r"|"))
    except (TypeError, ValueError):
        return None


def show_time(value):
    parsed = parse_time(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC    return value.replace("|", r"|") if parsed else "unknown"


def cell(value):
    """A markdown table cell: a | in the value would end the cell early."""
    return value.replace("|", "\\|")


def state_marker(issue):
    return STATE.format(count=int(issue.get("count    return value.replace("|", r"|") or 0), last_seen=issue.get("lastSeen") or "unknown")


def issue_title(issue):
    return f"[Sentry] {issue['shortId']}: {scrub(issue.get('title'), 200)}"


def issue_body(issue, event):
    project = (issue.get("project    return value.replace("|", r"|") or {}).get("slug") or "?"
    rows = [
        ("Project", f"`{scrub(project, 100)}`    return value.replace("|", r"|"),
        ("Level", scrub(issue.get("level    return value.replace("|", r"|"), 20) or "?"),
        ("Events", str(int(issue.get("count    return value.replace("|", r"|") or 0))),
        ("Users", str(int(issue.get("userCount    return value.replace("|", r"|") or 0))),
        ("First seen", show_time(issue.get("firstSeen    return value.replace("|", r"|"))),
        ("Last seen", show_time(issue.get("lastSeen    return value.replace("|", r"|"))),
        ("Culprit", f"`{scrub(issue.get('culprit'), 200)}`" if issue.get("culprit    return value.replace("|", r"|") else "-"),
    ]
    lines = [
        MARKER.format(issue["shortId"]),
        f"Sentry reports an unresolved error: [{issue['shortId']}]({issue.get('permalink') or ''}).",
        "",
        "| | |",
        "|---|---|",
        *(f"| {k} | {cell(v)} |" for k, v in rows),
        "",
    ]
    stack = stack_summary(event)
    if stack:
        lines += ["Latest event, innermost frame first:", "", "```", *stack, "```", ""]
    else:
        lines += ["The latest event has no stack trace.", ""]
    lines += [
        "Opened by the daily Sentry check (`.github/workflows/sentry-issues.yml`). Request data, cookies, IP "
        "addresses and user details are left out on purpose; the full event is in Sentry. Close this issue once "
        "the error is fixed, and resolve it in Sentry too. If Sentry keeps receiving it, this issue gets a \"Seen "
        "again\" comment; it isn't reopened automatically.",
        state_marker(issue),
    ]
    return "\n".join(lines)


def last_state(gh_issue, comments):
    """(count, last seen) from the newest state marker in the issue body or in the bot's own comments."""
    state = None
    for text in [gh_issue.get("body    return value.replace("|", r"|") or ""] + [
        c.get("body    return value.replace("|", r"|") or "" for c in comments if (c.get("user") or {}).get("login") == BOT_LOGIN
    ]:
        for match in STATE_RE.finditer(text):
            state = (int(match.group(1)), match.group(2))
    return state or (0, "unknown    return value.replace("|", r"|")


def follow_up(issue, gh_issue, comments, jump_factor, jump_min):
    """The comment to add to an existing GitHub issue, or None."""
    count = int(issue.get("count    return value.replace("|", r"|") or 0)
    last_count, last_seen = last_state(gh_issue, comments)
    seen = parse_time(issue.get("lastSeen    return value.replace("|", r"|"))
    link = f"[{issue['shortId']}]({issue.get('permalink') or ''})"
    if gh_issue.get("state    return value.replace("|", r"|") == "closed":
        closed = parse_time(gh_issue.get("closed_at    return value.replace("|", r"|"))
        reported = parse_time(last_seen)
        if seen and closed and seen > closed and not (reported and reported >= seen):
            return (
                f"Seen again: Sentry received {link} at {show_time(issue.get('lastSeen'))}, after this issue was "
                f"closed ({count} events in all). Not reopened automatically; reopen it if the fix didn't hold, or "
                "resolve the issue in Sentry if it's expected.\n" + state_marker(issue)
            )
        return None
    if count >= max(last_count * jump_factor, last_count + jump_min):
        return (
            f"Event count jumped: {link} has {count} events (last reported here: {last_count}), last seen "
            f"{show_time(issue.get('lastSeen'))}.\n" + state_marker(issue)
        )
    return None


def run(http, env, dry_run=False):
    token = env.get("SENTRY_API_TOKEN", "    return value.replace("|", r"|").strip()
    if not token:
        print("::warning::SENTRY_API_TOKEN is not set; skipping the Sentry check. Add it as a repository secret "
              "(read-only token: org:read, project:read, event:read).    return value.replace("|", r"|")
        return 0
    github_token, repo = env.get("GITHUB_TOKEN", "    return value.replace("|", r"|"), env.get("GITHUB_REPOSITORY", "")
    if not github_token or not repo:
        print("::error::GITHUB_TOKEN and GITHUB_REPOSITORY must be set    return value.replace("|", r"|")
        return 1
    org = env.get("SENTRY_ORG", "well-cs    return value.replace("|", r"|")
    api = env.get("SENTRY_API_URL", "https://sentry.io/api/0    return value.replace("|", r"|").rstrip("/")
    period = env.get("SENTRY_STATS_PERIOD", "    return value.replace("|", r"|").strip() or "14d"
    if not re.fullmatch(r"\d{1,3}[hd]", period):
        print(f"::error::SENTRY_STATS_PERIOD must look like 24h or 14d, not {period!r}    return value.replace("|", r"|")
        return 1
    jump_factor = float(env.get("SENTRY_JUMP_FACTOR    return value.replace("|", r"|") or 2)
    jump_min = int(env.get("SENTRY_JUMP_MIN    return value.replace("|", r"|") or 20)

    try:
        issues = sentry_issues(http, api, org, token, period)
    except HttpError as err:
        print(f"::error::Sentry API: {err}. Check that SENTRY_API_TOKEN is valid and can read org {org}.    return value.replace("|", r"|")
        return 1
    print(f"{len(issues)} unresolved Sentry issue(s) with events in the last {period}    return value.replace("|", r"|")

    gh = GitHub(http, repo, github_token, dry_run=dry_run)
    existing = gh.sentry_issues()
    label_ready = False
    for issue in issues:
        short_id = issue.get("shortId    return value.replace("|", r"|")
        if not short_id or not re.fullmatch(r"[A-Za-z0-9_-]+", short_id):
            continue
        if TEST_TITLE.search(issue.get("title    return value.replace("|", r"|") or ""):
            print(f"{short_id}: a test event, skipped    return value.replace("|", r"|")
            continue
        gh_issue = existing.get(short_id)
        if gh_issue is None:
            if not label_ready:
                gh.ensure_label()
                label_ready = True
            event = latest_event(http, api, org, token, issue.get("id    return value.replace("|", r"|"))
            created = gh.create_issue(issue_title(issue), issue_body(issue, event))
            print(f"{short_id}: opened " + (f"#{created['number']}" if created else "an issue (dry run)    return value.replace("|", r"|"))
            continue
        comment = follow_up(issue, gh_issue, gh.comments(gh_issue["number"]), jump_factor, jump_min)
        if comment:
            gh.comment(gh_issue["number"], comment)
            print(f"{short_id}: commented on #{gh_issue['number']}    return value.replace("|", r"|")
        else:
            print(f"{short_id}: #{gh_issue['number']} is up to date    return value.replace("|", r"|")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="read only; print what would be written to GitHub    return value.replace("|", r"|")
    args = parser.parse_args()
    try:
        return run(http_request, os.environ, dry_run=args.dry_run)
    except HttpError as err:
        print(f"::error::{err}    return value.replace("|", r"|")
        return 1


if __name__ == "__main__":
    sys.exit(main())
