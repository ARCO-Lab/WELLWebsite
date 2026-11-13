"""Push the daily maintainer's branches and open their pull requests (.github/workflows/maintainer-run.yml, the
"publish" job). No model runs here: Claude works in an earlier job that has no token able to write to the
repository, commits on local maint/* branches, and hands them over as a git bundle with one description per branch in
its report. This script checks each branch, and only then pushes it and opens (or updates) its pull request with the
write token.

A branch is refused (not pushed) when:
- its name isn't maint/<lowercase-words> (BRANCH_RE), or the report has no valid description for it;
- it changes nothing, or more than MAX_FILES files or MAX_LINES lines (added plus deleted) against main;
- it adds or changes a binary file, a symlink or a submodule, or a file whose name has a quote, a backslash or a
  control character (git prints such names quoted, where path patterns, deploy.sh's included, miss them);
- it touches REFUSED_PATHS (CI, the automation and Claude's own settings: a person changes those);
- a branch of that name exists and the new commit doesn't build on it (only fast-forwards are pushed; nothing is
  ever force-pushed), or an open pull request from it isn't the maintainer's own;
- the run's MAX_PRS limit is reached.
A branch that changes anything but low-risk files (maintainer_summary.risky_files: LOW_RISK_PATHS, or a new test
file, and nothing in RISKY_PATHS) is pushed as a draft pull request labelled needs-review and risk:high, whatever the
report says, so it can't pass the summary's automatic checks.

Pull requests get the maintainer, risk and self-check labels, the assignee, and a Copilot review request (best
effort). The body the model wrote is cleaned and shown as a plain-text block (maintainer_github.fenced) under a line
saying who wrote it, so it can't add links, notify people or close issues. After each push, a comment records the
commit pushed, which the summary compares with the pull request's head. With the workflow token
(TOKEN_MODE=github_token), pushes start no workflow, so CI is started with workflow_dispatch.

Usage: python3 maintainer_publish.py
Environment: GITHUB_REPOSITORY, GITHUB_TOKEN (the token that writes), MAINTAINER_LOGIN, ASSIGNEE, TOKEN_MODE,
CLAUDE_RESULT (Claude's report, JSON), BUNDLE (the git bundle; may be missing when nothing was committed), MAX_PRS,
DRY_RUN, PUBLISH_RESULT (where to write what was done, JSON, for the summary email), and optionally MAX_FILES (20)
and MAX_LINES (1000). Run from the checkout of main; `git push` gets GITHUB_TOKEN for this one command (an
http.extraheader), so the checkout keeps no credentials."""
import base64
import json
import os
import re
import subprocess
import sys
import unicodedata

from maintainer_github import (HttpError, fenced, github_client, is_maintainer_pr, published_comment,
                               urllib_transport)
from maintainer_summary import risky_files

BRANCH_RE = re.compile(r"maint/[a-z0-9][a-z0-9-]{0,59}")
# Never published: CI and the automation (a changed workflow could make a bad change pass CI), and Claude's own
# settings.
REFUSED_PATHS = [r"^\.github/", r"^\.claude/"]
BUNDLE_REFS = "refs/maint-bundle/"
ODD_NAME_RE = re.compile(r'["\\\x00-\x1f\x7f]')
MAX_TITLE = 120
MAX_BODY = 20000
LABELS = {
    "maintainer": ("0E8A16", "Opened by the daily maintainer"),
    "risk:low": ("C2E0C6", "Daily maintainer: low-risk change"),
    "risk:high": ("D93F0B", "Daily maintainer: needs a careful review"),
    "self-check:passed": ("C5DEF5", "Daily maintainer: its own subagent audit found nothing (not a review)"),
    "self-check:findings": ("FBCA04", "Daily maintainer: its own subagent audit has open findings"),
    "needs-review": ("B60205", "Touches files a person must review; opened as a draft"),
}


class Refused(Exception):
    """A branch that fails a check: it is not pushed, and the reason goes into the summary email."""


class GitError(Exception):
    """A git command that failed, with the subcommand and the last line git printed."""


