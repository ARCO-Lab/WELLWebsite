"""The worker's Sentry check (utils/sentry_poller.py over utils/sentry_github.py), against an in-memory Sentry and
GitHub: no network. Run from dashboard/backend: python -m unittest discover -s tests"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone
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

    def __init__(self, sentry=(), gh_issues=(), comments=None, errors=(), groups=None, resolve_status=None):
        self.sentry = list(sentry)
        self.gh_issues = [dict(i) for i in gh_issues]
        self.comments = {k: list(v) for k, v in (comments or {}).items()}
        self.errors = list(errors)
        # Sentry issues by short id, as the shortids lookup returns them; resolve_status: what a resolve fails with
        self.groups = {k: dict(v) for k, v in (groups or {}).items()}
        self.resolve_status = resolve_status
        # HTTP statuses the next shortids lookups, and the next closed-issues listings, fail with (one per request)
        self.lookup_errors, self.closed_errors = [], []
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
            if path.startswith("/api/0/organizations/well-cs/shortids/"):
                if self.lookup_errors:
                    raise sentry_github.HttpError(self.lookup_errors.pop(0), url)
                group = self.groups.get(path.split("/")[-2])
                if group is None:
                    raise sentry_github.HttpError(404, url)
                return 200, {}, {"shortId": path.split("/")[-2], "groupId": group["id"], "group": group}
            if method == "PUT":
                assert body == {"status": "resolved"}, body
                if self.resolve_status:
                    raise sentry_github.HttpError(self.resolve_status, url)
                group_id = path.split("/")[-2]
                next(g for g in self.groups.values() if g["id"] == group_id)["status"] = "resolved"
                return 200, {}, {"status": "resolved"}
            assert method == "GET", (method, url)
            return 200, {}, self.sentry
        assert url.startswith(f"{GITHUB}/repos/{REPO}/"), url
        assert headers["Authorization"] == f"Bearer {GITHUB_TOKEN}"
        if method == "GET" and path == f"/repos/{REPO}/issues" and query["state"] == ["closed"]:
            # GitHub's `since` is on the last update, which closing (or a later comment) moves
            assert query["labels"] == ["sentry"], query
            if self.closed_errors:
                raise sentry_github.HttpError(self.closed_errors.pop(0), url)
            since = datetime.fromisoformat(query["since"][0].replace("Z", "+00:00"))
            closed = [i for i in self.gh_issues if i["state"] == "closed"
                      and datetime.fromisoformat(i.get("updated_at", i["closed_at"]).replace("Z", "+00:00")) >= since]
            return 200, {}, closed if query["page"] == ["1"] else []
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

    def github_calls(self, since=0):
        """GitHub requests from the since-th call on, without the closed-issues listing every poll makes."""
        return [(m, urlparse(u).path) for m, u, _, _ in self.calls[since:]
                if u.startswith(GITHUB) and parse_qs(urlparse(u).query).get("state") != ["closed"]]

    def resolves(self):
        return [urlparse(u).path for m, u, _, _ in self.calls if m == "PUT"]

    def lookups(self):
        return [urlparse(u).path.split("/")[-2] for _, u, _, _ in self.calls if "/shortids/" in u]

    def sentry_queries(self):
        return [parse_qs(urlparse(u).query) for m, u, _, _ in self.calls
                if u.startswith(SENTRY) and u.split("?")[0].endswith("/issues/")]


class Clock:
    """The poller's monotonic clock, and utc() the wall clock that moves with it."""
    START = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def utc(self):
        return self.START + timedelta(seconds=self.now - 1000.0)


