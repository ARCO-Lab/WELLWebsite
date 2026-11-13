"""Unit tests for maintainer_summary.py (the daily maintainer's email), with the GitHub API and SMTP faked.
Run from this folder: python3 -m unittest discover -s .github/scripts -p 'test_maintainer*.py'"""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest

import maintainer_summary as ms
from maintainer_fakes import FakeTransport

REPO = "ARCO-Lab/WELLWebsite"
LOGIN = "maint-user"


def pr(number, branch, labels=(), user=LOGIN, sha=None, draft=False, head_repo=REPO):
    return {"number": number, "title": f"Fix {number}", "html_url": f"https://github.com/{REPO}/pull/{number}",
            "head": {"ref": branch, "sha": sha or f"{number:040x}", "repo": {"full_name": head_repo}},
            "user": {"login": user}, "labels": [{"name": name} for name in labels], "draft": draft}


def checks(*conclusions, status="completed", required=True):
    """Check runs with these conclusions, after the five required ones (all passed) unless required=False."""
    runs = [{"id": i, "name": name, "status": "completed", "conclusion": "success"}
            for i, name in enumerate(ms.REQUIRED_CHECKS if required else [])]
    runs += [{"id": 100 + i, "name": f"job{i}", "status": status, "conclusion": c} for i, c in enumerate(conclusions)]
    return {"check_runs": runs}


def classify(p, files, ci, *args, published="head", **kwargs):
    """ms.classify for this repository and login; by default the publish job's record matches the head."""
    if published == "head":
        published = p["head"]["sha"]
    return ms.classify(p, files, ci, REPO, LOGIN, *args, published=published, **kwargs)


def published(sha, user=LOGIN, edited=False):
    """A publish comment as the GitHub API lists it."""
    return {"user": {"login": user}, "body": f"Pushed.\n\n<!-- maintainer-published: {sha} -->",
            "created_at": "2026-11-12T11:40:00Z", "updated_at": "2026-11-12T11:45:00Z" if edited else
            "2026-11-12T11:40:00Z"}


class FakeSMTP:
    """Records what the email code does; `starttls` says whether the server offers STARTTLS."""
    instances = []

    def __init__(self, host, port, timeout=None, context=None, starttls=True):
        self.host, self.port, self.starttls_offered = host, port, starttls
        self.events, self.sent = [], []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        self.events.append("ehlo")

    def has_extn(self, name):
        return name == "starttls" and self.starttls_offered

    def starttls(self, context=None):
        self.events.append("starttls")

    def login(self, user, password):
        self.events.append(("login", user))

    def send_message(self, message):
        self.sent.append(message)


class FakeSmtpModule:
    SMTP = FakeSMTP
    SMTP_SSL = FakeSMTP


class NoStartTlsModule:
    @staticmethod
    def SMTP(host, port, timeout=None):
        return FakeSMTP(host, port, timeout, starttls=False)


