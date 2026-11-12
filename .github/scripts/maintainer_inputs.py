"""Collect what the daily maintainer should look at into one JSON file, before Claude starts
(.github/workflows/daily-maintainer.yml). Doing it here keeps the Sentry token out of Claude's environment, and
gives Claude the same facts each run instead of leaving it to search for them.

Collected (each part on its own: one that fails is recorded under "errors" and the rest still run):
- open issues labelled `sentry`, opened by a bot or a repository member;
- unresolved Sentry issues seen in the last 24 hours, with the latest event's exception and in-app frames
  (only when SENTRY_API_TOKEN is set);
- failed workflow runs on main in the last 24 hours, with their failed jobs and steps (the API canary, the load
  test and this maintainer are left out: the canary reports vendor outages, not code problems);
- unresolved github-code-quality[bot] review threads on open pull requests;
- open code scanning and Dependabot alerts, when ALERTS_TOKEN can read them;
- the maintainer's own open pull requests and maint/* branches, so the same problem isn't fixed twice.

Usage: python3 maintainer_inputs.py OUTPUT.json
Environment: GITHUB_REPOSITORY, GITHUB_TOKEN (read-only is enough), MAINTAINER_LOGIN, ALERTS_TOKEN (optional),
SENTRY_API_TOKEN
(optional), SENTRY_ORG (default well-cs), SENTRY_API_URL (default https://sentry.io)."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from maintainer_github import Client, HttpError, clip, github_client, urllib_transport

SKIPPED_WORKFLOWS = {".github/workflows/canary.yml", ".github/workflows/load-test.yml",
                     ".github/workflows/daily-maintainer.yml"}
FAILED = {"failure", "timed_out", "startup_failure"}
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
CODE_QUALITY_BOT = "github-code-quality"

THREADS_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number title url headRefName author { login }
        reviewThreads(first: 100) {
          nodes { isResolved isOutdated path line comments(first: 1) { nodes { author { login } body url } } }
        }
      }
    }
  }
}"""


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def sentry_github_issues(gh, repo):
    issues = gh.get_all(f"repos/{repo}/issues", {"labels": "sentry", "state": "open", "per_page": 50}, max_pages=2)
    out = []
    for issue in issues:
        user = issue.get("user") or {}
        if "pull_request" in issue:
            continue
        # Anyone can open an issue on a public repository; only bots (the sentry-issues workflow) and members count.
        if user.get("type") != "Bot" and issue.get("author_association") not in TRUSTED_ASSOCIATIONS:
            continue
        out.append({"number": issue["number"], "title": issue.get("title", ""), "url": issue.get("html_url"),
                    "updated_at": issue.get("updated_at"), "body": clip(issue.get("body"), 3000)})
    return out


def latest_exception(sentry, org, issue_id):
    """The latest event's exception types, values and last in-app frames, or None."""
    event = sentry.get(f"api/0/organizations/{org}/issues/{issue_id}/events/latest/")
    for entry in (event or {}).get("entries") or []:
        if entry.get("type") != "exception":
            continue
        values = []
        for value in (entry.get("data") or {}).get("values") or []:
            frames = ((value.get("stacktrace") or {}).get("frames")) or []
            in_app = [f for f in frames if f.get("inApp")] or frames
            values.append({"type": value.get("type"), "value": clip(value.get("value"), 500),
                           "frames": [{"file": f.get("filename"), "line": f.get("lineNo"),
                                       "function": f.get("function")} for f in in_app[-10:]]})
        return values
    return None


def sentry_issues(sentry, org, max_detailed=5):
    issues = sentry.get(f"api/0/organizations/{org}/issues/",
                        {"query": "is:unresolved lastSeen:-24h", "statsPeriod": "24h", "limit": 25})
    out = []
    for i, issue in enumerate(issues or []):
        item = {"id": issue.get("id"), "short_id": issue.get("shortId"), "title": clip(issue.get("title"), 300),
                "culprit": clip(issue.get("culprit"), 300), "level": issue.get("level"),
                "project": (issue.get("project") or {}).get("slug"), "count": issue.get("count"),
                "first_seen": issue.get("firstSeen"), "last_seen": issue.get("lastSeen"),
                "url": issue.get("permalink")}
        if i < max_detailed:
            try:
                item["exception"] = latest_exception(sentry, org, issue.get("id"))
            except (HttpError, OSError, ValueError) as error:
                item["exception_error"] = str(error)
        out.append(item)
    return out