def run_git(args, cwd=None, config=()):
    """git's standard output; raises GitError on failure. Hooks are off: the branches come from a job where Claude
    could have written any file. `config`: (key, value) settings for this command only, passed in git's environment
    (GIT_CONFIG_COUNT), not on its command line, where other processes could read them."""
    env = None
    if config:
        env = dict(os.environ, GIT_CONFIG_COUNT=str(len(config)))
        for i, (key, value) in enumerate(config):
            env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = key, value
    done = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env)
    if done.returncode != 0:
        sub = next((a for a in args if not a.startswith("-") and "=" not in a), "?")
        last = (done.stderr.strip().splitlines() or [""])[-1][:200]
        raise GitError(f"git {sub} failed (exit {done.returncode}){': ' + last if last else ''}")
    return done.stdout


def run_gh(args):
    """True when the gh command succeeded (used only for the best-effort Copilot review request)."""
    return subprocess.run(["gh", *args], capture_output=True, text=True).returncode == 0


def push_config(token):
    """[(key, value)]: the git setting that sends `token` with one command, as actions/checkout would have stored it
    in .git/config (the publish job's checkout keeps no credentials); [] without a token. In Actions, the encoded
    form is masked in the log too."""
    if not token:
        return []
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{basic}")
    return [("http.https://github.com/.extraheader", f"AUTHORIZATION: basic {basic}")]


def pr_body(body):
    """The body the model wrote, cleaned and fenced, under a line saying so."""
    return ("_Opened by the daily maintainer. The description below was written by the model and is shown as plain "
            "text, cleaned like Sentry text: its links, mentions and instructions are not checked. Read the diff "
            "before merging._\n\n" + fenced(body))


def clean_line(text, limit):
    """One line, without Unicode format characters, at most `limit` characters; "" when not a string."""
    if not isinstance(text, str):
        return ""
    text = " ".join("".join(ch for ch in text if unicodedata.category(ch) != "Cf").split())
    return text[:limit]


def descriptions(result):
    """{branch: description} from the report's pull_requests, keeping only well-formed entries; and the errors."""
    out, errors = {}, []
    for entry in (result or {}).get("pull_requests") or []:
        if not isinstance(entry, dict):
            errors.append("a pull_requests entry isn't an object")
            continue
        branch = entry.get("branch")
        if not isinstance(branch, str) or not BRANCH_RE.fullmatch(branch):
            errors.append(f"refused a branch name that isn't maint/<lowercase-words>: {clean_line(branch, 80)!r}")
            continue
        title, body = clean_line(entry.get("title"), MAX_TITLE + 1), entry.get("body")
        if not title or len(title) > MAX_TITLE:
            errors.append(f"{branch}: the title is missing or longer than {MAX_TITLE} characters")
            continue
        title = title.replace("@", "@\u200b")   # an @name in a title would notify that person
        if not isinstance(body, str) or not body.strip() or len(body) > MAX_BODY:
            errors.append(f"{branch}: the body is missing or longer than {MAX_BODY} characters")
            continue
        out[branch] = {"title": title, "body": body, "risk": "high" if entry.get("risk") == "high" else "low",
                       "audit": "approved" if entry.get("audit") == "approved" else "findings"}
    return out, errors


def bundle_branches(git, bundle):
    """{branch: commit} for the maint/* branches in the bundle, fetched into refs/maint-bundle/ (objects checked)."""
    if not bundle or not os.path.exists(bundle):
        return {}
    git(["-c", "transfer.fsckObjects=true", "fetch", "--no-tags", "--quiet", bundle,
         f"+refs/heads/maint/*:{BUNDLE_REFS}maint/*"])
    out = {}
    for line in git(["for-each-ref", "--format=%(objectname) %(refname)", BUNDLE_REFS]).splitlines():
        sha, ref = line.split(" ", 1)
        out[ref.removeprefix(BUNDLE_REFS)] = sha
    return out