class ClassifyTests(unittest.TestCase):
    def test_ready_needs_green_ci_audit_and_low_risk(self):
        verdict, reasons = classify(pr(1, "maint/a", ["risk:low", "self-check:passed"]), ["README.md"], "green")
        self.assertEqual(("ready", []), (verdict, reasons))

    def test_each_missing_condition_is_a_reason(self):
        verdict, reasons = classify(pr(1, "maint/a", ["risk:high", "self-check:findings"], draft=True),
                                    ["README.md"], "red", ["Dashboard build"])
        self.assertEqual("review", verdict)
        self.assertIn("CI failed: Dashboard build", reasons)
        self.assertIn("labelled risk:high", reasons)
        self.assertIn("its self-check has open findings", reasons)
        self.assertIn("draft", reasons)

    def test_unaudited_and_unlabelled(self):
        _, reasons = classify(pr(1, "maint/a"), ["README.md"], "pending")
        self.assertEqual(["CI still running", "no risk label", "not self-checked yet (no self-check:passed label)"],
                         reasons)

    def test_not_opened_by_the_maintainer(self):
        approved = ["risk:low", "self-check:passed", "maintainer"]
        for p in [pr(1, "maint/a", approved, user="someone"), pr(1, "maint/a", approved, head_repo="fork/WELLWebsite"),
                  pr(1, "maint/a", approved, head_repo=None),
                  # The owner's own pull request from another branch: with a PAT, the same account as the maintainer.
                  pr(1, "feat/charts", approved), pr(1, "main", approved), pr(1, "fix/maint/x", approved)]:
            verdict, reasons = classify(p, ["README.md"], "green")
            self.assertEqual(("review", ["not opened by the maintainer"]), (verdict, reasons))
        # No maintainer login known: nothing counts as the maintainer's.
        self.assertEqual("review", ms.classify(pr(1, "maint/a", approved, user=""), [], "green", REPO, "",
                                               published="sha1")[0])

    def test_the_head_must_be_the_commit_the_maintainer_published(self):
        labels = ["risk:low", "self-check:passed"]
        p = pr(1, "maint/a", labels, sha="a" * 40)
        self.assertEqual(("ready", []), classify(p, ["README.md"], "green", published="a" * 40))
        _, reasons = classify(p, ["README.md"], "green", published="b" * 40)
        self.assertEqual(["changed since the maintainer published it (head aaaaaaaaaaaa, published bbbbbbbbbbbb)"],
                         reasons)
        _, reasons = classify(p, ["README.md"], "green", published=None)
        self.assertEqual(["no record of the commit the maintainer published"], reasons)

    def test_published_commit_counts_only_the_maintainers_unedited_comments(self):
        a, b = "a" * 40, "b" * 40
        self.assertEqual(b, ms.published_commit([published(a), published(b)], LOGIN))   # the newest
        self.assertEqual(a, ms.published_commit([published(a), published(b, user="someone")], LOGIN))
        self.assertEqual(a, ms.published_commit([published(a), published(b, edited=True)], LOGIN))
        self.assertIsNone(ms.published_commit([published("not-a-sha")], LOGIN))
        self.assertIsNone(ms.published_commit([published(a)], ""))

    def test_required_checks_missing(self):
        _, reasons = classify(pr(1, "maint/a", ["risk:low", "self-check:passed"]), ["README.md"], "missing",
                              missing_checks=["Dashboard image"])
        self.assertEqual(["required checks missing: Dashboard image"], reasons)

    def test_risky_files_override_a_low_risk_label(self):
        for path in ["dashboard/backend/app/api/routes/exports.py", "dashboard/backend/app/api/services/quality.py",
                     "dashboard/backend/app/utils/backup.py", "dashboard/backend/app/utils/heartbeat.py",
                     "dashboard/backend/app/utils/alerts.py", "dashboard/backend/app/scripts/backup_db.py",
                     "dashboard/backend/app/scripts/check_alerts.py", "dashboard/backend/app/scripts/daily_digest.py",
                     "dashboard/backend/tests/test_alerts.py", "dashboard/backend/tests/golden/x.csv",
                     "dashboard/e2e/fixtures/expected.json", "dashboard/e2e/data.spec.ts",
                     "dashboard/loadtest/seed.sql", "dashboard/frontend/tsconfig.json",
                     "dashboard/frontend/eslint.config.mjs", "dashboard/frontend/postcss.config.mjs",
                     "dashboard/frontend/scripts/copy-maplibre-worker.mjs",
                     "dashboard/frontend/scripts/proxyBackend.test.mjs", "dashboard/frontend/src/lib/proxyBackend.ts",
                     "dashboard/frontend/src/pages/index.tsx", "dashboard/frontend/src/instrumentation.ts",
                     "dashboard/frontend/sentry.server.config.ts", "dashboard/frontend/public/robots.txt",
                     # Not on the low-risk list at all, so they need a person whatever they are
                     "dashboard/backend/app/x.py", "Makefile", "scripts/anything.sh",
                     # Documentation where it is part of something risky
                     ".github/workflows/README.md", "home/readme.md",
                     "dashboard/backend/app/db/migrations/0006_x.sql", "dashboard/backend/app/db/models.py",
                     "dashboard/backend/app/scripts/migrate.py", "docker-compose.yml", "deploy.sh", "nginx.conf",
                     "dashboard/frontend/Dockerfile", "dashboard/backend/.dockerignore",
                     "dashboard/backend/app/scripts/inject_from_api.py",
                     "dashboard/backend/app/scripts/licor_backfill.py",
                     "dashboard/backend/app/scripts/scheduler_temp.py", "dashboard/backend/app/tasks/exports.py",
                     "dashboard/backend/app/utils/parsers.py", "dashboard/backend/app/utils/sampling_csv.py",
                     "dashboard/backend/app/config.py", "dashboard/backend/requirements.txt",
                     "dashboard/frontend/package.json", "dashboard/frontend/package-lock.json",
                     "dashboard/backend/app/utils/sentry.py", "dashboard/backend/app/utils/guards.py",
                     "dashboard/frontend/src/lib/sentry.ts", "dashboard/backend/app/server.py",
                     "dashboard/backend/app/ops/auth.py", "dashboard/backend/app/ops/templates/login.html",
                     "dashboard/frontend/src/pages/api/latest.ts", "dashboard/frontend/next.config.mjs",
                     ".gitignore", "dashboard/frontend/.gitignore", ".gitattributes",
                     ".github/workflows/ci.yml", ".github/maintainer/PROMPT.md",
                     ".github/scripts/maintainer_summary.py", ".claude/settings.json",
                     "home/index.php", "wordpress/uploads.ini"]:
            verdict, reasons = classify(pr(1, "maint/a", ["risk:low", "self-check:passed"]), [path], "green")
            self.assertEqual("review", verdict, path)
            self.assertIn(path, reasons[0])

    def test_only_the_low_risk_list_is_low_risk(self):
        self.assertEqual([], ms.risky_files(["dashboard/frontend/src/components/Map.tsx",
                                             "dashboard/frontend/src/hooks/useWindRose.ts",
                                             "dashboard/frontend/src/utils/chartStyle.ts",
                                             "dashboard/frontend/src/styles/globals.css", "README.md",
                                             "dashboard/backend/README.md", "docs/configuration.md"]))

    def test_a_new_test_file_is_low_risk_but_a_changed_one_is_not(self):
        new = "dashboard/backend/tests/test_new_thing.py"
        self.assertEqual([], ms.risky_files([new], added=[new]))
        self.assertEqual([new], ms.risky_files([new]))
        # Only a test module counts, not a helper or data file a test reads
        helper = "dashboard/backend/tests/golden/expected.csv"
        self.assertEqual([helper], ms.risky_files([helper], added=[helper]))
        _, reasons = classify(pr(1, "maint/a", ["risk:low", "self-check:passed"]), [new], "green", added=[new])
        self.assertEqual([], reasons)

    def test_ci_state(self):
        self.assertEqual(("none", ms.REQUIRED_CHECKS), ms.ci_state([]))
        self.assertEqual(("green", []), ms.ci_state(checks("success", "skipped", "neutral")["check_runs"]))
        self.assertEqual(("red", []), ms.ci_state(checks("success", "failure")["check_runs"]))
        self.assertEqual(("pending", []), ms.ci_state(checks(None, status="in_progress")["check_runs"]))
        # Everything that ran passed, but the required jobs never ran (CodeQL alone, say).
        self.assertEqual(("missing", ms.REQUIRED_CHECKS), ms.ci_state(checks("success", required=False)["check_runs"]))
        # A required job that was skipped doesn't count as passed.
        runs = checks()["check_runs"]
        runs[2]["conclusion"] = "skipped"
        self.assertEqual(("missing", ["Dashboard image"]), ms.ci_state(runs))

    def test_the_newest_run_of_a_check_counts(self):
        runs = checks()["check_runs"] + [{"id": -1, "name": "Dashboard build", "status": "completed",
                                          "conclusion": "failure"}]
        self.assertEqual(("green", []), ms.ci_state(runs))   # the failure is older than the success
        runs.append({"id": 50, "name": "Dashboard build", "status": "completed", "conclusion": "failure"})
        self.assertEqual(("red", []), ms.ci_state(runs))

    def test_required_checks_match_deploy_sh(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, "deploy.sh"), encoding="utf-8") as f:
            line = next(line for line in f if line.startswith("REQUIRED_CHECKS=("))
        self.assertEqual(ms.REQUIRED_CHECKS, re.findall(r'"([^"]+)"', line.split("#")[0]))