def failed_runs(gh, repo, since, max_runs=10):
    runs = gh.get_all(f"repos/{repo}/actions/runs", {"branch": "main", "created": f">={iso(since)}",
                                                     "per_page": 100}, max_pages=3, key="workflow_runs")
    out = []
    for run in runs:
        if run.get("conclusion") not in FAILED or run.get("path") in SKIPPED_WORKFLOWS:
            continue
        if len(out) >= max_runs:
            break
        item = {"id": run["id"], "workflow": run.get("name"), "path": run.get("path"), "event": run.get("event"),
                "conclusion": run.get("conclusion"), "head_sha": run.get("head_sha"), "url": run.get("html_url"),
                "created_at": run.get("created_at"), "failed_jobs": []}
        jobs = gh.get_all(f"repos/{repo}/actions/runs/{run['id']}/jobs", {"per_page": 100}, max_pages=1, key="jobs")
        for job in jobs:
            if job.get("conclusion") in FAILED:
                item["failed_jobs"].append({
                    "name": job.get("name"), "url": job.get("html_url"),
                    "failed_steps": [s.get("name") for s in job.get("steps") or [] if s.get("conclusion") in FAILED]})
        out.append(item)
    return out


def code_quality_threads(gh, repo):
    owner, name = repo.split("/", 1)
    data = gh.graphql(THREADS_QUERY, {"owner": owner, "name": name})
    out = []
    for pr in ((data.get("repository") or {}).get("pullRequests") or {}).get("nodes") or []:
        for thread in (pr.get("reviewThreads") or {}).get("nodes") or []:
            comments = (thread.get("comments") or {}).get("nodes") or []
            if thread.get("isResolved") or not comments:
                continue
            login = ((comments[0].get("author") or {}).get("login") or "").removesuffix("[bot]")
            if login != CODE_QUALITY_BOT:
                continue
            out.append({"pr": pr["number"], "pr_title": pr.get("title"), "pr_url": pr.get("url"),
                        "branch": pr.get("headRefName"), "pr_author": (pr.get("author") or {}).get("login"),
                        "path": thread.get("path"), "line": thread.get("line"), "outdated": thread.get("isOutdated"),
                        "body": clip(comments[0].get("body"), 1500), "url": comments[0].get("url")})
    return out


def code_scanning_alerts(gh, repo):
    alerts = gh.get_all(f"repos/{repo}/code-scanning/alerts", {"state": "open", "per_page": 100}, max_pages=2)
    return [{"number": a.get("number"), "rule": (a.get("rule") or {}).get("id"),
             "severity": (a.get("rule") or {}).get("security_severity_level") or (a.get("rule") or {}).get("severity"),
             "description": clip((a.get("rule") or {}).get("description"), 300),
             "path": ((a.get("most_recent_instance") or {}).get("location") or {}).get("path"),
             "line": ((a.get("most_recent_instance") or {}).get("location") or {}).get("start_line"),
             "url": a.get("html_url")} for a in alerts]


def dependabot_alerts(gh, repo):
    alerts = gh.get_all(f"repos/{repo}/dependabot/alerts", {"state": "open", "per_page": 100}, max_pages=2)
    out = []
    for a in alerts:
        dependency, advisory = a.get("dependency") or {}, a.get("security_advisory") or {}
        vulnerability = a.get("security_vulnerability") or {}
        out.append({"number": a.get("number"), "package": (dependency.get("package") or {}).get("name"),
                    "ecosystem": (dependency.get("package") or {}).get("ecosystem"),
                    "manifest": dependency.get("manifest_path"), "severity": advisory.get("severity"),
                    "summary": clip(advisory.get("summary"), 300),
                    "patched": (vulnerability.get("first_patched_version") or {}).get("identifier"),
                    "url": a.get("html_url")})
    return out


