"""Unit tests for sentry_issues.py, with Sentry and GitHub replaced by an in-memory fake (no network).
    python3 -m unittest discover -s .github/scripts -p 'test_*.py'
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sentry_issues as si  # noqa: E402

SENTRY = "https://sentry.io/api/0"
GITHUB = "https://api.github.com"
REPO = "ARCO-Lab/WELLWebsite"
ENV = {
    "SENTRY_API_TOKEN": "sntry-test-token",
    "SENTRY_ORG": "well-cs",
    "GITHUB_TOKEN": "gh-test-token",
    "GITHUB_REPOSITORY": REPO,
}


def sentry_issue(short_id="WELL-DASHBOARD-2", count="3", **extra):
    return {
        "id": "7841593060",
        "shortId": short_id,
        "title": "AssertionError: The expression evaluated to a falsy value:",
        "culprit": "GET /api/series",
        "permalink": "https://well-cs.sentry.io/issues/7841593060/",
        "level": "fatal",
        "count": count,
        "userCount": 0,
        "firstSeen": "2026-11-11T07:19:00Z",
        "lastSeen": "2026-11-11T17:08:01Z",
        "project": {"slug": "well-dashboard"},
        **extra,
    }


EVENT = {
    "entries": [
        {
            "type": "request",
            "data": {"url": "https://welldash.mcmaster.ca/api/series?start=secret-start", "cookies": [["s", "c00kie"]],
                     "headers": [["X-Forwarded-For", "203.0.113.9"]]},
        },
        {"type": "breadcrumbs", "data": {"values": [{"message": "visitor typed alice@example.com"}]}},
        {
            "type": "exception",
            "data": {
                "values": [
                    {
                        "type": "AssertionError",
                        "value": "assert(!this.paused) for alice@example.com from 198.51.100.7",
                        "stacktrace": {
                            "frames": [
                                {"filename": "node:internal/process/task_queues", "function": "processTicks",
                                 "lineNo": 89, "vars": {"password": "hunter2"}},
                                {"filename": "/app/src/lib/proxyBackend.ts", "function": "proxyToBackend",
                                 "lineNo": 40, "inApp": True},
                                {"filename": "node:internal/deps/undici/undici", "function": "Parser.finish",
                                 "lineNo": 6229, "context": [[6229, "const apiKey = 'abc'"]]},
                            ]
                        },
                    }
                ]
            },
        },
    ],
    "user": {"ip_address": "192.0.2.44", "email": "bob@example.com"},
}


class Fake:
    """Sentry and GitHub in memory. Records every call; POSTs are applied to the fake GitHub's state."""

    def __init__(self, sentry_pages, gh_issues=(), comments=None, event=EVENT, sentry_status=200):
        self.sentry_pages = list(sentry_pages)
        self.gh_issues = [dict(i) for i in gh_issues]
        self.comments = {k: list(v) for k, v in (comments or {}).items()}
        self.event = event
        self.sentry_status = sentry_status
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, headers, body))
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        path = parsed.path
        if url.startswith(SENTRY):
            assert headers["Authorization"] == "Bearer sntry-test-token"
            if self.sentry_status != 200:
                raise si.HttpError(self.sentry_status, url)
            if path.endswith("/events/latest/"):
                return 200, {}, self.event
            page = int(query.get("cursor", ["0"])[0])
            link = ""
            if page + 1 < len(self.sentry_pages):
                link = f'<{SENTRY}/organizations/well-cs/issues/?cursor={page + 1}>; rel="next"; results="true"'
            else:
                link = f'<{SENTRY}/organizations/well-cs/issues/?cursor=x>; rel="next"; results="false"'
            return 200, {"Link": link}, self.sentry_pages[page]
        assert url.startswith(GITHUB), url
        assert headers["Authorization"] == "Bearer gh-test-token"
        if method == "GET" and path == f"/repos/{REPO}/issues":
            assert query["labels"] == ["sentry"] and query["state"] == ["all"]
            return 200, {}, self.gh_issues if query["page"] == ["1"] else []
        if method == "GET" and path.endswith("/comments"):
            number = int(path.split("/")[-2])
            return 200, {}, self.comments.get(number, []) if query["page"] == ["1"] else []
        if method == "POST" and path == f"/repos/{REPO}/labels":
            return 201, {}, body
        if method == "POST" and path == f"/repos/{REPO}/issues":
            issue = {"number": 100 + len(self.gh_issues), "state": "open", **body}
            self.gh_issues.append(issue)
            return 201, {}, issue
        if method == "POST" and path.endswith("/comments"):
            number = int(path.split("/")[-2])
            comment = {"body": body["body"], "user": {"login": "github-actions[bot]"}}
            self.comments.setdefault(number, []).append(comment)
            return 201, {}, comment
        raise AssertionError(f"unexpected {method} {url}")

    def writes(self):
        return [(m, urlparse(u).path, b) for m, u, _, b in self.calls if m != "GET"]