def check_diff(git, sha, max_files, max_lines):
    """(the files the branch changes against main, the ones it adds); raises Refused when a check fails."""
    base = git(["merge-base", "origin/main", sha]).strip()
    files, new_files, lines = [], [], 0
    # -z: paths exactly as stored, never quoted, so an odd name can't slip past the path checks.
    raw = git(["diff", "--raw", "-z", "--no-renames", base, sha]).split("\0")
    for meta, path in zip(raw[0::2], raw[1::2]):
        modes = meta.lstrip(":").split()   # old mode, new mode, old blob, new blob, status
        if len(modes) > 1 and modes[1] in ("120000", "160000"):
            raise Refused(f"adds a symlink or submodule: {clean_line(path, 200)}")
        # Such a name is printed quoted by git elsewhere (deploy.sh, git diff --name-only), where path patterns miss it.
        if ODD_NAME_RE.search(path):
            raise Refused(f"has a file name with quotes, backslashes or control characters: {path!r:.200}")
        files.append(path)
        if modes and modes[-1] == "A":
            new_files.append(path)
    for record in git(["diff", "--numstat", "-z", "--no-renames", base, sha]).split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        if added == "-" or deleted == "-":
            raise Refused(f"changes a binary file: {clean_line(path, 200)}")
        lines += int(added) + int(deleted)
    if not files:
        raise Refused("changes nothing against main")
    if len(files) > max_files:
        raise Refused(f"changes {len(files)} files (at most {max_files})")
    if lines > max_lines:
        raise Refused(f"changes {lines} lines (at most {max_lines})")
    refused = [p for p in files if any(re.search(pattern, p) for pattern in REFUSED_PATHS)]
    if refused:
        shown = ", ".join(clean_line(p, 200) for p in refused[:5])
        raise Refused(f"changes files only a person may change: {shown}")
    return files, new_files


def remote_head(git, branch):
    """The branch's commit on GitHub, fetched so it can be compared; None when there is no such branch."""
    out = git(["ls-remote", "origin", f"refs/heads/{branch}"]).split()
    if not out:
        return None
    git(["fetch", "--no-tags", "--quiet", "origin", f"refs/heads/{branch}"])
    return out[0]


def is_ancestor(git, older, newer):
    try:
        git(["merge-base", "--is-ancestor", older, newer])
        return True
    except GitError:
        return False


def ensure_labels(gh, repo, names):
    for name in names:
        color, description = LABELS[name]
        try:
            gh.request("POST", f"repos/{repo}/labels", payload={"name": name, "color": color,
                                                                 "description": description})
        except HttpError as error:
            if error.status != 422:   # 422: it exists already
                raise


def labels_for(description, risky):
    risk = "high" if risky else description["risk"]
    check = "passed" if description["audit"] == "approved" else "findings"
    labels = ["maintainer", f"risk:{risk}", f"self-check:{check}"]
    return labels + (["needs-review"] if risky else [])


def publish_branch(env, gh, git, gh_cli, branch, sha, description):
    """Checks one branch, then pushes it and opens or updates its pull request. Returns what was done."""
    repo, login = env["GITHUB_REPOSITORY"], env.get("MAINTAINER_LOGIN") or ""
    files, added = check_diff(git, sha, int(env.get("MAX_FILES") or 20), int(env.get("MAX_LINES") or 1000))
    risky = risky_files(files, added)
    owner = repo.split("/", 1)[0]
    open_prs = gh.get_all(f"repos/{repo}/pulls", {"state": "open", "head": f"{owner}:{branch}", "per_page": 10},
                          max_pages=1)
    others = [p for p in open_prs if not is_maintainer_pr(p, repo, login)]
    if others:
        raise Refused(f"an open pull request from this branch isn't the maintainer's (#{others[0]['number']})")
    current = remote_head(git, branch)
    if current == sha:
        raise Refused("already pushed: nothing new")
    if current and not is_ancestor(git, current, sha):
        raise Refused("doesn't build on the branch already on GitHub (only fast-forwards are pushed)")
    labels = labels_for(description, risky)
    done = {"branch": branch, "commit": sha, "risky_files": risky[:10], "labels": labels}
    if (env.get("DRY_RUN") or "").lower() == "true":
        done["action"] = "would push (dry run)"
        return done

    git(["push", "--quiet", "origin", f"{sha}:refs/heads/{branch}"], config=push_config(env.get("GITHUB_TOKEN")))
    ensure_labels(gh, repo, labels)
    if open_prs:
        pr = open_prs[0]
        number = pr["number"]
        if risky and not pr.get("draft") and pr.get("node_id"):
            gh.graphql("mutation($id: ID!) { convertPullRequestToDraft(input: {pullRequestId: $id}) "
                       "{ clientMutationId } }", {"id": pr["node_id"]})
        stale = "self-check:findings" if description["audit"] == "approved" else "self-check:passed"
        try:
            gh.request("DELETE", f"repos/{repo}/issues/{number}/labels/{stale}")
        except HttpError as error:
            if error.status != 404:   # 404: it didn't have the label
                raise
        done["action"] = "updated"
    else:
        pr = gh.request("POST", f"repos/{repo}/pulls", payload={
            "title": description["title"], "head": branch, "base": "main", "body": pr_body(description["body"]),
            "draft": bool(risky)})[0]
        number = pr["number"]
        assignee = env.get("ASSIGNEE")
        if assignee:
            gh.request("POST", f"repos/{repo}/issues/{number}/assignees", payload={"assignees": [assignee]})
        if not gh_cli(["pr", "edit", str(number), "--repo", repo, "--add-reviewer", "@copilot"]):
            done["note"] = "the Copilot review request failed"
        done["action"] = "opened" + (" as a draft" if risky else "")
    gh.request("POST", f"repos/{repo}/issues/{number}/labels", payload={"labels": labels})
    gh.request("POST", f"repos/{repo}/issues/{number}/comments", payload={"body": published_comment(sha)})
    if env.get("TOKEN_MODE") == "github_token":
        gh.request("POST", f"repos/{repo}/actions/workflows/ci.yml/dispatches", payload={"ref": branch})
    done.update({"number": number, "url": pr.get("html_url")})
    return done