def maintainer_work(gh, repo, login):
    """The maintainer's own open pull requests (opened by its account from a branch of this repository), and the
    maint/* branches. Pull requests by anyone else are left out, so a stranger's one can't pose as its work."""
    prs = gh.get_all(f"repos/{repo}/pulls", {"state": "open", "per_page": 100}, max_pages=3)
    open_prs = [{"number": p["number"], "title": p.get("title"), "branch": (p.get("head") or {}).get("ref"),
                 "url": p.get("html_url"), "labels": [label.get("name") for label in p.get("labels") or []]}
                for p in prs
                if login and (p.get("user") or {}).get("login") == login
                and ((p.get("head") or {}).get("repo") or {}).get("full_name") == repo]
    refs = gh.get(f"repos/{repo}/git/matching-refs/heads/maint/") or []
    return {"open_prs": open_prs, "branches": [r["ref"].removeprefix("refs/heads/") for r in refs]}


def collect(env, transport=urllib_transport, now=None):
    now = now or datetime.now(timezone.utc)
    repo = env["GITHUB_REPOSITORY"]
    gh = github_client(env["GITHUB_TOKEN"], transport)
    result = {"repository": repo, "generated_at": iso(now), "since": iso(now - timedelta(hours=24)), "errors": []}

    def part(name, fn, *args):
        try:
            result[name] = fn(*args)
        except (HttpError, RuntimeError, OSError, ValueError, KeyError) as error:
            result[name] = None
            result["errors"].append(f"{name}: {error}")

    part("sentry_github_issues", sentry_github_issues, gh, repo)
    if env.get("SENTRY_API_TOKEN"):
        sentry = Client(env.get("SENTRY_API_URL") or "https://sentry.io", env["SENTRY_API_TOKEN"], transport)
        part("sentry_issues", sentry_issues, sentry, env.get("SENTRY_ORG") or "well-cs")
    else:
        result["sentry_issues"] = None
        result["notes"] = ["SENTRY_API_TOKEN is not set, so Sentry itself was not queried"]
    part("failed_runs_on_main", failed_runs, gh, repo, now - timedelta(hours=24))
    part("code_quality_threads", code_quality_threads, gh, repo)
    alerts = github_client(env.get("ALERTS_TOKEN") or env["GITHUB_TOKEN"], transport)
    for name, fn in (("code_scanning_alerts", code_scanning_alerts), ("dependabot_alerts", dependabot_alerts)):
        try:
            result[name] = fn(alerts, repo)
        except HttpError as error:
            # 403/404: the token can't read these alerts (or the feature is off). Not an error of the run.
            result[name] = None
            if error.status in (403, 404):
                result.setdefault("notes", []).append(f"{name}: not readable with this token ({error})")
            else:
                result["errors"].append(f"{name}: {error}")
        except (RuntimeError, OSError, ValueError) as error:
            result[name] = None
            result["errors"].append(f"{name}: {error}")
    part("maintainer_work", maintainer_work, gh, repo, env.get("MAINTAINER_LOGIN") or "")
    return result


def counts(result):
    """One log line of counts only: the details can hold error messages and stay out of the public log."""
    def n(key):
        value = result.get(key)
        return "-" if value is None else str(len(value))
    return (f"sentry issues on GitHub {n('sentry_github_issues')}, Sentry {n('sentry_issues')}, "
            f"failed runs {n('failed_runs_on_main')}, code-quality threads {n('code_quality_threads')}, "
            f"code scanning {n('code_scanning_alerts')}, Dependabot {n('dependabot_alerts')}, "
            f"errors {len(result['errors'])}")


def main(argv=None, env=None, transport=urllib_transport):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if len(argv) != 1:
        print("usage: maintainer_inputs.py OUTPUT.json", file=sys.stderr)
        return 2
    for name in ("GITHUB_REPOSITORY", "GITHUB_TOKEN"):
        if not env.get(name):
            print(f"::error::{name} is not set", file=sys.stderr)
            return 2
    result = collect(env, transport)
    with open(argv[0], "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(counts(result))
    for error in result["errors"]:
        print(f"::warning::{error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
