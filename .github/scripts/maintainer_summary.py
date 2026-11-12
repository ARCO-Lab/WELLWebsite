"""The daily maintainer's email (.github/workflows/daily-maintainer.yml): its open pull requests, sorted into
"Ready to merge" and "Needs your review", what this run did, and anything that went wrong. Sent every run, also
when there is nothing to report, so a missing email means the job itself didn't run.

A pull request is the maintainer's if it comes from a maint/* branch of the maintainer's account, or carries the
`maintainer` label. It is "Ready to merge" only when all of these hold; otherwise it "Needs your review", with the
reasons listed:
- it is the maintainer's own: from a maint/* branch of this repository, opened by the maintainer's account
  (with a personal token that is the owner's own account, so the branch is what tells them apart; a `maintainer`
  label alone, which anyone with triage rights can add, isn't enough);
- CI finished, every check passed, and the checks main requires (REQUIRED_CHECKS) are among them;
- it has the `audit:approved` label (set after an independent audit said "Approval recommended") and no
  `audit:findings` label;
- it has the `risk:low` label and not `risk:high`;
- none of its files match RISKY_PATHS (checked here too, whatever the labels say);
- it isn't a draft.

The email goes through SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM to ALERT_EMAILS, the same
settings and TLS rules as the backend's daily digest (dashboard/backend/app/scripts/daily_digest.py). Without
SMTP_HOST/SMTP_PORT the email is only printed. The text also goes to the job summary.

Environment: GITHUB_REPOSITORY, GITHUB_TOKEN (read-only), MAINTAINER_LOGIN, RUN_URL, CLAUDE_OUTCOME (the Claude
step's outcome), CLAUDE_RESULT (its structured output, JSON), INPUTS_FILE, PUBLISH_FILE (what maintainer_publish.py
pushed, opened and refused), MAIN_BEFORE and MAIN_AFTER (main's
commit before and after the run), TOKEN_MODE ("pat" or "github_token"), DRY_RUN, and the SMTP settings above."""
import json
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage

from maintainer_github import HttpError, clip, github_client, is_maintainer_pr, urllib_transport

# Changes a person must look at, whatever the audit said: data, schema, deploy, infrastructure, dependencies,
# security, the WordPress site, and the automation itself. PROMPT.md tells Claude to label these risk:high.
RISKY_PATHS = [
    r"^dashboard/backend/app/db/",                      # schema and migrations
    r"(^|/)migrate\.py$",
    r"(^|/)docker-compose[^/]*\.ya?ml$", r"(^|/)Dockerfile[^/]*$", r"(^|/)\.dockerignore$",
    r"^deploy\.sh$", r"^nginx\.conf$",
    r"(^|/)requirements[^/]*\.txt$", r"(^|/)package(-lock)?\.json$",
    r"^dashboard/backend/app/config\.py$",
    r"^dashboard/backend/app/server\.py$",               # the Flask app: routes, CORS, error handling
    r"^dashboard/backend/app/ops/",                      # the ops dashboard: login, password hashing, settings
    r"^dashboard/backend/app/tasks/",
    # ingestion, backfills, uploads and the scheduler
    r"^dashboard/backend/app/scripts/(inject|licor|wqdata|clean|clear|upload|download|sharepoint|scheduler)_",
    r"^dashboard/backend/app/utils/(parsers|fetching|borealis|sharepoint|sampling_\w+|sensor_names|timezone)\.py$",
    r"^dashboard/backend/app/utils/(sentry|guards)\.py$",   # error reporting and request guards
    r"^dashboard/frontend/src/lib/sentry\.ts$",
    r"^dashboard/frontend/src/pages/api/",              # the dashboard's server side: proxying to the backend
    r"(^|/)next\.config\.[^/]+$",
    r"(^|/)\.git(ignore|attributes)$",
    r"^\.github/",                                       # workflows, Dependabot, and this maintainer
    r"^\.claude/",
    r"^home/", r"^wordpress/",
]
# The checks main's branch protection requires: the job names in ci.yml, as in deploy.sh's REQUIRED_CHECKS
# (a unit test keeps the two the same).
REQUIRED_CHECKS = ["Backend image and tests", "Dashboard build", "Dashboard image", "Deploy script",
                   "End-to-end data (vendors to browser)"]
PASSED = {"success", "neutral", "skipped"}