def poller(fake, env=ENV, clock=None):
    lines, warnings, sleeps = [], [], []
    clock = clock or Clock()
    p = SentryPoller(env=env, http=fake, log=lines.append, warn=warnings.append, clock=clock, sleep=sleeps.append,
                     utc_now=clock.utc)
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
        self.assertEqual(fake.github_calls(), [])   # only the closed-issues listing (ResolveTest)
        self.assertEqual(lines, [])   # nothing new: nothing logged either

    def test_a_new_issue_is_opened_once(self):
        clock = Clock()
        fake = Fake([sentry_issue()])
        p, lines, _, _ = poller(fake, clock=clock)
        self.assertTrue(p.poll())
        clock.now += 60
        self.assertTrue(p.poll())
        self.assertTrue(poller(fake)[0].poll())   # a restarted worker, which remembers nothing: found by its marker
        created = [b for m, path, b in fake.writes() if path == f"/repos/{REPO}/issues"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["title"], "[Sentry] WELL-DASHBOARD-7: TypeError")
        self.assertEqual(created[0]["labels"], ["sentry"])
        self.assertTrue(created[0]["body"].startswith("<!-- sentry:WELL-DASHBOARD-7 -->\n"))
        self.assertIn(sentry_github.UNTRUSTED_NOTE, created[0]["body"])
        self.assertIn("WELL-DASHBOARD-7: opened #100", lines)
        self.assertFalse(any("up to date" in line for line in lines))   # logged by the daily run only

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
        self.assertEqual(fake.github_calls(), [])
        self.assertIn("WELL-DASHBOARD-7: a test event, skipped", lines)


class HandledTest(TestCase):
    """The poller remembers each issue's (count, last seen) it has handled, and skips it until either changes."""

    def test_an_unchanged_issue_costs_one_request_to_each_and_no_log_line(self):
        clock = Clock()
        fake = Fake([sentry_issue()])
        p, lines, _, _ = poller(fake, clock=clock)
        p.poll()
        before, logged = len(fake.calls), len(lines)
        for _ in range(5):
            clock.now += 60
            self.assertTrue(p.poll())
        # One Sentry listing and one GitHub listing of the issues closed lately per poll
        self.assertEqual(len(fake.calls) - before, 10)
        self.assertEqual(sum(u.startswith(SENTRY) for _, u, _, _ in fake.calls[before:]), 5)
        self.assertEqual(fake.github_calls(before), [])
        self.assertEqual(lines[logged:], [])

    def test_a_new_event_is_looked_at_again(self):
        for change in ({"lastSeen": "2026-11-14T10:06:00Z"}, {"count": "4"}):
            with self.subTest(change=change):
                clock = Clock()
                fake = Fake([sentry_issue()])
                p, lines, _, _ = poller(fake, clock=clock)
                p.poll()
                before, logged = len(fake.calls), len(lines)
                fake.sentry = [sentry_issue(**change)]
                clock.now += 60
                self.assertTrue(p.poll())
                self.assertIn(("GET", f"/repos/{REPO}/issues/100/comments"), fake.github_calls(before))
                self.assertEqual(fake.writes()[-1][1], f"/repos/{REPO}/issues")   # no new comment: not a jump
                self.assertFalse(any("up to date" in line for line in lines[logged:]))
                clock.now += 60
                calls = len(fake.calls)
                p.poll()   # and then remembered again
                self.assertEqual(fake.github_calls(calls), [])

    def test_a_failed_poll_forgets_nothing_it_did_not_finish(self):
        clock = Clock()
        fake = Fake([sentry_issue("WELL-DASHBOARD-7"), sentry_issue("WELL-DASHBOARD-8")])
        p, _, _, _ = poller(fake, clock=clock)
        real = fake.__call__
        opened = []

        def second_create_fails(method, url, headers, body=None):
            if method == "POST" and urlparse(url).path == f"/repos/{REPO}/issues":
                opened.append(body["title"])
                if len(opened) == 2:
                    raise sentry_github.HttpError(422, url)
            return real(method, url, headers, body)

        p.http = second_create_fails
        self.assertFalse(p.poll())
        self.assertEqual(list(p.handled), ["WELL-DASHBOARD-7"])
        p.http = fake
        clock.now = p.wait_until
        self.assertTrue(p.poll())
        self.assertEqual(sorted(p.handled), ["WELL-DASHBOARD-7", "WELL-DASHBOARD-8"])
        titles = [b["title"] for _, path, b in fake.writes() if path == f"/repos/{REPO}/issues"]
        self.assertEqual(sorted(titles), [f"[Sentry] WELL-DASHBOARD-{n}: TypeError" for n in (7, 8)])

    def test_the_memory_is_bounded(self):
        handled = {f"OLD-{i}": ("1", "x") for i in range(sentry_github.MAX_HANDLED)}
        sentry_github.remember(handled, sentry_issue())
        self.assertEqual(handled, {"WELL-DASHBOARD-7": ("3", "2026-11-14T10:05:00Z")})

    def test_the_daily_run_remembers_nothing_and_still_says_up_to_date(self):
        env = {"SENTRY_API_TOKEN": SENTRY_TOKEN, "GITHUB_TOKEN": GITHUB_TOKEN, "GITHUB_REPOSITORY": REPO}
        fake = Fake([sentry_issue()])
        sentry_github.run(fake, env, log=lambda line: None)
        lines = []
        sentry_github.run(fake, env, log=lines.append)
        self.assertIn("WELL-DASHBOARD-7: #100 is up to date", lines)