def routes(prs, files=None, runs=None, compare=None, comments=None, commits=None):
    r = {("GET", f"/repos/{REPO}/pulls"): prs}
    for p in prs:
        r[("GET", f"/repos/{REPO}/pulls/{p['number']}/files")] = [
            {"filename": f, "status": "modified"} for f in (files or {}).get(p["number"], ["README.md"])]
        r[("GET", f"/repos/{REPO}/commits/{p['head']['sha']}/check-runs")] = (runs or {}).get(p["number"],
                                                                                           checks("success"))
        # By default the publish job's comment records the pull request's head
        r[("GET", f"/repos/{REPO}/issues/{p['number']}/comments")] = (comments or {}).get(
            p["number"], [published(p["head"]["sha"])])
        # By default one commit, the head, authored by the maintainer
        r[("GET", f"/repos/{REPO}/pulls/{p['number']}/commits")] = (commits or {}).get(
            p["number"], [{"sha": p["head"]["sha"], "author": {"login": LOGIN}}])
    if compare:
        r[("GET", f"/repos/{REPO}/compare/{compare[0]}...{compare[1]}")] = {"commits": compare[2]}
    return r


def env(**extra):
    base = {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t", "MAINTAINER_LOGIN": LOGIN, "RUN_URL": "https://run/1",
            "CLAUDE_OUTCOME": "success",
            "CLAUDE_RESULT": json.dumps({"summary": "Fixed one thing.", "actions": [
                {"what": "Opened a PR for the export timeout", "url": "https://github.com/x/pull/9"}],
                "skipped": ["Sentry WELL-12: already fixed by #80"], "errors": []})}
    base.update(extra)
    return base