def risky_files(paths):
    return [p for p in paths if any(re.search(pattern, p) for pattern in RISKY_PATHS)]


def latest_runs(check_runs):
    """The newest check run of each name (a re-run, or CI started by hand after a pull_request run)."""
    newest = {}
    for run in check_runs:
        name = run.get("name")
        if name not in newest or (run.get("id") or 0) > (newest[name].get("id") or 0):
            newest[name] = run
    return list(newest.values())


def ci_state(check_runs, required=REQUIRED_CHECKS):
    """(state, [missing required check names]) for a commit's check runs. The state is "green" (all finished and
    passed, every required check among them), "red", "pending", "missing" (passed, but a required check never
    ran) or "none"."""
    runs = latest_runs(check_runs)
    if not runs:
        return "none", list(required)
    if any(run.get("status") != "completed" for run in runs):
        return "pending", []
    if not all(run.get("conclusion") in PASSED for run in runs):
        return "red", []
    passed = {run.get("name") for run in runs if run.get("conclusion") == "success"}
    missing = [name for name in required if name not in passed]
    return ("missing", missing) if missing else ("green", [])


def classify(pr, files, ci, repo, login, failed_checks=(), missing_checks=()):
    """("ready", []) or ("review", [reasons])."""
    labels = {label.get("name") for label in pr.get("labels") or []}
    reasons = []
    if not is_maintainer_pr(pr, repo, login):
        reasons.append("not opened by the maintainer")
    if ci == "red":
        reasons.append("CI failed" + (f": {', '.join(failed_checks)}" if failed_checks else ""))
    elif ci == "pending":
        reasons.append("CI still running")
    elif ci == "none":
        reasons.append("no CI checks found")
    elif ci == "missing":
        reasons.append(f"required checks missing: {', '.join(missing_checks)}")
    if "risk:high" in labels:
        reasons.append("labelled risk:high")
    elif "risk:low" not in labels:
        reasons.append("no risk label")
    risky = risky_files(files)
    if risky:
        shown = ", ".join(risky[:5]) + (f" and {len(risky) - 5} more" if len(risky) > 5 else "")
        reasons.append(f"touches files that need a person: {shown}")
    if "audit:findings" in labels:
        reasons.append("the audit has open findings")
    elif "audit:approved" not in labels:
        reasons.append("not audited yet (no audit:approved label)")
    if pr.get("draft"):
        reasons.append("draft")
    return ("review", reasons) if reasons else ("ready", [])


def maintainer_prs(gh, repo, login):
    prs = gh.get_all(f"repos/{repo}/pulls", {"state": "open", "per_page": 100}, max_pages=3)
    # Labelled ones are listed too, so a stray `maintainer` label shows up, as "not opened by the maintainer".
    return [p for p in prs
            if is_maintainer_pr(p, repo, login)
            or any(label.get("name") == "maintainer" for label in p.get("labels") or [])]


def review_prs(gh, repo, prs, login):
    """[(pr, verdict, reasons)] with each pull request's files and checks looked up."""
    out = []
    for pr in prs:
        files = [f["filename"] for f in gh.get_all(f"repos/{repo}/pulls/{pr['number']}/files",
                                                   {"per_page": 100}, max_pages=30)]
        runs = latest_runs(gh.get_all(f"repos/{repo}/commits/{pr['head']['sha']}/check-runs",
                                      {"per_page": 100, "filter": "latest"}, max_pages=3, key="check_runs"))
        failed = sorted({r.get("name") for r in runs
                         if r.get("status") == "completed" and r.get("conclusion") not in PASSED})
        state, missing = ci_state(runs)
        verdict, reasons = classify(pr, files, state, repo, login, failed, missing)
        out.append((pr, verdict, reasons))
    return out


def direct_pushes(gh, repo, before, after, login):
    """Commits that reached main during the run committed by the maintainer's account itself rather than through
    GitHub's merge button (committer "web-flow"). The maintainer must never push to main, so any is an error."""
    if not before or not after or before == after:
        return []
    commits = (gh.get(f"repos/{repo}/compare/{before}...{after}") or {}).get("commits") or []
    return [c for c in commits if ((c.get("committer") or {}).get("login") == login)]


