"""Unit tests for maintainer_publish.py (the step that pushes the maintainer's branches and opens their pull
requests), with real git repositories in a temporary directory and the GitHub API faked.
Run: python3 -m unittest discover -s .github/scripts -p 'test_maintainer*.py'"""
import functools
import json
import os
import subprocess
import tempfile
import unittest

import maintainer_publish as mp
from maintainer_fakes import FakeTransport

REPO = "ARCO-Lab/WELLWebsite"
LOGIN = "maint-user"
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
            "-c", "core.autocrlf=false", "-c", "core.hooksPath=/dev/null"]


def git(cwd, *args):
    return subprocess.run(["git", *IDENTITY, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def routes(open_prs=None):
    return {
        ("GET", f"/repos/{REPO}/pulls"): open_prs or [],
        ("POST", f"/repos/{REPO}/labels"): (422, {"message": "already exists"}),
        ("POST", f"/repos/{REPO}/pulls"): (201, {"number": 101, "html_url": "https://github.com/x/pull/101"}),
        ("POST", f"/repos/{REPO}/issues/101/assignees"): (201, {}),
        ("POST", f"/repos/{REPO}/issues/101/labels"): {},
        ("POST", f"/repos/{REPO}/issues/80/labels"): {},
        ("POST", f"/repos/{REPO}/issues/101/comments"): (201, {}),
        ("POST", f"/repos/{REPO}/issues/80/comments"): (201, {}),
        ("DELETE", f"/repos/{REPO}/issues/80/labels/self-check:findings"): (404, {"message": "Label does not exist"}),
        ("POST", f"/repos/{REPO}/actions/workflows/ci.yml/dispatches"): (204, {}),
        ("POST", "/graphql"): {"data": {}},
    }


def description(branch, risk="low", audit="approved", **extra):
    return {"branch": branch, "title": f"Fix {branch}", "body": "## Summary\nA fix.", "risk": risk, "audit": audit,
            **extra}


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.origin = os.path.join(root, "origin.git")
        self.claude = os.path.join(root, "claude")      # where Claude commits (the maintain job)
        self.publisher = os.path.join(root, "publish")  # the publish job's checkout of main
        git(root, "init", "-q", "--bare", "-b", "main", self.origin)
        git(root, "clone", "-q", self.origin, self.claude)
        self.write("README.md", "hello\n")
        self.write("dashboard/backend/app/x.py", "x = 1\n")
        git(self.claude, "add", "-A")
        git(self.claude, "commit", "-qm", "init")
        git(self.claude, "push", "-q", "origin", "HEAD:main")
        git(root, "clone", "-q", self.origin, self.publisher)
        self.bundle = os.path.join(root, "branches.bundle")
        self.gh_calls = []

    def write(self, path, text, repo=None):
        full = os.path.join(repo or self.claude, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def branch(self, name, files, base="origin/main"):
        """A maint branch in Claude's checkout, with one commit writing `files` ({path: text})."""
        git(self.claude, "switch", "-q", "-c", name, base)
        for path, text in files.items():
            self.write(path, text)
        git(self.claude, "add", "-A")
        git(self.claude, "commit", "-qm", f"change on {name}")
        return git(self.claude, "rev-parse", "HEAD").strip()

    def make_bundle(self):
        # As the workflow makes it: only the commits that aren't on main.
        git(self.claude, "fetch", "-q", "origin")
        git(self.claude, "bundle", "create", "-q", self.bundle, "--branches=maint/*", "--not", "origin/main")

    def remote(self, name):
        out = git(self.publisher, "ls-remote", "origin", f"refs/heads/{name}").split()
        return out[0] if out else None

    def publish(self, pull_requests, open_prs=None, **env):
        self.make_bundle()
        transport = FakeTransport(routes(open_prs))

        def gh_cli(args):
            self.gh_calls.append(args)
            return True

        full_env = {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "pat", "MAINTAINER_LOGIN": LOGIN,
                    "ASSIGNEE": "owner", "TOKEN_MODE": "pat", "MAX_PRS": "3", "BUNDLE": self.bundle,
                    "CLAUDE_RESULT": json.dumps({"summary": "s", "actions": [], "skipped": [], "errors": [],
                                                 "pull_requests": pull_requests}), **env}
        out = mp.publish(full_env, transport, functools.partial(mp.run_git, cwd=self.publisher), gh_cli)
        return out, transport

    def posted(self, transport, path):
        return [c["body"] for c in transport.calls if c["method"] == "POST" and c["path"] == path]

    def test_a_low_risk_branch_is_pushed_and_opened(self):
        sha = self.branch("maint/fix-x", {"README.md": "better\n"})
        out, transport = self.publish([description("maint/fix-x")])
        self.assertEqual([], out["refused"] + out["errors"])
        self.assertEqual(sha, self.remote("maint/fix-x"))
        (pr,) = self.posted(transport, f"/repos/{REPO}/pulls")
        body = pr.pop("body")
        self.assertEqual({"title": "Fix maint/fix-x", "head": "maint/fix-x", "base": "main", "draft": False}, pr)
        # The model's body, fenced, under a line written by this script
        self.assertTrue(body.startswith("_Opened by the daily maintainer. The description below was written by the "
                                        "model"), body)
        self.assertTrue(body.endswith("\n\n```text\n## Summary\nA fix.\n```"), body)
        # The commit pushed is recorded for the summary
        (comment,) = self.posted(transport, f"/repos/{REPO}/issues/101/comments")
        self.assertIn(f"<!-- maintainer-published: {sha} -->", comment["body"])
        (labels,) = self.posted(transport, f"/repos/{REPO}/issues/101/labels")
        self.assertEqual(["maintainer", "risk:low", "self-check:passed"], labels["labels"])
        self.assertEqual([{"assignees": ["owner"]}], self.posted(transport, f"/repos/{REPO}/issues/101/assignees"))
        self.assertEqual([["pr", "edit", "101", "--repo", REPO, "--add-reviewer", "@copilot"]], self.gh_calls)
        self.assertEqual([], self.posted(transport, f"/repos/{REPO}/actions/workflows/ci.yml/dispatches"))
        self.assertEqual("opened", out["published"][0]["action"])

    def test_the_model_cannot_mention_link_or_close_through_the_body_or_title(self):
        self.branch("maint/fix-y", {"README.md": "y\n"})
        evil = "Fixes #4 cc @owner\n```\n<img src=x onerror=alert(1)> [click](https://evil.example/?t=1)"
        _, transport = self.publish([description("maint/fix-y", body=evil, title="Fix for @team")])
        (pr,) = self.posted(transport, f"/repos/{REPO}/pulls")
        fence = pr["body"].split("```text\n", 1)[1]
        self.assertEqual(1, fence.count("```"))   # only the closing fence: the body's own ``` was neutralised
        for raw in ("#4", "@owner", "<img", "?t=1"):
            self.assertNotIn(raw, pr["body"])
        self.assertEqual("Fix for @\u200bteam", pr["title"])

    def test_files_off_the_low_risk_list_become_a_draft(self):
        self.branch("maint/code", {"dashboard/backend/app/x.py": "x = 2\n",
                                   "dashboard/backend/tests/test_new.py": "pass\n"})
        out, transport = self.publish([description("maint/code")])
        (pr,) = self.posted(transport, f"/repos/{REPO}/pulls")
        self.assertTrue(pr["draft"])
        # The new test file is fine; the app file isn't on the list
        self.assertEqual(["dashboard/backend/app/x.py"], out["published"][0]["risky_files"])

    def test_a_new_test_file_alone_is_low_risk(self):
        self.branch("maint/test", {"dashboard/backend/tests/test_new.py": "pass\n"})
        out, transport = self.publish([description("maint/test")])
        (pr,) = self.posted(transport, f"/repos/{REPO}/pulls")
        self.assertFalse(pr["draft"])
        self.assertEqual([], out["published"][0]["risky_files"])

    def test_the_push_token_goes_in_gits_environment_not_its_command_line(self):
        ((key, value),) = mp.push_config("tok")
        self.assertEqual("http.https://github.com/.extraheader", key)
        self.assertEqual("AUTHORIZATION: basic eC1hY2Nlc3MtdG9rZW46dG9r", value)   # x-access-token:tok
        self.assertEqual([], mp.push_config(""))
        self.assertEqual(value, mp.run_git(["config", "--get", key], cwd=self.publisher, config=[(key, value)]).strip())
        # Not stored in the checkout
        with self.assertRaises(mp.GitError):
            mp.run_git(["config", "--get", key], cwd=self.publisher)

    def test_risky_paths_become_a_draft_labelled_needs_review(self):
        self.branch("maint/deploy-fix", {"deploy.sh": "#!/bin/sh\n", "home/index.php": "<?php\n"})
        out, transport = self.publish([description("maint/deploy-fix", risk="low")])
        (pr,) = self.posted(transport, f"/repos/{REPO}/pulls")
        self.assertTrue(pr["draft"])
        (labels,) = self.posted(transport, f"/repos/{REPO}/issues/101/labels")
        self.assertEqual(["maintainer", "risk:high", "self-check:passed", "needs-review"], labels["labels"])
        self.assertEqual("opened as a draft", out["published"][0]["action"])
        self.assertEqual(["deploy.sh", "home/index.php"], sorted(out["published"][0]["risky_files"]))

    def test_changes_to_ci_or_the_automation_are_refused(self):
        for name, path in (("maint/ci", ".github/workflows/ci.yml"), ("maint/claude", ".claude/settings.json")):
            git(self.claude, "switch", "-q", "main")
            self.branch(name, {path: "x\n", "README.md": "y\n"})
        out, transport = self.publish([description("maint/ci"), description("maint/claude")])
        self.assertEqual({"maint/ci", "maint/claude"}, {r["branch"] for r in out["refused"]})
        self.assertTrue(all("only a person may change" in r["reason"] for r in out["refused"]))
        self.assertIsNone(self.remote("maint/ci"))
        self.assertEqual([], [c for c in transport.calls if c["method"] == "POST"])

    def test_names_git_would_quote_are_refused(self):
        # Built with plumbing in a separate index, so the names never touch the file system (Windows forbids " and
        # a backslash in names).
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(self.tmp.name, "odd.index")}

        def plumb(*args, stdin=None):
            # protectNTFS off: Git for Windows otherwise refuses these names even in the index.
            return subprocess.run(["git", *IDENTITY, "-c", "core.protectNTFS=false", *args], cwd=self.claude,
                                  env=env, input=stdin, check=True, capture_output=True, text=True).stdout.strip()

        blob = plumb("hash-object", "-w", "--stdin", stdin="<?php\n")
        for branch, name in (("maint/quote", 'home/a".php'), ("maint/backslash", "home/b\\c.php"),
                             ("maint/tab", "docs/tab\tname.md")):
            plumb("read-tree", "origin/main")
            plumb("update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
            commit = plumb("commit-tree", plumb("write-tree"), "-p", "origin/main", "-m", branch)
            plumb("update-ref", f"refs/heads/{branch}", commit)
        out, _ = self.publish([description(b) for b in ("maint/quote", "maint/backslash", "maint/tab")])
        self.assertEqual({"maint/quote", "maint/backslash", "maint/tab"}, {r["branch"] for r in out["refused"]})
        self.assertTrue(all("quotes, backslashes or control characters" in r["reason"] for r in out["refused"]))
        self.assertIsNone(self.remote("maint/quote"))

    def test_size_limits(self):
        self.branch("maint/many-files", {f"docs/f{i}.md": "x\n" for i in range(4)})
        git(self.claude, "switch", "-q", "main")
        self.branch("maint/many-lines", {"docs/long.md": "x\n" * 50})
        out, _ = self.publish([description("maint/many-files"), description("maint/many-lines")],
                              MAX_FILES="3", MAX_LINES="40")
        reasons = {r["branch"]: r["reason"] for r in out["refused"]}
        self.assertEqual("changes 4 files (at most 3)", reasons["maint/many-files"])
        self.assertEqual("changes 50 lines (at most 40)", reasons["maint/many-lines"])
        self.assertIsNone(self.remote("maint/many-files"))

    def test_binary_files_and_symlinks_are_refused(self):
        git(self.claude, "switch", "-q", "-c", "maint/binary", "origin/main")
        with open(os.path.join(self.claude, "blob.bin"), "wb") as f:
            f.write(b"\x00\x01\x02binary")
        git(self.claude, "add", "-A")
        git(self.claude, "commit", "-qm", "binary")
        # A symlink, made through the index so the test also runs where the file system has none.
        git(self.claude, "switch", "-q", "-c", "maint/link", "origin/main")
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.claude, input="/etc/passwd",
                              capture_output=True, text=True, check=True).stdout.strip()
        git(self.claude, "update-index", "--add", "--cacheinfo", f"120000,{blob},link")
        git(self.claude, "commit", "-qm", "link")
        out, _ = self.publish([description("maint/binary"), description("maint/link")])
        reasons = {r["branch"]: r["reason"] for r in out["refused"]}
        self.assertEqual("changes a binary file: blob.bin", reasons["maint/binary"])
        self.assertEqual("adds a symlink or submodule: link", reasons["maint/link"])

    def test_names_and_descriptions_must_match(self):
        self.branch("maint/Bad_Name", {"README.md": "a\n"})
        git(self.claude, "switch", "-q", "main")
        self.branch("maint/undescribed", {"README.md": "b\n"})
        out, _ = self.publish([description("maint/Bad_Name"), description("maint/not-committed"),
                               {**description("maint/x"), "branch": "main"}])
        reasons = {r["branch"]: r["reason"] for r in out["refused"]}
        self.assertEqual("the name isn't maint/<lowercase-words>", reasons["maint/Bad_Name"])
        self.assertEqual("no valid description of it in the report", reasons["maint/undescribed"])
        self.assertEqual("described in the report but not committed", reasons["maint/not-committed"])
        self.assertEqual(2, len(out["errors"]))   # the two invalid names in the report
        self.assertEqual([], out["published"])

    def test_bad_titles_and_bodies_are_errors(self):
        described, errors = mp.descriptions({"pull_requests": [
            {**description("maint/a"), "title": "x" * 121},
            {**description("maint/b"), "body": ""},
            {**description("maint/c"), "title": "Fix‮ it\nnow", "risk": "unknown", "audit": "yes"},
            "not an object"]})
        self.assertEqual(["maint/c"], list(described))
        self.assertEqual({"title": "Fix it now", "body": "## Summary\nA fix.", "risk": "low", "audit": "findings"},
                         described["maint/c"])
        self.assertEqual(3, len(errors))

    def test_an_existing_branch_is_only_fast_forwarded(self):
        first = self.branch("maint/fix", {"README.md": "one\n"})
        git(self.claude, "push", "-q", "origin", "maint/fix")
        # Claude adds a commit on top: a fast-forward, pushed, and the maintainer's open pull request updated.
        self.write("README.md", "two\n")
        git(self.claude, "commit", "-qam", "more")
        second = git(self.claude, "rev-parse", "HEAD").strip()
        mine = {"number": 80, "draft": False, "node_id": "PR_80", "html_url": "p80", "user": {"login": LOGIN},
                "head": {"ref": "maint/fix", "repo": {"full_name": REPO}}}
        out, transport = self.publish([description("maint/fix")], open_prs=[mine])
        self.assertEqual(second, self.remote("maint/fix"))
        self.assertEqual("updated", out["published"][0]["action"])
        self.assertEqual([], self.posted(transport, f"/repos/{REPO}/pulls"))
        self.assertEqual([{"labels": ["maintainer", "risk:low", "self-check:passed"]}],
                         self.posted(transport, f"/repos/{REPO}/issues/80/labels"))
        # A rewritten branch (not built on what GitHub has) is refused, never force-pushed.
        git(self.claude, "switch", "-q", "-C", "maint/fix", "origin/main")
        self.write("README.md", "other\n")
        git(self.claude, "commit", "-qam", "rewrite")
        out, _ = self.publish([description("maint/fix")], open_prs=[mine])
        self.assertIn("only fast-forwards", out["refused"][0]["reason"])
        self.assertEqual(second, self.remote("maint/fix"))
        self.assertNotEqual(first, second)

    def test_someone_elses_pull_request_is_left_alone(self):
        self.branch("maint/fix", {"README.md": "one\n"})
        theirs = {"number": 81, "user": {"login": "stranger"},
                  "head": {"ref": "maint/fix", "repo": {"full_name": REPO}}}
        out, _ = self.publish([description("maint/fix")], open_prs=[theirs])
        self.assertIn("isn't the maintainer's (#81)", out["refused"][0]["reason"])
        self.assertIsNone(self.remote("maint/fix"))

    def test_an_unchanged_branch_is_skipped_quietly(self):
        self.branch("maint/old", {"README.md": "one\n"})
        git(self.claude, "push", "-q", "origin", "maint/old")
        out, transport = self.publish([])
        self.assertEqual({"published": [], "refused": [], "errors": []}, out)
        self.assertEqual([], [c for c in transport.calls if c["method"] != "GET"])

    def test_the_limit_and_dry_run(self):
        for name in ("maint/a", "maint/b"):
            git(self.claude, "switch", "-q", "main")
            self.branch(name, {"README.md": f"{name}\n"})
        out, transport = self.publish([description("maint/a"), description("maint/b")], MAX_PRS="1",
                                      DRY_RUN="true")
        self.assertEqual(["maint/a"], [p["branch"] for p in out["published"]])
        self.assertEqual("would push (dry run)", out["published"][0]["action"])
        self.assertEqual("over this run's limit of 1 pull requests", out["refused"][0]["reason"])
        self.assertIsNone(self.remote("maint/a"))
        self.assertEqual([], [c for c in transport.calls if c["method"] != "GET"])

    def test_workflow_token_mode_starts_ci(self):
        self.branch("maint/fix", {"README.md": "one\n"})
        _, transport = self.publish([description("maint/fix")], TOKEN_MODE="github_token")
        self.assertEqual([{"ref": "maint/fix"}],
                         self.posted(transport, f"/repos/{REPO}/actions/workflows/ci.yml/dispatches"))

    def test_no_bundle_publishes_nothing(self):
        out = mp.publish({"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t", "CLAUDE_RESULT": "not json",
                          "BUNDLE": os.path.join(self.tmp.name, "missing.bundle")}, FakeTransport({}),
                         functools.partial(mp.run_git, cwd=self.publisher), lambda args: True)
        self.assertEqual({"published": [], "refused": [], "errors": []}, out)


if __name__ == "__main__":
    unittest.main()