def closed_issue(number=9, short_id="WELL-BACKEND-2", closed_at="2026-11-14T12:00:30Z", reason="completed",
                 **extra):
    """A GitHub issue the check opened (its token belongs to a maintainer), closed with `reason`."""
    return {"number": number, "state": "closed", "state_reason": reason, "closed_at": closed_at,
            "updated_at": closed_at, "title": f"[Sentry] {short_id}: TypeError", "author_association": "MEMBER",
            "user": {"login": "maintainer"},
            "body": f"<!-- sentry:{short_id} -->\n<!-- sentry-state count=3 last_seen=x -->", **extra}


def group(group_id="555", status="unresolved", last_seen="2026-11-14T11:00:00Z"):
    return {"id": group_id, "status": status, "lastSeen": last_seen}


class ResolveTest(TestCase):
    """A GitHub issue closed as completed resolves its Sentry issue on the next poll (the worker only)."""

    def polled(self, fake, minutes=1):
        """A poller started at 12:00 UTC, polled then and once a minute for `minutes` more."""
        clock = Clock()
        p, lines, warnings, _ = poller(fake, clock=clock)
        results = [p.poll()]
        for _ in range(minutes):
            clock.now += 60
            results.append(p.poll())
        self.assertTrue(all(results), lines)
        return p, lines, warnings

    def test_closed_as_completed_resolves_the_sentry_issue_once(self):
        fake = Fake(gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()})
        _, lines, _ = self.polled(fake, minutes=3)
        self.assertEqual(fake.resolves(), ["/api/0/organizations/well-cs/issues/555/"])
        self.assertEqual(fake.groups["WELL-BACKEND-2"]["status"], "resolved")
        self.assertEqual(fake.lookups(), ["WELL-BACKEND-2"])   # looked up once, not every poll
        self.assertIn("WELL-BACKEND-2: resolved in Sentry (#9 closed as completed)", lines)
        self.assertEqual(fake.github_calls(), [])   # nothing else asked of GitHub, nothing written there

    def test_a_restarted_worker_finds_it_resolved_and_says_nothing(self):
        fake = Fake(gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()})
        self.polled(fake)
        _, lines, _ = self.polled(fake)   # remembers nothing, so looks it up again
        self.assertEqual(len(fake.resolves()), 1)
        self.assertEqual(lines, [])

    def test_the_closed_listing_covers_the_look_back(self):
        fake = Fake()
        self.polled(fake)
        since = [parse_qs(urlparse(u).query)["since"] for _, u, _, _ in fake.calls
                 if parse_qs(urlparse(u).query).get("state") == ["closed"]]
        # A day back after start-up, then LOOKBACK_MIN minutes back from the next poll (at 12:01)
        self.assertEqual(since, [["2026-11-13T12:00:00Z"], ["2026-11-14T11:51:00Z"]])

    def test_not_planned_or_duplicate_leaves_sentry_alone(self):
        for reason in ("not_planned", "duplicate", None):
            with self.subTest(reason=reason):
                fake = Fake(gh_issues=[closed_issue(reason=reason)], groups={"WELL-BACKEND-2": group()})
                self.polled(fake)
                self.assertEqual(fake.lookups(), [])
                self.assertEqual(fake.resolves(), [])

    def test_an_issue_a_visitor_opened_and_closed_resolves_nothing(self):
        visitor = closed_issue(author_association="NONE", user={"login": "visitor"})
        fake = Fake(gh_issues=[visitor], groups={"WELL-BACKEND-2": group()})
        self.polled(fake)
        self.assertEqual(fake.lookups(), [])

    def test_linked_by_the_title_when_there_is_no_marker(self):
        cases = (("WELL-BACKEND-2: export fails", ["WELL-BACKEND-2"]),
                 ("[Sentry] WELL-BACKEND-2 slow export", ["WELL-BACKEND-2"]),
                 ("Export fails, maybe WELL-BACKEND-2", []),   # a mention, not a link
                 ("Export fails", []))
        for title, expected in cases:
            with self.subTest(title=title):
                fake = Fake(gh_issues=[closed_issue(title=title, body="Seen on the export page")],
                            groups={"WELL-BACKEND-2": group()})
                self.polled(fake)
                self.assertEqual(fake.lookups(), expected)
                self.assertEqual(len(fake.resolves()), len(expected))

    def test_already_resolved_is_not_resolved_again(self):
        fake = Fake(gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group(status="resolved")})
        _, lines, _ = self.polled(fake)
        self.assertEqual(fake.resolves(), [])
        self.assertEqual(lines, [])

    def test_closed_long_ago_and_commented_on_since_is_left_alone(self):
        # e.g. a "Seen again" comment moves updated_at; resolving then would hide the regression
        old = closed_issue(closed_at="2026-11-01T09:00:00Z", updated_at="2026-11-14T12:00:10Z")
        fake = Fake(gh_issues=[old], groups={"WELL-BACKEND-2": group()})
        self.polled(fake)
        self.assertEqual(fake.lookups(), [])

    def test_a_regression_after_closing_is_not_resolved_and_still_gets_seen_again(self):
        # Sentry received the error again after the GitHub issue was closed (and so marked it unresolved again)
        seen = "2026-11-14T12:00:45Z"
        fake = Fake([sentry_issue("WELL-BACKEND-2", count="9", lastSeen=seen)], gh_issues=[closed_issue()],
                    groups={"WELL-BACKEND-2": group(last_seen=seen)})
        _, lines, _ = self.polled(fake)
        self.assertEqual(fake.resolves(), [])
        self.assertIn("WELL-BACKEND-2: seen again after #9 was closed, so left unresolved in Sentry", lines)
        [comment] = fake.comments[9]
        self.assertTrue(comment["body"].startswith("Seen again"))
        self.assertFalse(any(m == "PATCH" for m, _, _ in fake.writes()))   # still never reopened

    def test_unknown_short_id_is_a_warning(self):
        fake = Fake(gh_issues=[closed_issue()])
        _, lines, _ = self.polled(fake, minutes=2)
        self.assertEqual(lines, ["[WARN] WELL-BACKEND-2 (#9, closed): no such Sentry issue in well-cs"])

    def test_a_token_without_event_write_warns_once_and_the_rest_still_works(self):
        fake = Fake([sentry_issue()], gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()},
                    resolve_status=403)
        clock = Clock()
        p, lines, warnings, _ = poller(fake, clock=clock)
        self.assertTrue(p.poll())
        fake.gh_issues.append(closed_issue(number=10, short_id="WELL-BACKEND-3", closed_at="2026-11-14T12:01:30Z"))
        fake.groups["WELL-BACKEND-3"] = group("556")
        for _ in range(3):
            clock.now += 60
            self.assertTrue(p.poll())
        warned = [line for line in lines if line.startswith("[WARN]")]
        self.assertEqual(len(warned), 1)
        self.assertIn("HTTP 403", warned[0])
        self.assertIn("event:write", warned[0])
        self.assertEqual(fake.lookups(), ["WELL-BACKEND-2"])   # not tried again
        self.assertEqual(warnings, [])   # not a failed poll, so nothing for Sentry
        self.assertIn("WELL-DASHBOARD-7: opened #101", lines)   # the new Sentry issue was still opened
        self.assertNotIn(SENTRY_TOKEN, " ".join(lines))

    def test_a_failed_closed_listing_is_a_failed_poll_and_the_next_one_catches_up(self):
        clock = Clock()
        fake = Fake([sentry_issue()], gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()})
        fake.closed_errors = [500] * 3   # a GET: tried three times, then the poll fails
        p, lines, _, _ = poller(fake, clock=clock)
        self.assertFalse(p.poll())
        self.assertIn("WELL-DASHBOARD-7: opened #101", lines)   # the new Sentry issue went first
        clock.now = p.wait_until
        self.assertTrue(p.poll())
        self.assertEqual(len(fake.resolves()), 1)

    def test_new_sentry_issues_are_handled_before_the_closings(self):
        fake = Fake([sentry_issue()], gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()})
        self.polled(fake, minutes=0)
        paths = [urlparse(u).path for _, u, _, _ in fake.calls]
        created = paths.index(f"/repos/{REPO}/issues", paths.index(f"/repos/{REPO}/labels"))
        self.assertLess(created, paths.index("/api/0/organizations/well-cs/shortids/WELL-BACKEND-2/"))

    def test_a_failed_lookup_or_resolve_warns_for_that_issue_and_the_next_poll_tries_again(self):
        # 403 on the lookup is a read failing, not a token without event:write
        for failure in ("lookup 500", "lookup 403", "resolve 500"):
            with self.subTest(failure=failure):
                clock = Clock()
                second = closed_issue(number=10, short_id="WELL-BACKEND-3", closed_at="2026-11-14T12:00:40Z")
                fake = Fake([sentry_issue()], gh_issues=[closed_issue(), second],
                            groups={"WELL-BACKEND-2": group(), "WELL-BACKEND-3": group("556")})
                where, status = failure.split()
                if where == "lookup":
                    fake.lookup_errors = [int(status)] * (3 if status == "500" else 1)   # GETs retried on a 5xx
                else:
                    fake.resolve_status = int(status)
                p, lines, warnings, _ = poller(fake, clock=clock)
                self.assertTrue(p.poll())
                warned = [line for line in lines if line.startswith("[WARN]")]
                self.assertEqual(len(warned), 2 if where == "resolve" else 1, lines)
                self.assertTrue(warned[0].startswith("[WARN] WELL-BACKEND-2 (#9, closed): "), warned)
                self.assertIn(f"HTTP {status}", warned[0])
                self.assertNotIn("event:write", " ".join(lines))
                self.assertIn("WELL-DASHBOARD-7: opened #102", lines)   # new errors still became issues
                self.assertFalse(p.resolving.forbidden)
                self.assertEqual(warnings, [])
                fake.resolve_status = None
                clock.now += 60
                self.assertTrue(p.poll())
                self.assertEqual({g["status"] for g in fake.groups.values()}, {"resolved"})

    def test_the_daily_run_resolves_nothing(self):
        env = {"SENTRY_API_TOKEN": SENTRY_TOKEN, "GITHUB_TOKEN": GITHUB_TOKEN, "GITHUB_REPOSITORY": REPO}
        fake = Fake([sentry_issue()], gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()})
        sentry_github.run(fake, env, log=lambda line: None)
        self.assertEqual(fake.lookups(), [])
        self.assertFalse(any(parse_qs(urlparse(u).query).get("state") == ["closed"] for _, u, _, _ in fake.calls))

    def test_dry_run_resolves_nothing(self):
        env = {"SENTRY_API_TOKEN": SENTRY_TOKEN, "GITHUB_TOKEN": GITHUB_TOKEN, "GITHUB_REPOSITORY": REPO}
        fake = Fake(gh_issues=[closed_issue()], groups={"WELL-BACKEND-2": group()})
        lines = []
        sentry_github.run(fake, env, dry_run=True, log=lines.append, closed_since=Clock.START)
        self.assertEqual(fake.resolves(), [])
        self.assertIn("[dry run] would resolve WELL-BACKEND-2 in Sentry (#9 closed as completed)", lines)


