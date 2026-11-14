"""The worker's Sentry check (utils/sentry_poller.py over utils/sentry_github.py), against an in-memory Sentry and
GitHub: no network. Run from dashboard/backend: python -m unittest discover -s tests"""
import pathlib
import sys
from unittest import TestCase, main
from urllib.parse import parse_qs, urlparse

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from utils import sentry_github  # noqa: E402
from utils.sentry_poller import (  # noqa: E402
    DEFAULT_INTERVAL_S, LOOKBACK_MIN, MAX_BACKOFF_S, MAX_LOOKBACK_MIN, REPORT_AFTER_FAILURES, SentryPoller,
)

SENTRY = "https://sentry.io/api/0"
GITHUB = "https://api.github.com"
REPO = "ARCO-Lab/WELLWebsite"
SENTRY_TOKEN = "sntry-poller-token"
GITHUB_TOKEN = "github_pat_poller-token"
ENV = {"SENTRY_API_TOKEN": SENTRY_TOKEN, "GITHUB_ISSUES_TOKEN": GITHUB_TOKEN}


def sentry_issue(short_id="WELL-DASHBOARD-7", count="3", title="TypeError: x is undefined", **extra):
    return {
        "id": "123", "shortId": short_id, "title": title, "metadata": {"type": "TypeError"},
        "culprit": "GET /api/series", "permalink": "https://well-cs.sentry.io/issues/123/", "level": "error",
        "count": count, "userCount": 1, "firstSeen": "2026-11-14T10:00:00Z", "lastSeen": "2026-11-14T10:05:00Z",
        "project": {"slug": "well-dashboard"}, **extra,
    }


class Fake:
    """Sentry and GitHub in memory. `errors` is a list of HTTP statuses (with Retry-After seconds) the next requests
    fail with, before the fake answers normally again."""

    def __init__(self, sentry=(), gh_issues=(), comments=None, errors=()):
        self.sentry = list(sentry)
        self.gh_issues = [dict(i) for i in gh_issues]
        self.comments = {k: list(v) for k, v in (comments or {}).items()}
        self.errors = list(errors)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, headers, body))
        if self.errors:
            status, retry_after = self.errors.pop(0)
            raise sentry_github.HttpError(status, url, retry_after)
        parsed = urlparse(url)
        query, path = parse_qs(parsed.query), parsed.path
        if url.startswith(SENTRY):
            assert headers["Authorization"] == f"Bearer {SENTRY_TOKEN}"
            if path.endswith("/events/latest/"):
                return 200, {}, {"entries": []}
            return 200, {}, self.sentry
        assert url.startswith(f"{GITHUB}/repos/{REPO}/"), url
        assert headers["Authorization"] == f"Bearer {GITHUB_TOKEN}"
        if method == "GET" and path == f"/repos/{REPO}/issues":
            assert query["labels"] == ["sentry"] and query["state"] == ["all"], query
            return 200, {}, self.gh_issues if query["page"] == ["1"] else []
        if method == "GET" and path.endswith("/comments"):
            return 200, {}, self.comments.get(int(path.split("/")[-2]), []) if query["page"] == ["1"] else []
        if method == "POST" and path == f"/repos/{REPO}/labels":
            return 201, {}, body
        if method == "POST" and path == f"/repos/{REPO}/issues":
            issue = {"number": 100 + len(self.gh_issues), "state": "open", **body}
            self.gh_issues.append(issue)
            return 201, {}, issue
        if method == "POST" and path.endswith("/comments"):
            # The worker's token belongs to a maintainer, so GitHub marks its comments as a member's.
            comment = {"body": body["body"], "user": {"login": "maintainer"}, "author_association": "MEMBER"}
            self.comments.setdefault(int(path.split("/")[-2]), []).append(comment)
            return 201, {}, comment
        raise AssertionError(f"unexpected {method} {url}")

    def writes(self):
        return [(m, urlparse(u).path, b) for m, u, _, b in self.calls if m != "GET"]

    def sentry_queries(self):
        return [parse_qs(urlparse(u).query) for m, u, _, _ in self.calls
                if u.startswith(SENTRY) and u.split("?")[0].endswith("/issues/")]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def poller(fake, env=ENV, clock=None):
    lines, warnings, sleeps = [], [], []
    p = SentryPoller(env=env, http=fake, log=lines.append, warn=warnings.append, clock=clock or Clock(),
                     sleep=sleeps.append)
    return p, lines, warnings, sleeps