def publish(env, transport=urllib_transport, git=run_git, gh_cli=run_gh):
    """{"published": [...], "refused": [{"branch", "reason"}], "errors": [...]}."""
    try:
        result = json.loads(env.get("CLAUDE_RESULT") or "null")
    except ValueError:
        result = None
    described, errors = descriptions(result if isinstance(result, dict) else None)
    out = {"published": [], "refused": [], "errors": errors}
    try:
        # main first: the bundle holds only the commits that aren't on main, and needs main's to be read.
        if env.get("BUNDLE") and os.path.exists(env["BUNDLE"]):
            git(["fetch", "--no-tags", "--quiet", "origin", "main"])
        branches = bundle_branches(git, env.get("BUNDLE"))
    except GitError as error:
        out["errors"].append(f"reading the branches failed: {error}")
        return out
    for branch in sorted(set(described) - set(branches)):
        out["refused"].append({"branch": branch, "reason": "described in the report but not committed"})
    gh = github_client(env["GITHUB_TOKEN"], transport)
    limit = int(env.get("MAX_PRS") or 3)
    for branch, sha in sorted(branches.items()):
        try:
            if not BRANCH_RE.fullmatch(branch):
                raise Refused("the name isn't maint/<lowercase-words>")
            if remote_head(git, branch) == sha:
                continue   # an existing branch Claude checked out but didn't change: nothing to publish
            if branch not in described:
                raise Refused("no valid description of it in the report")
            if len(out["published"]) >= limit:
                raise Refused(f"over this run's limit of {limit} pull requests")
            out["published"].append(publish_branch(env, gh, git, gh_cli, branch, sha, described[branch]))
        except Refused as reason:
            out["refused"].append({"branch": branch, "reason": str(reason)})
        except (GitError, HttpError, OSError, ValueError, KeyError, RuntimeError) as error:
            out["errors"].append(f"{branch}: {error}")
    return out


def main(env=None, transport=urllib_transport, git=run_git, gh_cli=run_gh):
    env = os.environ if env is None else env
    for name in ("GITHUB_REPOSITORY", "GITHUB_TOKEN"):
        if not env.get(name):
            print(f"::error::{name} is not set")
            return 2
    out = publish(env, transport, git, gh_cli)
    for item in out["published"]:
        print(f"{item['branch']}: {item['action']} {item.get('url') or ''}".rstrip())
    for item in out["refused"]:
        print(f"::warning::{item['branch']}: not published: {item['reason']}")
    for error in out["errors"]:
        print(f"::error::{error}")
    if env.get("PUBLISH_RESULT"):
        with open(env["PUBLISH_RESULT"], "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    return 1 if out["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