class ResolveByHandTest(TestCase):
    """python -m utils.sentry_github --resolve SHORT_ID ..."""

    def test_resolves_the_given_short_ids(self):
        fake = Fake(groups={"WELL-BACKEND-2": group(), "WELL-BACKEND-3": group("556", status="resolved")})
        lines = []
        code = sentry_github.resolve_short_ids(fake, ENV, ["WELL-BACKEND-2", "WELL-BACKEND-3"], log=lines.append)
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["WELL-BACKEND-2: resolved", "WELL-BACKEND-3: already resolved"])
        self.assertEqual(fake.resolves(), ["/api/0/organizations/well-cs/issues/555/"])

    def test_unknown_ids_and_a_token_without_event_write_fail(self):
        fake = Fake(groups={"WELL-BACKEND-2": group()}, resolve_status=403)
        lines = []
        code = sentry_github.resolve_short_ids(fake, ENV, ["WELL-BACKEND-2", "WELL-NOPE-1", "a/b"], log=lines.append)
        self.assertEqual(code, 1)
        self.assertIn("(the token needs event:write)", lines[0])
        self.assertEqual(lines[1:], ["WELL-NOPE-1: no such Sentry issue in well-cs", "'a/b' is not a Sentry short id"])
        self.assertEqual(sentry_github.resolve_short_ids(fake, {}, ["WELL-BACKEND-2"], log=lines.append), 1)


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