class SettingsTest(TestCase):
    def test_off_without_either_token_and_says_so_in_one_line(self):
        for env in ({}, {"SENTRY_API_TOKEN": SENTRY_TOKEN}, {"GITHUB_ISSUES_TOKEN": GITHUB_TOKEN},
                    {"SENTRY_API_TOKEN": " ", "GITHUB_ISSUES_TOKEN": GITHUB_TOKEN}):
            with self.subTest(env=sorted(env)):
                fake = Fake([sentry_issue()])
                p, lines, _, _ = poller(fake, env)
                self.assertFalse(p.enabled)
                line = p.describe()
                self.assertIn("off", line)
                self.assertEqual(len(line.splitlines()), 1)
                self.assertIsNone(p.poll())
                self.assertEqual(fake.calls, [])
                self.assertNotIn(SENTRY_TOKEN, line)

    def test_on_with_both_tokens_and_the_interval(self):
        p, _, _, _ = poller(Fake())
        self.assertTrue(p.enabled)
        self.assertEqual(p.interval_s, DEFAULT_INTERVAL_S)
        self.assertIn("every 60 s", p.describe())
        self.assertNotIn(GITHUB_TOKEN, p.describe())
        for value, expected in (("120", 120), ("5", 30), ("soon", DEFAULT_INTERVAL_S)):
            with self.subTest(value=value):
                p, _, _, _ = poller(Fake(), {**ENV, "SENTRY_SYNC_INTERVAL_S": value})
                self.assertEqual(p.interval_s, expected)

    def test_a_general_github_token_is_not_used(self):
        p, _, _, _ = poller(Fake(), {"SENTRY_API_TOKEN": SENTRY_TOKEN, "GITHUB_TOKEN": GITHUB_TOKEN})
        self.assertFalse(p.enabled)