class GatherTests(unittest.TestCase):
    def test_selects_maint_branches_of_the_maintainer_and_labelled_prs(self):
        prs = [pr(1, "maint/a", ["risk:low", "self-check:passed"]), pr(2, "feat/x"), pr(3, "maint/b", user="someone"),
               pr(4, "fix/y", ["maintainer"], user="someone"),
               pr(5, "feat/owner", ["risk:low", "self-check:passed", "maintainer"])]
        reviewed, result, errors, _ = ms.gather(env(), FakeTransport(routes(prs)))
        self.assertEqual([1, 4, 5], [p["number"] for p, _, _ in reviewed])
        self.assertEqual("ready", reviewed[0][1])
        self.assertIn("not opened by the maintainer", reviewed[1][2])
        # The owner's labelled pull request from a feature branch is listed, but never ready.
        self.assertEqual(("review", ["not opened by the maintainer"]), reviewed[2][1:])
        self.assertEqual("Fixed one thing.", result["summary"])
        self.assertEqual([], errors)

    def test_a_commit_added_after_publishing_needs_review(self):
        prs = [pr(1, "maint/a", ["risk:low", "self-check:passed"], sha="c" * 40),
               pr(2, "maint/b", ["risk:low", "self-check:passed"], sha="d" * 40)]
        comments = {1: [published("a" * 40)], 2: [published("d" * 40, edited=True)]}
        reviewed, _, errors, _ = ms.gather(env(), FakeTransport(routes(prs, comments=comments)))
        self.assertEqual([], errors)
        self.assertEqual(("review", ["changed since the maintainer published it (head cccccccccccc, published "
                                     "aaaaaaaaaaaa)"]), reviewed[0][1:])
        self.assertEqual(("review", ["no record of the commit the maintainer published"]), reviewed[1][1:])

    def test_commits_by_anyone_else_need_review(self):
        labels = ["risk:low", "self-check:passed"]
        prs = [pr(1, "maint/a", labels, sha="c" * 40), pr(2, "maint/b", labels, sha="d" * 40)]
        commits = {1: [{"sha": "e" * 40, "author": {"login": "someone"}}, {"sha": "c" * 40, "author": {"login": LOGIN}}],
                   2: [{"sha": "d" * 40, "author": None}]}   # an email GitHub can't tie to an account
        reviewed, _, errors, _ = ms.gather(env(), FakeTransport(routes(prs, commits=commits)))
        self.assertEqual([], errors)
        self.assertEqual(("review", ["has commits not authored by the maintainer: eeeeeeeeeeee"]), reviewed[0][1:])
        self.assertEqual(("review", ["has commits not authored by the maintainer: dddddddddddd"]), reviewed[1][1:])

    def test_claude_failure_and_missing_report_are_errors(self):
        _, result, errors, _ = ms.gather(env(CLAUDE_OUTCOME="failure", CLAUDE_RESULT=""), FakeTransport(routes([])))
        self.assertIsNone(result)
        self.assertEqual(["the Claude step's outcome was failure"], errors)
        _, _, errors, _ = ms.gather(env(CLAUDE_RESULT="not json"), FakeTransport(routes([])))
        self.assertEqual(["Claude finished but its report was missing or not JSON"], errors)

    def test_inputs_errors_and_notes_are_carried(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "inputs.json")
            with open(path, "w") as f:
                json.dump({"errors": ["sentry_issues: HTTP 500"], "notes": ["no Sentry token"]}, f)
            _, _, errors, notes = ms.gather(env(INPUTS_FILE=path), FakeTransport(routes([])))
        self.assertEqual(["collecting inputs: sentry_issues: HTTP 500"], errors)
        self.assertEqual(["no Sentry token"], notes)

    def test_refused_branches_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "publish.json")
            with open(path, "w") as f:
                json.dump({"published": [{"branch": "maint/a", "action": "opened as a draft"}],
                           "refused": [{"branch": "maint/b", "reason": "changes 30 files (at most 20)"}],
                           "errors": ["maint/c: HTTP 500"]}, f)
            _, _, errors, notes = ms.gather(env(PUBLISH_FILE=path), FakeTransport(routes([])))
            _, _, missing, _ = ms.gather(env(PUBLISH_FILE=os.path.join(tmp, "none.json")),
                                         FakeTransport(routes([])))
        self.assertEqual(["publishing: maint/c: HTTP 500",
                          "not published: maint/b: changes 30 files (at most 20)"], errors)
        self.assertEqual(["maint/a: opened as a draft"], notes)
        self.assertEqual(["the publish step left no result (did it run?)"], missing)

    def test_github_error_is_reported_not_raised(self):
        transport = FakeTransport({("GET", f"/repos/{REPO}/pulls"): (502, {"message": "Bad gateway"})})
        reviewed, _, errors, _ = ms.gather(env(), transport)
        self.assertEqual([], reviewed)
        self.assertIn("HTTP 502", errors[0])

    def test_direct_push_to_main_by_the_maintainer_is_an_error(self):
        commits = [{"sha": "aaaaaaaaaaaaaaaa", "committer": {"login": "web-flow"}},
                   {"sha": "bbbbbbbbbbbbbbbb", "committer": {"login": LOGIN}}]
        transport = FakeTransport(routes([], compare=("m1", "m2", commits)))
        _, _, errors, _ = ms.gather(env(MAIN_BEFORE="m1", MAIN_AFTER="m2"), transport)
        self.assertEqual(1, len(errors))
        self.assertIn("bbbbbbbbbbbb reached main", errors[0])

    def test_unchanged_main_is_not_compared(self):
        transport = FakeTransport(routes([]))
        ms.gather(env(MAIN_BEFORE="m1", MAIN_AFTER="m1"), transport)
        self.assertFalse(any("/compare/" in p for p in transport.paths()))