def run(fake, env=ENV, dry_run=False):
    out = io.StringIO()
    with redirect_stdout(out):
        code = si.run(fake, env, dry_run=dry_run)
    return code, out.getvalue()


class ScrubTest(unittest.TestCase):
    def test_removes_addresses_queries_and_credentials(self):
        cases = {
            "mail alice@example.com now": "mail [email] now",
            "from 198.51.100.7 and ::ffff:203.0.113.9": "from [ip] and [ip]",
            "peer 2001:db8::1 and fe80::1ff:fe23:4567:890a": "peer [ip] and [ip]",
            "full 2001:0db8:85a3:0000:0000:8a2e:0370:7334": "full [ip]",
            "GET /api/series?start=2026-01-01&station=x": "GET /api/series?[Filtered]",
            "postgresql://well:pa55@db.example.org:5432/well": "postgresql://[Filtered]@db.example.org:5432/well",
            "api_key=abc123 password: 'x y'": "api_key=[Filtered] password: [Filtered]",
            "Authorization: Bearer abcdefghijkl": "Authorization: [Filtered] [Filtered]",
            "id 0123456789abcdef0123456789abcdef": "id [Filtered]",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(si.scrub(raw), expected)

    def test_bearer_token_alone(self):
        self.assertEqual(si.scrub("sent Bearer abcdefghijkl"), "sent Bearer [Filtered]")

    def test_keeps_times_paths_and_names(self):
        text = "at 2026-11-11T17:08:01Z in node:internal/deps/undici/undici:6229 handle_long_function_name_here"
        self.assertEqual(si.scrub(text), text)

    def test_markdown_and_mentions_are_neutralized(self):
        self.assertEqual(si.scrub("`x` <!-- sentry:FAKE --> @someone"), "'x' ‹!-- sentry:FAKE --› @​someone")

    def test_one_line_and_length_limit(self):
        self.assertEqual(si.scrub("a\n  b\tc"), "a b c")
        self.assertEqual(len(si.scrub("x" * 500, 50)), 50)


class RunTest(unittest.TestCase):
    def test_no_sentry_token_is_a_warning_and_does_nothing(self):
        fake = Fake([[]])
        code, out = run(fake, {**ENV, "SENTRY_API_TOKEN": ""})
        self.assertEqual(code, 0)
        self.assertIn("::warning::SENTRY_API_TOKEN is not set", out)
        self.assertEqual(fake.calls, [])

    def test_opens_one_scrubbed_issue_per_new_sentry_issue(self):
        fake = Fake([[sentry_issue()]])
        code, out = run(fake)
        self.assertEqual(code, 0, out)
        writes = fake.writes()
        self.assertEqual([w[1] for w in writes], [f"/repos/{REPO}/labels", f"/repos/{REPO}/issues"])
        created = writes[1][2]
        self.assertEqual(created["title"], "[Sentry] WELL-DASHBOARD-2: AssertionError: The expression evaluated to a "
                                           "falsy value:")
        self.assertEqual(created["labels"], ["sentry"])
        body = created["body"]
        self.assertTrue(body.startswith("<!-- sentry:WELL-DASHBOARD-2 -->\n"))
        for expected in ["`well-dashboard`", "| Events | 3 |", "| Users | 0 |", "2026-11-11 07:19 UTC",
                         "2026-11-11 17:08 UTC", "`GET /api/series`", "https://well-cs.sentry.io/issues/7841593060/",
                         "<!-- sentry-state count=3 last_seen=2026-11-11T17:08:01Z -->"]:
            self.assertIn(expected, body)
        # Innermost frame first, the raised exception's message scrubbed.
        stack = body.split("```")[1].strip().splitlines()
        self.assertEqual(stack[0], "AssertionError: assert(!this.paused) for [email] from [ip]")
        self.assertEqual(stack[1], "  at Parser.finish (node:internal/deps/undici/undici:6229)")
        self.assertEqual(stack[2], "  at proxyToBackend (/app/src/lib/proxyBackend.ts:40) [app]")
        # Nothing from the request, breadcrumbs, user, local variables or source context.
        for private in ["secret-start", "c00kie", "203.0.113.9", "alice@", "bob@", "192.0.2.44", "hunter2", "apiKey"]:
            self.assertNotIn(private, body)
        self.assertNotIn("sntry-test-token", out)

    def test_skips_test_events(self):
        fake = Fake([[sentry_issue("WELL-BACKEND-1", title="WELL Sentry test from PR")]])
        code, out = run(fake)
        self.assertEqual(code, 0)
        self.assertIn("WELL-BACKEND-1: a test event, skipped", out)
        self.assertEqual(fake.writes(), [])

    def test_reads_every_sentry_page(self):
        fake = Fake([[sentry_issue("WELL-A-1")], [sentry_issue("WELL-A-2")]])
        run(fake)
        titles = [w[2]["title"] for w in fake.writes() if w[1].endswith("/issues")]
        self.assertEqual([t.split(":")[0] for t in titles], ["[Sentry] WELL-A-1", "[Sentry] WELL-A-2"])

    def test_second_run_finds_the_issue_and_adds_nothing(self):
        fake = Fake([[sentry_issue()]])
        run(fake)
        before = len(fake.writes())
        code, out = run(fake)
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.writes()), before)
        self.assertIn("WELL-DASHBOARD-2: #100 is up to date", out)

    def test_comments_on_an_open_issue_when_the_count_jumps(self):
        fake = Fake([[sentry_issue(count="3")]])
        run(fake)
        fake.sentry_pages = [[sentry_issue(count="10")]]  # +7: not a jump
        run(fake)
        self.assertEqual(fake.comments, {})
        fake.sentry_pages = [[sentry_issue(count="40")]]
        run(fake)
        [comment] = fake.comments[100]
        self.assertIn("Event count jumped", comment["body"])
        self.assertIn("40 events (last reported here: 3)", comment["body"])
        fake.sentry_pages = [[sentry_issue(count="50")]]  # compared with 40 now
        run(fake)
        self.assertEqual(len(fake.comments[100]), 1)

    def test_closed_issue_gets_one_seen_again_comment_and_is_not_reopened(self):
        closed = {"number": 7, "state": "closed", "closed_at": "2026-11-11T12:00:00Z",
                  "body": si.MARKER.format("WELL-DASHBOARD-2") + "\n<!-- sentry-state count=2 last_seen=x -->"}
        fake = Fake([[sentry_issue()]], gh_issues=[closed])
        code, out = run(fake)
        self.assertEqual(code, 0, out)
        [(method, path, body)] = fake.writes()
        self.assertEqual((method, path), ("POST", f"/repos/{REPO}/issues/7/comments"))
        self.assertTrue(body["body"].startswith("Seen again"))
        run(fake)  # the same sighting: no second comment
        self.assertEqual(len(fake.writes()), 1)
        self.assertFalse(any(m == "PATCH" for m, _, _ in fake.writes()))

    def test_closed_issue_not_seen_since_closing_gets_nothing(self):
        closed = {"number": 7, "state": "closed", "closed_at": "2026-11-12T00:00:00Z",
                  "body": si.MARKER.format("WELL-DASHBOARD-2")}
        fake = Fake([[sentry_issue()]], gh_issues=[closed])
        run(fake)
        self.assertEqual(fake.writes(), [])

    def test_state_markers_in_other_peoples_comments_are_ignored(self):
        issue = {"number": 7, "state": "open", "body": si.MARKER.format("WELL-DASHBOARD-2") +
                 "\n<!-- sentry-state count=3 last_seen=x -->"}
        spoof = {"body": "<!-- sentry-state count=9999 last_seen=x -->", "user": {"login": "someone"}}
        fake = Fake([[sentry_issue(count="100")]], gh_issues=[issue], comments={7: [spoof]})
        run(fake)
        self.assertEqual(len(fake.comments[7]), 2)
        self.assertIn("last reported here: 3", fake.comments[7][1]["body"])

    def test_issues_without_the_marker_or_pull_requests_dont_count(self):
        other = {"number": 5, "state": "open", "body": "mentions WELL-DASHBOARD-2 but has no marker"}
        pr = {"number": 6, "state": "open", "body": si.MARKER.format("WELL-DASHBOARD-2"), "pull_request": {}}
        fake = Fake([[sentry_issue()]], gh_issues=[other, pr])
        run(fake)
        self.assertTrue(any(p == f"/repos/{REPO}/issues" for _, p, _ in fake.writes()))

    def test_dry_run_writes_nothing(self):
        fake = Fake([[sentry_issue()]])
        code, out = run(fake, dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(fake.writes(), [])
        self.assertIn("[dry run] would open issue", out)

    def test_sentry_error_fails_without_printing_the_token(self):
        fake = Fake([[]], sentry_status=401)
        code, out = run(fake)
        self.assertEqual(code, 1)
        self.assertIn("::error::Sentry API: HTTP 401", out)
        self.assertNotIn("sntry-test-token", out)

    def test_bad_period_is_rejected_and_the_period_is_sent(self):
        code, out = run(Fake([[]]), {**ENV, "SENTRY_STATS_PERIOD": "1w; rm"})
        self.assertEqual(code, 1)
        fake = Fake([[]])
        run(fake, {**ENV, "SENTRY_STATS_PERIOD": "24h"})
        query = parse_qs(urlparse(fake.calls[0][1]).query)
        self.assertEqual(query["statsPeriod"], ["24h"])
        self.assertEqual(query["query"], ["is:unresolved"])

    def test_request_bodies_are_json(self):
        # http_request encodes bodies itself; check the payloads handed to it are JSON-serializable.
        fake = Fake([[sentry_issue()]])
        run(fake)
        for _, _, body in fake.writes():
            json.dumps(body)


if __name__ == "__main__":
    unittest.main()