class PollTest(TestCase):
    def test_asks_sentry_only_for_recent_issues_and_github_only_when_there_are_some(self):
        clock = Clock()
        fake = Fake([])
        p, lines, _, _ = poller(fake, clock=clock)
        self.assertTrue(p.poll())
        clock.now += 60
        self.assertTrue(p.poll())
        queries = fake.sentry_queries()
        # The first poll after start-up covers a day (anything older is the daily workflow's), then a few minutes
        self.assertEqual(queries[0]["query"], [f"is:unresolved lastSeen:-{MAX_LOOKBACK_MIN}m"])
        self.assertEqual(queries[1]["query"], [f"is:unresolved lastSeen:-{LOOKBACK_MIN}m"])
        self.assertEqual(queries[1]["statsPeriod"], ["14d"])   # counts over the same period as the daily run
        self.assertTrue(all(u.startswith(SENTRY) for _, u, _, _ in fake.calls))
        self.assertEqual(lines, [])   # nothing new: nothing logged either

    def test_a_new_issue_is_opened_once(self):
        clock = Clock()
        fake = Fake([sentry_issue()])
        p, lines, _, _ = poller(fake, clock=clock)
        self.assertTrue(p.poll())
        clock.now += 60
        self.assertTrue(p.poll())
        created = [b for m, path, b in fake.writes() if path == f"/repos/{REPO}/issues"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["title"], "[Sentry] WELL-DASHBOARD-7: TypeError")
        self.assertEqual(created[0]["labels"], ["sentry"])
        self.assertTrue(created[0]["body"].startswith("<!-- sentry:WELL-DASHBOARD-7 -->\n"))
        self.assertIn(sentry_github.UNTRUSTED_NOTE, created[0]["body"])
        self.assertIn("WELL-DASHBOARD-7: #100 is up to date", lines)

    def test_same_issue_as_the_daily_workflow_writes(self):
        fake = Fake([sentry_issue()])
        poller(fake)[0].poll()
        mine = [b for _, path, b in fake.writes() if path == f"/repos/{REPO}/issues"][0]
        daily = Fake([sentry_issue()])
        sentry_github.run(daily, {"SENTRY_API_TOKEN": SENTRY_TOKEN, "GITHUB_TOKEN": GITHUB_TOKEN,
                                  "GITHUB_REPOSITORY": REPO}, log=lambda line: None)
        theirs = [b for _, path, b in daily.writes() if path == f"/repos/{REPO}/issues"][0]
        self.assertEqual(mine, theirs)

    def test_no_duplicate_when_the_marker_exists_open_or_closed(self):
        for state in ("open", "closed"):
            with self.subTest(state=state):
                existing = {"number": 9, "state": state, "closed_at": "2026-11-14T12:00:00Z",
                            "body": "<!-- sentry:WELL-DASHBOARD-7 -->\n<!-- sentry-state count=3 last_seen=x -->"}
                fake = Fake([sentry_issue()], gh_issues=[existing])
                p, _, _, _ = poller(fake)
                self.assertTrue(p.poll())
                self.assertEqual(fake.writes(), [])

    def test_marker_added_by_the_daily_workflow_meanwhile_is_found_before_opening(self):
        fake = Fake([sentry_issue()])
        real_latest = sentry_github.latest_event

        def latest_event_while_the_workflow_opens_it(*args, **kwargs):
            # The daily workflow opens the issue between the poller's first listing and its create
            fake.gh_issues.append({"number": 42, "state": "open", "body": "<!-- sentry:WELL-DASHBOARD-7 -->"})
            return real_latest(*args, **kwargs)

        sentry_github.latest_event = latest_event_while_the_workflow_opens_it
        try:
            self.assertTrue(poller(fake)[0].poll())
        finally:
            sentry_github.latest_event = real_latest
        self.assertFalse(any(path == f"/repos/{REPO}/issues" for _, path, _ in fake.writes()))

    def test_count_jump_comment(self):
        clock = Clock()
        fake = Fake([sentry_issue(count="3")])
        p, _, _, _ = poller(fake, clock=clock)
        p.poll()
        fake.sentry = [sentry_issue(count="40")]
        clock.now += 60
        p.poll()
        [comment] = fake.comments[100]
        self.assertTrue(comment["body"].startswith("Event count jumped"))
        self.assertIn("40 events (last reported here: 3)", comment["body"])
        fake.sentry = [sentry_issue(count="45")]   # its own comment is the new baseline
        clock.now += 60
        p.poll()
        self.assertEqual(len(fake.comments[100]), 1)

    def test_closed_issue_seen_again_once_not_every_minute(self):
        clock = Clock()
        closed = {"number": 9, "state": "closed", "closed_at": "2026-11-14T09:00:00Z",
                  "body": "<!-- sentry:WELL-DASHBOARD-7 -->\n<!-- sentry-state count=3 last_seen=x -->"}
        fake = Fake([sentry_issue(count="4")], gh_issues=[closed])
        p, _, _, _ = poller(fake, clock=clock)
        p.poll()
        for minute in range(6, 10):   # it keeps happening, minute after minute
            fake.sentry = [sentry_issue(count=str(minute), lastSeen=f"2026-11-14T10:{minute:02d}:00Z")]
            clock.now += 60
            p.poll()
        self.assertEqual(len(fake.comments[9]), 1)
        self.assertTrue(fake.comments[9][0]["body"].startswith("Seen again"))
        fake.sentry = [sentry_issue(count="90", lastSeen="2026-11-15T10:00:00Z")]   # a day later
        clock.now += 60
        p.poll()
        self.assertEqual(len(fake.comments[9]), 2)
        self.assertFalse(any(m == "PATCH" for m, _, _ in fake.writes()))   # never reopened

    def test_test_events_are_skipped(self):
        fake = Fake([sentry_issue(title="Error: Sentry test from the worker")])
        p, lines, _, _ = poller(fake)
        self.assertTrue(p.poll())
        self.assertEqual(fake.writes(), [])
        self.assertFalse(any(u.startswith(GITHUB) for _, u, _, _ in fake.calls))
        self.assertIn("WELL-DASHBOARD-7: a test event, skipped", lines)


