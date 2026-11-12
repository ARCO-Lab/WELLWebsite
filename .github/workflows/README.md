# GitHub Actions and repository automation

What runs on GitHub: CI on every pull request, the daily API canary, the daily Sentry check, the daily maintainer,
the load test and Dependabot. The workflows are in this folder; their scripts are in [`.github/scripts/`](../scripts/).

## CI

`ci.yml` checks every pull request and every push to `main`, close to production: the backend is tested inside the same
Docker image the VM builds. Its jobs:

| Job | What it checks |
|---|---|
| Backend image and tests | The backend image builds and its packages are consistent (`pip check`); the unit tests run inside it with throwaway PostgreSQL 13 databases (the run fails if a PostgreSQL test was skipped); every migration applies to a fresh database and a second run finds nothing to apply; the app, worker, scheduler and export modules import. |
| Dashboard build | `npx tsc --noEmit`, `npm test` (chart helpers, site time, the backend proxy), `npm run build` and `npm run lint`. |
| Dashboard image | The dashboard image builds and starts and serves the dashboard. |
| End-to-end data (vendors to browser) | Vendor fixtures through the real ingestion, PostgreSQL, the backend and the built dashboard, to what a browser shows and downloads, in three browser time zones ([dashboard/frontend/README.md](../../dashboard/frontend/README.md#end-to-end-tests)). |
| Lint Python, shell and compose | ruff's pyflakes rules on the backend and the CI scripts, the `.github/scripts` unit tests (Sentry issues, daily maintainer), shellcheck on `deploy.sh` and the CI and load-test scripts, `docker compose config`, and the WordPress Apache/PHP config files in the image compose runs. |
| Deploy script | `deploy.sh` in a sandbox (`test_deploy.sh`: a fake remote and stub `docker` and `curl`), and `canary_issue.sh` against a stub `gh`. |

`deploy.sh --auto` waits for every job except the lint job before deploying a commit
([docs/deploying.md](../../docs/deploying.md#automatic-deploys---auto)). How to keep the lint job and GitHub's
code-quality bot quiet in backend code is in [dashboard/backend/README.md](../../dashboard/backend/README.md#local-setup).

## API canary

`canary.yml` runs `dashboard/backend/app/scripts/api_canary.py` every day at 11:17 UTC. It makes one small request to
each source and checks both the HTTP status and that the response still has the fields ingestion reads:

- **LI-COR**: the last 6 hours for the first logger in `HOBOLINK_LOGGERS` (`data[]` records with `sensor_sn`, and a
  `timestamp` and numeric `value` on every record ingestion stores; battery and unknown logger channels are skipped,
  as ingestion skips them).
- **WQData**: the last 6 hours for `WQ_DEVICE_ID`, as exactly one request, because WQData's hourly quota is shared
  with the 10-minute ingestion (`data[]` points with `timestamp` and `values[].parameterId`, plus `info` for paging).
- **Borealis**: the metadata of both datasets (`BOREALIS_SAMPLING_PERSISTENT_ID`, which downloads read, and
  `BOREALIS_UPLOAD_PERSISTENT_ID`, which uploads add to; the older `DEMO_BOREALIS_*` names are read when these are
  unset) with `BOREALIS_API_TOKEN` (`data.latestVersion` with `versionState` and `files[].dataFile`). This proves the
  token is accepted and can read both datasets, not that it may still add files: the monthly upload also needs edit
  rights on the upload dataset, which the canary doesn't test (`scripts/borealis_check.py --check` does).

It prints one `OK` or `FAIL` line per source (HTTP status and reason only, never URLs, keys or response bodies) and
fails the run if any source fails. An empty response counts as a failure too, since ingestion would have nothing to
store. Every failure shows on the repository's Actions tab, and the workflow keeps one GitHub issue in step with it
(`.github/scripts/canary_issue.sh`, run by the workflow's second job):

- **A failed run** opens an issue titled "API canary failing", labelled `canary` (the label is created if missing) and
  assigned to the maintainer set in `canary_issue.sh` (`CANARY_ISSUE_ASSIGNEE` overrides it), with the run's
  `OK`/`FAIL` lines and a link to the run. If a `canary` issue is already open, the run adds the same as a comment
  instead, so a long outage stays in one issue. A run that fails before the canary prints anything (a failed install,
  a timeout) still counts as a failure, and says so. The issue also says "printed no results" if GitHub withheld the
  lines: it drops a job output that contains any secret's value (the run log then shows "Skip output 'report' since it
  may contain secret"), which can happen if a short secret such as `WQ_DEVICE_ID` matches a printed number. The run
  log still has the lines.
- **The next passing run** comments "Recovered" with its link and closes the issue. A passing run with no open issue
  does nothing.
- Only the canary's own `OK`/`FAIL` lines are posted. The issue job uses the workflow's `GITHUB_TOKEN` with
  `issues: write` (and `contents: read`), runs on a separate runner from the vendor secrets, and only runs for
  scheduled and manual runs, never for pull requests.

Being assigned (or watching the repository) means GitHub emails about the issue. The usual "workflow run failed" email
also still goes out, if the person's notification settings include Actions: for a scheduled run, to whoever last
changed the workflow's `cron` line (or last re-enabled the workflow); for a manual run, to whoever started it. GitHub
turns scheduled workflows off after 60 days without activity in the repository, and a disabled schedule sends nothing
and opens no issue: after a quiet period, check the Actions tab and re-enable the workflow there.

Using it:

- **Run it by hand**: Actions → API canary → Run workflow. On the VM:
  `docker compose exec worker python scripts/api_canary.py`.
- **When a key is rotated**, update the matching repository secret (Settings → Secrets and variables → Actions) as
  well as `dashboard/backend/app/.env` on the VM, then run the canary by hand. The secrets are `HOBOLINK_API_URL`,
  `HOBOLINK_API_TOKEN`, `HOBOLINK_LOGGERS`, `WQ_API_URL`, `WQ_API_KEY`, `WQ_DEVICE_ID`, `BOREALIS_URL`,
  `BOREALIS_API_TOKEN`, `BOREALIS_SAMPLING_PERSISTENT_ID` and `BOREALIS_UPLOAD_PERSISTENT_ID` (or the older
  `DEMO_BOREALIS_URL`, `DEMO_BOREALIS_AW_PERSISTENT_ID` and `DEMO_BOREALIS_WC_PERSISTENT_ID`).
- **Tests**: `dashboard/backend/tests/test_api_canary.py` (no network). The canary keeps copies of a few constants
  from `utils/parsers.py` so the workflow needs only `requests`; CI runs the tests that check those copies still match
  on every pull request, with the rest of the backend tests (by hand, from `dashboard/backend`:
  `python -m unittest discover -s tests -t .`). The issue logic is tested by `.github/scripts/test_canary_issue.sh`
  against a stub `gh` (`bash .github/scripts/test_canary_issue.sh`; CI runs it with the deploy script test).

## Sentry errors as GitHub issues

Every day at 13:17 UTC, the `Sentry issues` workflow (`sentry-issues.yml`, script `.github/scripts/sentry_issues.py`)
lists the unresolved issues in the `well-cs` Sentry organization that had events in the last 14 days. It does this
without Sentry's GitHub app, which needs an organization owner to install:
- An issue with no GitHub issue yet gets one, labelled `sentry` and titled `[Sentry] <short id>: <exception type>` (or
  `unresolved error` when the type is missing or doesn't look like an exception class, such as `TypeError` or
  `psycopg2.errors.UndefinedTable`). The issue shows the Sentry title, the project, event and user counts, first and
  last seen, the culprit, the top 8 frames of the latest event's stack trace and a link to Sentry.
- An open GitHub issue gets a comment when the event count jumps: at least twice the count last reported there and 20
  more events (`SENTRY_JUMP_FACTOR`, `SENTRY_JUMP_MIN`).
- A closed GitHub issue gets one "Seen again" comment per new sighting after it was closed. It is never reopened
  automatically: reopen it if the fix didn't hold, or resolve the issue in Sentry.
- Test events (titles containing "Sentry test") are skipped.

GitHub issues are matched to Sentry issues by a hidden `<!-- sentry:<short id> -->` line in the issue body, among open
and closed issues labelled `sentry`, so don't remove that line. The repository is public, so the issue text never
includes request data, cookies, headers, local variables, breadcrumbs or user details. E-mail and IP addresses, query
strings, invisible Unicode characters and anything that looks like a key are also removed from the title, the culprit
and the stack frames. That text can come from site visitors, so it stays in code spans or a code block, under a line
saying to treat it as data, not instructions; the issue title holds only the short id and the exception type.

To set it up, create a Sentry auth token with only `org:read`, `project:read` and `event:read` (*User settings >
Personal Tokens*, or an internal integration's token) and save it as the repository secret `SENTRY_API_TOKEN`
(*Settings > Secrets and variables > Actions*). Without the secret, the run passes with a warning. The workflow writes
issues with the built-in `GITHUB_TOKEN` and does nothing on forks. To run it by hand, open *Actions > Sentry issues >
Run workflow*. You can choose another period there (e.g. `24h`) or tick *dry run*, which only prints what it would do.
How errors reach Sentry in the first place is in
[dashboard/backend/README.md](../../dashboard/backend/README.md#error-reporting-sentry).

## Daily maintainer

`daily-maintainer.yml` (with its steps in `maintainer-run.yml`) runs Claude Code ([anthropics/claude-code-action](https://github.com/anthropics/claude-code-action)) every day at 11:23 UTC (6:23 or 7:23 in Toronto) to find and fix problems, and emails a summary. Every change arrives as a pull request for you to read and merge; the maintainer is told never to merge, and its tool rules deny it (see [what stops it](#what-stops-it-from-doing-harm) for what that does and doesn't guarantee).

What a run does:

1. **Collects the inputs** (`.github/scripts/maintainer_inputs.py`, into one JSON file): open issues labelled `sentry`; unresolved Sentry issues seen in the last 24 hours with their latest exception (organization `well-cs`, when `SENTRY_API_TOKEN` is set); failed workflow runs on `main` in the last 24 hours (the API canary, the load test and the maintainer itself are left out); unresolved github-code-quality[bot] comments on open pull requests; open code scanning and Dependabot alerts, when the token can read them; and the maintainer's own open pull requests and `maint/*` branches, so nothing is fixed twice. The Sentry token is used in this step only and is never in Claude's environment.
2. **Claude works through them** following `.github/maintainer/PROMPT.md`: it skips what isn't a code problem (vendor outages, expired keys, bots probing URLs) or is already handled, and fixes the rest, most important first, at most 3 pull requests a run. Each fix gets its own `maint/<topic>` branch from `main`, new commits only, a test where the code is testable, the CI checks run before pushing, a pull request assigned to the repository maintainer with the sections Summary, What changes, Testing, Deploy and Risk, and the github-code-quality comments addressed. A separate subagent then audits the pull request, and Claude fixes its findings until the audit says "Approval recommended".
3. **Labels** each pull request: `maintainer`; `risk:high` if it touches the database schema or migrations, `docker-compose.yml`, Dockerfiles, `deploy.sh`, `nginx.conf`, dependency manifests, ingestion, backfills, uploads, the scheduler, Sentry or other security code, the Flask app (`server.py`), the ops dashboard (`app/ops/`), the dashboard's API routes or `next.config.*`, `.gitignore`/`.gitattributes`, `.github/`, `.claude/`, `home/` or `wordpress/`, otherwise `risk:low`; and `audit:approved` once the audit recommends approval and CI passed (`audit:findings` while it doesn't).
4. **Emails the summary** (`.github/scripts/maintainer_summary.py`) to `ALERT_EMAILS`, every run, also when there is nothing to report ("all clear"), so a day without an email means the job didn't run. It lists the maintainer's open pull requests (from `maint/*` branches, or labelled `maintainer`) in two groups, with links: **Ready to merge** (the maintainer's own: from a `maint/*` branch of this repository and opened by the maintainer's account; with the PAT that account is your own, which opens your other pull requests too, so the `maint/*` branch is what tells them apart, and your other pull requests are never listed as ready; CI passed with all five checks `main` requires among the results, `audit:approved`, `risk:low`, no risky files, not a draft) and **Needs your review** (anything else, with the reasons: not opened by the maintainer (a `maintainer` label alone doesn't count), `risk:high`, a risky file, which the script checks itself whatever the label says, failed, unfinished or missing required checks, an audit with findings). Then what the run did and skipped, and any errors, including a commit that reached `main` from the maintainer's account other than through a merged pull request. The same text is in the run's job summary.

**Who the pull requests come from.** With `WELL_MAINTAINER_PAT` set, the checkout, every push and every pull request use that token, so commits and pull requests appear as its owner, with the owner's GitHub noreply address (`<id>+<login>@users.noreply.github.com`, read from the API at run time) as the commit email, and CI starts on them as on any pull request. Without it, the workflow falls back to its own `GITHUB_TOKEN`: commits and pull requests appear as `github-actions[bot]`, and the email says so. GitHub doesn't start workflows for pushes or pull requests made with that token, so in this mode the maintainer starts CI itself on its branch (`gh workflow run ci.yml --ref maint/<topic>`; `ci.yml` accepts `workflow_dispatch` for this). Those runs have the same job names on the same commit, so they count for `main`'s required checks. The fallback needs two settings: the workflow's `permissions` grant `contents`, `pull-requests`, `issues` and `actions: write` (only in the `with-workflow-token` job, which runs only without the PAT), and *Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests* must be on (the organization may have to allow it first), or `gh pr create` fails. Nothing in the workflow approves a pull request.

Secrets (Settings → Secrets and variables → Actions → New repository secret):

| Secret | Needed | What |
| --- | --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` | this or the next | Run `claude setup-token` locally (Claude Pro or Max subscription) and paste the token. Uses the subscription's limits. |
| `ANTHROPIC_API_KEY` | this or the previous | An API key from the Claude Console, billed per use. Set only one of the two. |
| `WELL_MAINTAINER_PAT` | optional (recommended) | A fine-grained personal access token created by the account the maintainer's pull requests should come from: *Settings → Developer settings → Fine-grained tokens → Generate new token*, resource owner `ARCO-Lab`, *Only select repositories* → `ARCO-Lab/WELLWebsite`, repository permissions **Contents: Read and write**, **Pull requests: Read and write**, **Issues: Read and write**, **Actions: Read**, **Metadata: Read** (added automatically), and optionally **Dependabot alerts: Read** and **Code scanning alerts: Read** so the inputs include those alerts. Expiry: the longest the organization allows (90 days is a sensible default); put a reminder in the calendar, since an expired token fails the run with "WELL_MAINTAINER_PAT was rejected". The organization must allow fine-grained tokens, and may have to approve this one (*ARCO-Lab → Settings → Personal access tokens*). It has no Workflows permission, on purpose, so it can't change workflow files. |
| `SENTRY_API_TOKEN` | optional | A read-only Sentry auth token for `well-cs` (a personal token with `event:read`, `project:read` and `org:read`). Without it Sentry isn't queried; the `sentry` GitHub issues still are. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAILS` | optional | The same values as the backend's daily digest in `dashboard/backend/app/.env` (see [Monitoring](../../dashboard/backend/README.md#monitoring)): port 465 uses SSL, other ports STARTTLS, and the password is never sent unencrypted. Without `SMTP_HOST`/`SMTP_PORT` the summary is only in the job summary. |

A missing Claude credential fails the run at its first step, and a rejected (expired or revoked) PAT right after; a missing optional secret only adds a warning. Those two failures stop the run before the summary email, so the only signal is GitHub's "workflow run failed" email (sent, for a scheduled run, to whoever last changed the workflow's `cron` line, if their notification settings include Actions) and the red run on the Actions tab: a morning without the maintainer's email means look there. The repository variable `MAINTAINER_MODEL` (Settings → Secrets and variables → Actions → Variables), if set, picks the model (e.g. `opus`); otherwise Claude Code's default is used.

Using it:

- **Run it by hand**: Actions → Daily maintainer → Run workflow. *dry run* investigates and reports without creating branches or pull requests (an instruction to Claude, not enforced by the token); *max prs* changes the limit for that run (1 or more; 0 is refused with a message, use *dry run* to change nothing).
- **Pause it**: Actions → Daily maintainer → ⋯ → Disable workflow (Enable workflow resumes it). GitHub also disables scheduled workflows after 60 days without repository activity.
- **Change what it does**: edit `.github/maintainer/PROMPT.md` (instructions), `.github/maintainer/settings.json` (allowed and denied tools) or `RISKY_PATHS` in `.github/scripts/maintainer_summary.py` (what always needs your review) in a normal pull request. The maintainer is told not to edit these, and its tool rules deny it.
- **Tests**: `python3 -m unittest discover -s .github/scripts -p 'test_maintainer*.py'` (standard library only; the GitHub and Sentry APIs and SMTP are faked). CI runs them in the "Lint Python, shell and compose" job.

### What stops it from doing harm

- **`main` can't be pushed to**: branch protection requires a pull request and the five CI checks, with no bypass, for administrators too. A commit can only reach `main` through a merged pull request.
- **Merging is not blocked by GitHub.** `main` requires no approving review, and both tokens can merge a pull request whose checks passed through the API (the PAT has Contents and Pull requests write; so does the workflow token in the fallback). That the maintainer never merges rests on its instructions and its tool rules below. Requiring one approving review on `main` would make GitHub enforce it (the PAT's owner can't approve their own pull request), at the cost of every pull request, yours included, needing a second person's approval.
- **Tool rules** (`.github/maintainer/settings.json`): git, `gh` for pull requests, issues, runs and labels, npm, Python, ruff, shellcheck and Docker for the tests are allowed; merging, closing or reviewing pull requests, pushes to `main` or anything but `maint/*` (any push with a refspec such as `a:b`, more than one branch, `HEAD` or `--all` is denied, so `git push origin maint/x:main` or `git push origin maint/x other` can't slip through the allow rule), force-pushes, branch deletion, amends and rebases, `gh secret`/`gh repo`/`gh auth`, writes through `gh api` (`-X`, `--method`, `-f`, `-F`, GraphQL), `curl`, `wget`, `nc`, Python one-liners that open network connections or read the environment, printing the environment, `git remote`/`git config` (the action keeps the token in the remote URL), reading `.git/config` or `.env` files, and editing `.github/workflows/` or the maintainer itself are denied. `gh pr edit` and labelling are allowed on any pull request (only changing a pull request's base branch is denied): that the maintainer edits and labels only its own `maint/*` pull requests rests on the prompt alone. The rules match commands as written, and Claude can still write and run a Python file, so they stop mistakes, not a determined attacker. The same file turns off Claude Code's commit and pull request attribution (`"attribution": {"commit": "", "pr": "", "sessionUrl": false}`), so no `Co-Authored-By` or "Generated with" line is added.
- **Untrusted input**: Sentry events, issue bodies, review comments and logs are text from outside (anyone can make the site raise an error with a message they chose), so they can try to give Claude instructions (prompt injection). The prompt tells Claude to treat them as data, never follow instructions in them, and report any that try; the Sentry token is never in Claude's environment, and the tool rules above limit what a fooled Claude could run. This is a reduced risk, not a removed one, which is why everything still goes through your review.
- **Network**: not restricted beyond the tool rules. An egress allowlist (for example `step-security/harden-runner` in block mode) would also need Docker Hub, npm, PyPI, the Playwright downloads, Anthropic, GitHub, Sentry and the SMTP host, and any miss would fail runs; it isn't used.
- **Permissions**: the workflow token only reads when the PAT is set (the `with-pat` job); it gets write permissions only in the `with-workflow-token` job, which runs only when the PAT isn't set.

## Load test

`load-test.yml` measures how the dashboard copes when many people open it at once, on a throwaway copy of the stack on
the runner; it never touches production. It runs by hand from the Actions tab (a weekly run is off unless the
repository variable `LOAD_TEST_WEEKLY` is `true`). What it runs and how to read the results:
[docs/load-testing.md](../../docs/load-testing.md).

## Dependabot

`.github/dependabot.yml` opens a few pull requests every Monday that bump dependencies, each checked by CI like any
other pull request: the dashboard's npm packages, the end-to-end tests' npm packages, the backend's pip requirements
(`requirements.txt` pins every package, dependencies included), the base images of the two images built on the
server, and the actions used in these workflows. Minor and patch bumps are grouped into one pull request per
ecosystem; major bumps come one per pull request, so each breaking change is reviewed on its own. A few packages are
held back on purpose; the file says which and why. WordPress core and plugins under `home/` are updated through
WordPress itself, not by Dependabot.