def parse_result(text):
    """Claude's structured output, or None when it is missing or isn't JSON."""
    if not text or not text.strip():
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def pr_line(pr, reasons=()):
    line = f"- #{pr['number']} {pr.get('title', '')}\n  {pr.get('html_url', '')}"
    if reasons:
        line += "\n  Why: " + "; ".join(reasons)
    return line


def build_email(reviewed, result, errors, run_url, dry_run=False, notes=()):
    """(subject, body)."""
    ready = [(pr, r) for pr, verdict, r in reviewed if verdict == "ready"]
    review = [(pr, r) for pr, verdict, r in reviewed if verdict == "review"]
    lines = []
    if dry_run:
        lines += ["This was a dry run: nothing was pushed or opened.", ""]
    lines.append(f"Ready to merge ({len(ready)}):")
    lines += [pr_line(pr) for pr, _ in ready] or ["- none"]
    lines += ["", f"Needs your review ({len(review)}):"]
    lines += [pr_line(pr, r) for pr, r in review] or ["- none"]
    lines += ["", "What this run did:"]
    if result is None:
        lines.append("- Claude gave no report (see the errors below and the run log).")
    else:
        lines.append(clip(str(result.get("summary") or "(no summary)"), 3000))
        for action in result.get("actions") or []:
            if isinstance(action, dict):
                url = f" {action['url']}" if action.get("url") else ""
                lines.append(f"- {clip(str(action.get('what', '')), 500)}{url}")
        for skipped in result.get("skipped") or []:
            lines.append(f"- Skipped: {clip(str(skipped), 500)}")
        errors = list(errors) + [f"Claude: {clip(str(e), 500)}" for e in result.get("errors") or []]
    if notes:
        lines += ["", "Notes:"] + [f"- {n}" for n in notes]
    lines += ["", "Errors:"] + ([f"- {e}" for e in errors] or ["- none"])
    lines += ["", "Nothing is ever merged by the maintainer; merging is yours.", f"Run: {run_url}"]

    if errors:
        headline = f"{len(errors)} error{'s' if len(errors) != 1 else ''}"
    elif not reviewed:
        headline = "all clear"
    else:
        headline = f"{len(ready)} ready to merge, {len(review)} need your review"
    if errors and reviewed:
        headline += f"; {len(ready)} ready, {len(review)} to review"
    return f"WELL maintainer: {headline}", "\n".join(lines) + "\n"


EMAIL_RE = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+")


def parse_alert_emails(text):
    """Recipients from ALERT_EMAILS, as the backend reads them (dashboard/backend/app/utils/digest.py)."""
    valid, invalid = [], []
    for entry in re.split(r"[,;\s]+", text or ""):
        if not entry:
            continue
        if not EMAIL_RE.fullmatch(entry):
            invalid.append(entry)
        elif entry.lower() not in (v.lower() for v in valid):
            valid.append(entry)
    return valid, invalid


def smtp_settings(env):
    """As dashboard/backend/app/utils/digest.py: None unless SMTP_HOST and SMTP_PORT are both set."""
    host, port = (env.get("SMTP_HOST") or "").strip(), (env.get("SMTP_PORT") or "").strip()
    if not host or not port:
        return None
    if not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError("SMTP_PORT must be a port number")
    user = (env.get("SMTP_USER") or "").strip()
    sender = (env.get("SMTP_FROM") or "").strip() or user
    if not sender:
        raise ValueError("set SMTP_FROM (or SMTP_USER) to the address the email is sent from")
    return {"host": host, "port": int(port), "user": user, "password": env.get("SMTP_PASSWORD") or "",
            "from": sender}


def send_email(settings, recipients, subject, body, smtp=smtplib):
    """As daily_digest.py: SSL on port 465, otherwise STARTTLS when offered; never a login without encryption."""
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings["from"], ", ".join(recipients), subject
    message.set_content(body)
    context = ssl.create_default_context()
    if settings["port"] == 465:
        server = smtp.SMTP_SSL(settings["host"], settings["port"], timeout=30, context=context)
    else:
        server = smtp.SMTP(settings["host"], settings["port"], timeout=30)
    with server:
        if settings["port"] != 465:
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls(context=context)
                server.ehlo()
            elif settings["user"] and settings["password"]:
                raise RuntimeError(f"{settings['host']}:{settings['port']} doesn't offer STARTTLS; not logging in "
                                   "without encryption")
        if settings["user"] and settings["password"]:
            server.login(settings["user"], settings["password"])
        server.send_message(message)