class FailureTest(TestCase):
    def test_429_is_retried_after_retry_after(self):
        fake = Fake([sentry_issue()], errors=[(429, 7), (429, None)])
        p, lines, _, sleeps = poller(fake)
        self.assertTrue(p.poll())
        self.assertEqual(sleeps, [7, 8])   # what Sentry asked for, then the second default delay
        self.assertEqual(len([1 for _, path, _ in fake.writes() if path == f"/repos/{REPO}/issues"]), 1)
        self.assertTrue(any("HTTP 429" in line and "trying again" in line for line in lines))

    def test_a_poll_that_keeps_failing_backs_off_and_never_raises(self):
        clock = Clock()
        fake = Fake([sentry_issue()], errors=[(503, None)] * 1000)
        p, lines, warnings, _ = poller(fake, clock=clock)
        results = []
        for _ in range(60):   # an hour of scheduled polls
            results.append(p.poll())
            clock.now += 60
        tried = [minute for minute, r in enumerate(results) if r is not None]
        self.assertTrue(all(results[minute] is False for minute in tried))
        # Waits longer each time, up to MAX_BACKOFF_S: polls at minutes 0, 1, 3, 7, 15, 30 and 45
        self.assertEqual(tried, [0, 1, 3, 7, 15, 30, 45])
        self.assertLessEqual(max(b - a for a, b in zip(tried, tried[1:])) * 60, MAX_BACKOFF_S)
        self.assertEqual(len(warnings), 1)                         # reported once, after REPORT_AFTER_FAILURES
        self.assertIn(f"{REPORT_AFTER_FAILURES} polls in a row failed", warnings[0])
        # Back to normal: the next poll covers the whole gap since the last success (none yet: a day)
        fake.errors = []
        clock.now = p.wait_until
        self.assertTrue(p.poll())
        self.assertTrue(any("working again" in line for line in lines))
        for line in lines + warnings:
            self.assertNotIn(SENTRY_TOKEN, line)
            self.assertNotIn(GITHUB_TOKEN, line)

    def test_lookback_covers_a_gap_after_failures(self):
        clock = Clock()
        fake = Fake([])
        p, _, _, _ = poller(fake, clock=clock)
        p.poll()
        fake.errors = [(500, None)] * 3   # the GET is tried three times, then the poll fails
        clock.now += 60
        self.assertFalse(p.poll())
        clock.now += 30 * 60
        self.assertTrue(p.poll())
        self.assertEqual(fake.sentry_queries()[-1]["query"], ["is:unresolved lastSeen:-36m"])

    def test_a_failed_create_is_not_retried_but_the_next_poll_finds_it(self):
        clock = Clock()
        fake = Fake([sentry_issue()])
        p, _, _, _ = poller(fake, clock=clock)
        real = fake.__call__

        def create_then_502(method, url, headers, body=None):
            result = real(method, url, headers, body)
            if method == "POST" and urlparse(url).path == f"/repos/{REPO}/issues":
                raise sentry_github.HttpError(502, url)   # GitHub opened it, but the answer was lost
            return result

        p.http = sentry_github.with_retries(create_then_502, sleep=lambda s: None, log=lambda line: None)
        self.assertFalse(p.poll())
        clock.now = p.wait_until
        p.http = sentry_github.with_retries(fake, sleep=lambda s: None, log=lambda line: None)
        self.assertTrue(p.poll())
        self.assertEqual(len([1 for _, path, _ in fake.writes() if path == f"/repos/{REPO}/issues"]), 1)

    def test_an_unexpected_error_is_logged_not_raised(self):
        p, lines, _, _ = poller(Fake([{"shortId": "WELL-DASHBOARD-7", "title": "x", "count": "many"}]))
        self.assertFalse(p.poll())
        self.assertTrue(any(line.startswith("[ERROR] Sentry issues to GitHub failed") for line in lines))


if __name__ == "__main__":
    main()