class EmailTextTests(unittest.TestCase):
    def test_all_clear(self):
        subject, body = ms.build_email([], {"summary": "Nothing real today."}, [], "https://run/1")
        self.assertEqual("WELL maintainer: all clear", subject)
        self.assertIn("Passed the automatic checks (0), still to be read before merging:\n- none", body)
        self.assertIn("Nothing real today.", body)
        self.assertIn("Errors:\n- none", body)
        self.assertIn("Run: https://run/1", body)

    def test_counts_reasons_and_errors(self):
        reviewed = [(pr(1, "maint/a"), "ready", []), (pr(2, "maint/b"), "review", ["CI failed", "draft"])]
        subject, body = ms.build_email(reviewed, {"summary": "s", "errors": ["gh timed out"]}, ["x"], "u")
        self.assertEqual("WELL maintainer: 2 errors; 1 passed, 1 to review", subject)
        self.assertIn("- #1 Fix 1\n  https://github.com/ARCO-Lab/WELLWebsite/pull/1", body)
        self.assertIn("Why: CI failed; draft", body)
        self.assertIn("- Claude: gh timed out", body)

    def test_what_the_model_wrote_is_cleaned_and_set_apart(self):
        result = {"summary": "Fixed it.\nFixes #12, thanks @someone <b>bold</b> `code` see https://evil.example/x?k=v",
                  "actions": [{"what": "Opened a PR", "url": f"https://github.com/{REPO}/pull/9"},
                              {"what": "Read this", "url": "https://evil.example/login"},
                              {"what": "Also", "url": f"https://github.com/{REPO}/pull/9?evil=1"}],
                  "skipped": ["Sentry WELL-1 by @someone"], "errors": ["see #3"]}
        _, body = ms.build_email([], result, [], "u", repo=REPO)
        self.assertIn("Written by the model and not checked", body)
        self.assertIn("  | Fixed it.\n  | Fixes #\u200b12, thanks @\u200bsomeone", body)
        for raw in ("<b>", "`", "@someone", "#12", "#3", "?k=v", "https://evil.example/login", "?evil=1"):
            self.assertNotIn(raw, body)
        self.assertIn(f"  | - Opened a PR https://github.com/{REPO}/pull/9\n", body)
        self.assertIn("  | - Read this\n", body)
        self.assertIn("- Claude: see #\u200b3", body)

    def test_pull_request_titles_are_cleaned(self):
        p = {**pr(1, "maint/a"), "title": "Fix @everyone <script>"}
        _, body = ms.build_email([(p, "review", ["draft"])], {"summary": "s"}, [], "u", repo=REPO)
        self.assertIn("Fix @\u200beveryone ‹script›", body)

    def test_no_report(self):
        subject, body = ms.build_email([], None, ["the Claude step's outcome was failure"], "u")
        self.assertEqual("WELL maintainer: 1 error", subject)
        self.assertIn("Claude gave no report", body)

    def test_dry_run_is_said(self):
        _, body = ms.build_email([], {"summary": "s"}, [], "u", dry_run=True)
        self.assertTrue(body.startswith("This was a dry run"))