def gather(env, transport=urllib_transport):
    """(reviewed pull requests, Claude's result, errors, notes) from the environment and the GitHub API."""
    repo, login = env["GITHUB_REPOSITORY"], env.get("MAINTAINER_LOGIN") or ""
    errors, notes = [], []
    outcome = env.get("CLAUDE_OUTCOME") or "unknown"
    if outcome != "success":
        errors.append(f"the Claude step's outcome was {outcome}")
    result = parse_result(env.get("CLAUDE_RESULT"))
    if result is None and outcome == "success":
        errors.append("Claude finished but its report was missing or not JSON")
    inputs_file = env.get("INPUTS_FILE")
    if inputs_file:
        try:
            with open(inputs_file, encoding="utf-8") as f:
                inputs = json.load(f)
            errors += [f"collecting inputs: {e}" for e in inputs.get("errors") or []]
            notes += inputs.get("notes") or []
        except (OSError, ValueError) as error:
            errors.append(f"the inputs file couldn't be read: {error}")
    # What maintainer_publish.py did: a branch it refused to push needs a look as much as an error does.
    publish_file = env.get("PUBLISH_FILE")
    if publish_file and os.path.exists(publish_file):
        try:
            with open(publish_file, encoding="utf-8") as f:
                published = json.load(f)
            errors += [f"publishing: {e}" for e in published.get("errors") or []]
            errors += [f"not published: {r.get('branch')}: {r.get('reason')}" for r in published.get("refused") or []]
            notes += [f"{p.get('branch')}: {p.get('action')}" for p in published.get("published") or []]
        except (OSError, ValueError, AttributeError) as error:
            errors.append(f"the publish result couldn't be read: {error}")
    elif publish_file:
        errors.append("the publish step left no result (did it run?)")
    gh = github_client(env["GITHUB_TOKEN"], transport)
    reviewed = []
    try:
        reviewed = review_prs(gh, repo, maintainer_prs(gh, repo, login), login)
    except (HttpError, OSError, ValueError, KeyError) as error:
        errors.append(f"listing the maintainer's pull requests: {error}")
    if login:
        try:
            for commit in direct_pushes(gh, repo, env.get("MAIN_BEFORE"), env.get("MAIN_AFTER"), login):
                errors.append(f"commit {commit.get('sha', '')[:12]} reached main committed by {login} directly, "
                              "not through a merged pull request; check whether this run pushed it")
        except (HttpError, OSError, ValueError) as error:
            errors.append(f"checking main for direct pushes: {error}")
    return reviewed, result, errors, notes


def main(env=None, transport=urllib_transport, smtp=smtplib):
    env = os.environ if env is None else env
    for name in ("GITHUB_REPOSITORY", "GITHUB_TOKEN"):
        if not env.get(name):
            print(f"::error::{name} is not set")
            return 2
    reviewed, result, errors, notes = gather(env, transport)
    if env.get("TOKEN_MODE") == "github_token":
        notes.insert(0, "Pull requests are opened as github-actions[bot] until WELL_MAINTAINER_PAT is set (and CI on "
                        "them is started by the maintainer through workflow_dispatch, since their pushes start none).")
    try:
        settings = smtp_settings(env)
    except ValueError as error:
        settings, errors = None, errors + [f"SMTP settings: {error}"]
    recipients, invalid = parse_alert_emails(env.get("ALERT_EMAILS"))
    if invalid:
        notes.append(f"ALERT_EMAILS: ignored {len(invalid)} entries that aren't email addresses")
    subject, body = build_email(reviewed, result, errors, env.get("RUN_URL") or "",
                                dry_run=(env.get("DRY_RUN") or "").lower() == "true", notes=notes)
    summary_file = env.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"## {subject}\n\n```\n{body}```\n")
    print(f"{subject}\n\n{body}")
    if settings is None:
        print("::warning::SMTP_HOST/SMTP_PORT not set, so the summary was not emailed")
        return 0
    if not recipients:
        print("::error::SMTP is set up but ALERT_EMAILS has no valid address")
        return 1
    try:
        send_email(settings, recipients, subject, body, smtp)
    except (OSError, smtplib.SMTPException, RuntimeError) as error:
        print(f"::error::sending the email failed: {type(error).__name__}: {error}")
        return 1
    print(f"Emailed {len(recipients)} recipient(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