class MainTests(unittest.TestCase):
    def setUp(self):
        FakeSMTP.instances = []

    def run_main(self, smtp=FakeSmtpModule, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            summary = os.path.join(tmp, "summary.md")
            with contextlib.redirect_stdout(io.StringIO()):
                code = ms.main(env(GITHUB_STEP_SUMMARY=summary, **extra), FakeTransport(routes([])), smtp)
            with open(summary) as f:
                return code, f.read()

    def test_without_smtp_it_prints_and_succeeds(self):
        code, summary = self.run_main()
        self.assertEqual(0, code)
        self.assertIn("WELL maintainer: all clear", summary)
        self.assertEqual([], FakeSMTP.instances)

    def test_sends_one_email_with_starttls_and_login(self):
        code, _ = self.run_main(SMTP_HOST="smtp.example.com", SMTP_PORT="587", SMTP_USER="u@example.com",
                                SMTP_PASSWORD="p", ALERT_EMAILS="a@example.com, b@example.com; nope")
        self.assertEqual(0, code)
        (server,) = FakeSMTP.instances
        self.assertEqual(["ehlo", "starttls", "ehlo", ("login", "u@example.com")], server.events)
        (message,) = server.sent
        self.assertEqual("a@example.com, b@example.com", message["To"])
        self.assertEqual("u@example.com", message["From"])
        self.assertEqual("WELL maintainer: all clear", message["Subject"])

    def test_never_logs_in_without_tls(self):
        code, _ = self.run_main(smtp=NoStartTlsModule, SMTP_HOST="h", SMTP_PORT="25", SMTP_USER="u@example.com",
                                SMTP_PASSWORD="p", ALERT_EMAILS="a@example.com")
        self.assertEqual(1, code)
        self.assertNotIn(("login", "u@example.com"), FakeSMTP.instances[0].events)
        self.assertEqual([], FakeSMTP.instances[0].sent)

    def test_github_token_mode_is_explained(self):
        _, summary = self.run_main(TOKEN_MODE="github_token")
        self.assertIn("opened as github-actions[bot] until WELL_MAINTAINER_PAT is set", summary)
        _, summary = self.run_main(TOKEN_MODE="pat")
        self.assertNotIn("WELL_MAINTAINER_PAT", summary)

    def test_smtp_without_recipients_fails(self):
        code, _ = self.run_main(SMTP_HOST="h", SMTP_PORT="587", SMTP_FROM="f@example.com", ALERT_EMAILS="")
        self.assertEqual(1, code)

    def test_missing_github_settings(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, ms.main({"GITHUB_REPOSITORY": REPO}, FakeTransport({}), FakeSmtpModule))


if __name__ == "__main__":
    unittest.main()
