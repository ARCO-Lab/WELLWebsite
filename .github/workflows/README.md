# GitHub Actions and repository automation

What runs on GitHub: CI on every pull request, the daily API canary, the daily Sentry check, the daily maintainer,
the load test and Dependabot. The workflows are in this folder; their scripts are in [`.github/scripts/`](../scripts/).

## CI

`ci.yml` checks every pull request and every push to `main`, close to production: the backend is tested inside the same
Docker image the VM builds. Its jobs:

| Job | What it checks |
|---|---|
| Backend image and tests | The backend image builds and its packages are consistent (`pip check`); the unit tests run inside it with throwaway PostgreSQL 13 databases (the run fails if a PostgreSQL test was skipped), then the PostgreSQL ones again as the app's own role `well_app` from `dashboard/backend/app/db/roles.sql`, which `tests/test_db_roles.py` checks can't run programs or create roles; every migration applies to a fresh database as `well_app`, the roles check passes and a second run finds nothing to apply; the app, worker, scheduler and export modules import. |
| Dashboard build | `npx tsc --noEmit`, `npm test` (chart helpers, site time, the tile loader, the backend proxy, sampling fetches, export polling, shared links), `npm run build` and `npm run lint`. |
| Dashboard image | The dashboard image builds and starts and serves the dashboard. |
| End-to-end data (vendors to browser) | Vendor fixtures through the real ingestion, PostgreSQL, the backend and the built dashboard, to what a browser shows and downloads, in three browser time zones ([dashboard/frontend/README.md](../../dashboard/frontend/README.md#end-to-end-tests)). |
| Lint Python, shell and compose | ruff's pyflakes rules on the backend and the CI scripts, the `.github/scripts` unit tests (Sentry issues, daily maintainer), shellcheck on `deploy.sh`, `wordpress/backup.sh`, the CI and load-test scripts and `dashboard/backend/app/db/roles.sh` (which must print its steps), the WordPress backup's tests (`test_wordpress_backup.sh`: stub `docker` and `curl`, then a throwaway MySQL 5.7), `docker compose config`, the WordPress Apache/PHP config files in the image compose runs, and `php -l` on every PHP file of the theme (`home/wp-content/themes/well`) in that image. |
| Deploy script | `deploy.sh` in a sandbox (`test_deploy.sh`: a fake remote and stub `docker` and `curl`), and `canary_issue.sh` against a stub `gh`. |

`deploy.sh --auto` waits for every job except the lint job before deploying a commit
([docs/deploying.md](../../docs/deploying.md#automatic-deploys---auto)). How to keep the lint job and GitHub's
code-quality bot quiet in backend code is in [dashboard/backend/README.md](../../dashboard/backend/README.md#local-setup).

A new push to a pull request cancels the older CI run on it. Runs on `main` are never cancelled or replaced, because
`--auto` counts a cancelled check as failed and wouldn't deploy that commit: each commit on `main` gets its own
concurrency group, so its run neither cancels nor waits behind another.

Every third-party action is pinned to a full commit SHA, with its release in a comment
(`actions/checkout@<sha>  # v7.0.1`), so a moved or replaced tag can't change what runs; this matters most in
`maintainer-run.yml`, whose `prepare` and `publish` jobs hold the maintainer's personal access token and whose Claude
step holds Claude's credential (it gets only the read-only workflow token for GitHub). Dependabot updates the SHA and
the comment together.

## API canary

`canary.yml` runs `dashboard/backend/app/scripts/api_canary.py` every day at 11:17 UTC. It makes a few small requests
to each source and checks both the HTTP status and that the response still has the fields ingestion reads:

- **LI-COR**: the last 6 hours for the first logger in `HOBOLINK_LOGGERS` (`data[]` records with `sensor_sn`, and a
  `timestamp` and numeric `value` on every record ingestion stores; battery and unknown logger channels are skipped,
  as ingestion skips them).
- **WQData**: the last 6 hours for `WQ_DEVICE_ID`, as exactly one request, because WQData's hourly quota is shared
  with the 10-minute ingestion (`data[]` points with `timestamp` and `values[].parameterId`, plus `info` for paging).
  Only when those 6 hours hold no points does it look further back, one day per request (about 3.5 s apart, at most
  7, and for at most 90 s in all), for the device's newest point (when a day's answer is cut off by paging, it says
  "at least as late as" that time). That is still a failure, but it reads "the device stopped reporting at `<time>`
  UTC" (or "none in the last 7 days either"), so a sonde or modem that went quiet isn't mistaken for a rejected key.
- **Borealis**: first the token alone (`/api/users/:me`), then the metadata of both datasets
  (`BOREALIS_SAMPLING_PERSISTENT_ID`, which downloads read, and `BOREALIS_UPLOAD_PERSISTENT_ID`, which uploads add to; the older `DEMO_BOREALIS_*` names are read when these are
  unset) with `BOREALIS_API_TOKEN` (`data.latestVersion` with `versionState` and `files[].dataFile`). This proves the
  token is accepted and can read both datasets, not that it may still add files: the monthly upload also needs edit
  rights on the upload dataset, which the canary doesn't test (`scripts/borealis_check.py --check` does).
  A 401 on the token gives "token not valid on `<host>`": the token is wrong, expired, or was made on the other server (tokens from `demo.borealisdata.ca` and
  `borealisdata.ca` are separate), so create it on the host named. A valid token followed by a 403 or 404 gives "token
  OK on `<host>`; the download (or upload) dataset (`BOREALIS_*_PERSISTENT_ID`) was not found or isn't shared with
  this token", and says so when the id belongs to the other server. `BOREALIS_URL` may be a collection page; the API
  calls go to its server root.

It prints one `OK` or `FAIL` line per source (HTTP status and reason only, never URLs, keys or response bodies; the
Borealis host name is printed, and persistent ids are named by their variable, since in CI they are secrets and GitHub
withholds a job output that contains a secret's value) and fails the run if any source fails. An empty response counts as a failure too, since ingestion would have nothing to
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

`daily-maintainer.yml` (with its steps in `maintainer-run.yml`) runs Claude Code ([anthropics/claude-code-action](https://github.com/anthropics/claude-code-action)) every day at 11:23 UTC (6:23 or 7:23 in Toronto) to find and fix problems, and emails a summary. Every change arrives as a pull request for you to read and merge. Claude runs with a read-only token and only commits locally; a separate job with no model checks its branches, pushes them and opens the pull requests (see [what stops it](#what-stops-it-from-doing-harm) for what that does and doesn't guarantee).

What a run does, in three jobs (`maintainer-run.yml`):

1. **Collects the inputs** (job `prepare`; `.github/scripts/maintainer_inputs.py`, into one JSON file): open issues labelled `sentry`; unresolved Sentry issues seen in the last 24 hours with their latest exception (organization `well-cs`, when `SENTRY_API_TOKEN` is set); failed workflow runs on `main` in the last 24 hours (the API canary, the load test and the maintainer itself are left out); unresolved github-code-quality[bot] comments on open pull requests; open code scanning and Dependabot alerts, when the token can read them; and the maintainer's own open pull requests and `maint/*` branches, so nothing is fixed twice. The Sentry token and the PAT are used in this job only, never in Claude's. Text from outside (Sentry titles, culprits and exception messages, issue and pull request titles and bodies, review comments) goes under an `untrusted_data` key, below a note at the top of the file saying it is data. Sentry text is cleaned the way `sentry_issues.py` cleans it for public issues (no invisible characters, addresses, query strings or credentials; one line; a code span), an exception type is kept only when it looks like a class name, and a frame's file and function only when they look like a path and an identifier. Threads on pull requests from forks are left out.
2. **Claude works through them** (job `maintain`, with a read-only workflow token and no other GitHub token) following `.github/maintainer/PROMPT.md`: it skips what isn't a code problem (vendor outages, expired keys, bots probing URLs) or is already handled, and fixes the rest, most important first, at most 3 a run. Each fix gets its own local `maint/<topic>` branch from `main`, new commits only, a test where the code is testable, and the CI checks run before it is reported. A fresh subagent audits each branch, and Claude fixes its findings until it says "Approval recommended". That is a self-check by the same run, not an independent review, which is why the labels say `self-check`. Claude can't push: it describes each branch in its report (title, body with Summary, What changes, Testing, Deploy and Risk, its risk and self-check result), and a step after it bundles the `maint/*` branches.
3. **Publishes them** (job `publish`, no model; `.github/scripts/maintainer_publish.py`, run from `main`'s copy): for each branch it checks that the name is `maint/<lowercase-words>`, that the report describes it, that it changes at most 20 files and 1,000 lines, no binary file, symlink or submodule, and nothing under `.github/` or `.claude/`, and that it only adds commits to a branch already on GitHub (nothing is force-pushed) whose open pull request, if any, is the maintainer's own. A branch that fails is not pushed, and the email says why. Then it pushes the branch and opens its pull request, assigned to the repository maintainer, with a Copilot review requested, and labels it: `maintainer`; `risk:high` or `risk:low` from the report; `self-check:passed` or `self-check:findings`. The body Claude wrote is shown as a plain-text block under a line saying the model wrote it, cleaned the way Sentry text is for public issues (no invisible characters, addresses, query strings or credentials; `@` and a `#` before a number neutralised), so it can't notify anyone, add a link or close an issue. After each push it comments the commit it pushed, which the summary checks against the pull request's head. Only a branch whose every file is low risk (`LOW_RISK_PATHS` in `maintainer_summary.py`: documentation, and the dashboard's `src/components/`, `hooks/`, `utils/` and `styles/`; or a backend test file the branch adds) is opened as a normal pull request. Anything else, and anything in `RISKY_PATHS` (the API, every backend utility and script, changed or deleted tests, the end-to-end and load tests, build and lint settings, the dashboard's `src/lib/` and pages, the database schema or migrations, `docker-compose.yml`, Dockerfiles, `deploy.sh`, `nginx.conf`, dependency manifests, the Flask app, the ops dashboard, `.gitignore`/`.gitattributes`, `home/` or `wordpress/`), is opened as a **draft** labelled `needs-review` and `risk:high`, whatever the report says. With the workflow token, it also starts CI on the branch, since pushes with that token start none. CI and code-quality comments on these pull requests are seen by the next day's run.
4. **Emails the summary** (also in job `publish`) (`.github/scripts/maintainer_summary.py`) to `ALERT_EMAILS`, every run, also when there is nothing to report ("all clear"), so a day without an email means the job didn't run. It lists the maintainer's open pull requests (from `maint/*` branches, or labelled `maintainer`) in two groups, with links: **Passed the automatic checks** (the maintainer's own: from a `maint/*` branch of this repository and opened by the maintainer's account; with the PAT that account is your own, which opens your other pull requests too, so the `maint/*` branch is what tells them apart, and your other pull requests are never listed there; its head is still the commit the publish job pushed, by that job's unedited comment, so a commit anyone else added since makes it need review; every commit in it authored by the maintainer's account; CI passed with all five checks `main` requires among the results, `self-check:passed`, `risk:low`, every file low risk, not a draft). These still need you to read them before merging: passing means only that nothing automatic found a reason to stop. **Needs your review** has anything else, with the reasons: not opened by the maintainer (a `maintainer` label alone doesn't count), changed since it was published, a commit someone else authored, `risk:high`, a file that isn't low risk, which the script checks itself whatever the label says, failed, unfinished or missing required checks, a self-check with findings. What Claude wrote about the run (its summary, actions, skips and errors) is cleaned the same way as the pull request bodies and set apart under "Written by the model and not checked"; a link it gives is kept only when it points into this repository. Then what the run did and skipped, which branches were published and which refused (and why), and any errors, including a commit that reached `main` from the maintainer's account other than through a merged pull request. The same text is in the run's job summary.

**Who the pull requests come from.** With `WELL_MAINTAINER_PAT` set, the publish job pushes and opens pull requests with that token, so commits and pull requests appear as its owner, with the owner's GitHub noreply address (`<id>+<login>@users.noreply.github.com`, read from the API at run time) as the commit email, and CI starts on them as on any pull request. Without it, the publish job uses the workflow's own `GITHUB_TOKEN`: commits and pull requests appear as `github-actions[bot]`, and the email says so. GitHub doesn't start workflows for pushes or pull requests made with that token, so in this mode the publish job starts CI itself on each branch (`workflow_dispatch` on `ci.yml`, which accepts it for this). Those runs have the same job names on the same commit, so they count for `main`'s required checks. The fallback needs two settings: the workflow's `permissions` grant `contents`, `pull-requests`, `issues` and `actions: write` (only in the `with-workflow-token` job, which runs only without the PAT; the `prepare` and `maintain` jobs narrow it to read), and *Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests* must be on (the organization may have to allow it first), or opening the pull request fails. Nothing in the workflow approves a pull request.

Secrets (Settings → Secrets and variables → Actions → New repository secret):

| Secret | Needed | What |
| --- | --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` | this or the next | Run `claude setup-token` locally (Claude Pro or Max subscription) and paste the token. Uses the subscription's limits. |
| `ANTHROPIC_API_KEY` | this or the previous | An API key from the Claude Console, billed per use; set a monthly spend limit for it in the Console. Set only one of the two. |
| `WELL_MAINTAINER_PAT` | optional (recommended) | A fine-grained personal access token created by the account the maintainer's pull requests should come from: *Settings → Developer settings → Fine-grained tokens → Generate new token*, resource owner `ARCO-Lab`, *Only select repositories* → `ARCO-Lab/WELLWebsite`, repository permissions **Contents: Read and write**, **Pull requests: Read and write**, **Issues: Read and write**, **Actions: Read**, **Metadata: Read** (added automatically), and optionally **Dependabot alerts: Read** and **Code scanning alerts: Read** so the inputs include those alerts. Expiry: the longest the organization allows (90 days is a sensible default); put a reminder in the calendar, since an expired token fails the run with "WELL_MAINTAINER_PAT was rejected". The organization must allow fine-grained tokens, and may have to approve this one (*ARCO-Lab → Settings → Personal access tokens*). It has no Workflows permission, on purpose, so it can't change workflow files. |
| `SENTRY_API_TOKEN` | optional | A read-only Sentry auth token for `well-cs` (a personal token with `event:read`, `project:read` and `org:read`). Without it Sentry isn't queried; the `sentry` GitHub issues still are. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAILS` | optional | The same values as the backend's daily digest in `dashboard/backend/app/.env` (see [Monitoring](../../dashboard/backend/README.md#monitoring)): port 465 uses SSL, other ports STARTTLS, and the password is never sent unencrypted. Without `SMTP_HOST`/`SMTP_PORT` the summary is only in the job summary. |

With no Claude credential set, a scheduled run is skipped at its first step with a notice and ends green (a maintainer that isn't set up yet is not a daily red run), while a run started by hand fails there. A rejected (expired or revoked) PAT fails the run right after; a missing optional secret only adds a warning. Those two failures (a manual run with no Claude credential, a rejected PAT) stop the run before the summary email, so the only signal is GitHub's "workflow run failed" email (sent, for a scheduled run, to whoever last changed the workflow's `cron` line, if their notification settings include Actions) and the red run on the Actions tab: a morning without the maintainer's email means look there. The repository variable `MAINTAINER_MODEL` (Settings → Secrets and variables → Actions → Variables), if set, picks the model (e.g. `opus`); otherwise Claude Code's default is used.

Using it:

- **Run it by hand**: Actions → Daily maintainer → Run workflow. *dry run* investigates and reports without pushing or opening anything (enforced: the publish job only checks the branches and says what it would push); *max prs* changes the limit for that run (1 or more; 0 is refused with a message, use *dry run* to change nothing).
- **Pause it**: Actions → Daily maintainer → ⋯ → Disable workflow (Enable workflow resumes it). GitHub also disables scheduled workflows after 60 days without repository activity.
- **Change what it does**: edit `.github/maintainer/PROMPT.md` (instructions), `.github/maintainer/settings.json` (allowed and denied tools), `LOW_RISK_PATHS` and `RISKY_PATHS` in `.github/scripts/maintainer_summary.py` (what may pass without your review, and what never does) or the checks in `.github/scripts/maintainer_publish.py` (`REFUSED_PATHS`, `MAX_FILES`, `MAX_LINES`) in a normal pull request. The maintainer can't change these: its tool rules deny edits under `.github/`, and the publish job refuses any branch that touches it.
- **Tests**: `python3 -m unittest discover -s .github/scripts -p 'test_maintainer*.py'` (standard library and git only; the GitHub and Sentry APIs and SMTP are faked, the publish checks run against real throwaway git repositories, and the tool rules are matched against example commands). CI runs them in the "Lint Python, shell and compose" job.

### What stops it from doing harm

- **`main` can't be pushed to**: branch protection requires a pull request and the five CI checks, with no bypass, for administrators too. A commit can only reach `main` through a merged pull request.
- **No write token where Claude runs.** Claude's job has only a read-only workflow token (and Claude's own credential). The PAT and the Sentry token are in other jobs, which matters because every secret a job uses sits in that job's runner memory, where any command could read it; separate jobs run on separate machines. So even a fooled Claude, running arbitrary code through a test, can't push, open, label or merge anything with it.
- **A deterministic gate before anything is pushed** (`maintainer_publish.py`, from `main`, not from Claude's branches): the branch name, size, file types and paths are checked as above; `.github/` and `.claude/` changes are refused, so a branch can't change CI to make itself pass; anything outside the low-risk list becomes a draft labelled `needs-review`; nothing is force-pushed; another person's pull request is never touched.
- **`deploy.sh --auto` holds what review must see** (see [Deploying](../../docs/deploying.md#automatic-deploys---auto)): besides migrations, `docker-compose.yml` and a WordPress core update, any commit that touches `.github/`, `deploy.sh`, PHP, JavaScript, HTML or SVG under `home/`, `wp-config*`, `.htaccess` or anything in `wordpress/` (its Apache/PHP config, and `backup.sh`, which the host's cron runs) waits for a person to run `./deploy.sh`. These go live with no rebuild or test, so a merge alone mustn't put them on the VM.
- **What remains: GitHub doesn't enforce "never merges".** `main` requires no approving review, and the PAT belongs to your own account, so the publish job's token could merge a pull request whose checks passed; only that the publish job's code never does (and Claude never has that token) keeps it from happening. The same identity also means GitHub can't require an approval of the maintainer's pull requests: they are yours, and you can't approve your own. The stronger setup, if you want GitHub itself to enforce it: create a separate machine account (or a GitHub App) with the **Write** role on this repository, make `WELL_MAINTAINER_PAT` that account's token, and add a ruleset on `main` (*Settings → Rules → Rulesets*) requiring **one approving review**, with the repository admin role on the bypass list. You still merge your own pull requests alone (as admin), while the maintainer's account can't merge anything, and its pull requests need your approval. The cost is a second account to keep (and its token to renew).
- **Tool rules** (`.github/maintainer/settings.json`): git for reading, branching and committing (no `push`, `remote`, `config`, `-c` or fetches from anywhere but `origin`), read-only `gh` (pull requests, issues, runs, labels, and `gh api` reads of this repository), and the exact test and lint commands of the prompt are allowed. Everything else is denied, explicitly so for: any `gh` write, `curl`, `wget`, `nc`, `ssh`, `scp`, `rsync`, `openssl` and `/dev/tcp`, whether run directly, by path or through `env`, `timeout`, `nohup`, `xargs`, `sudo`, `bash -c` or `sh -c`; Python one-liners, `node -e`, `perl`, Docker; web fetches; printing the environment; reading `.git/config`, `.env` files or `/proc`; and editing `.git/`, `.github/` or `.claude/`. The rules match commands as written, and running the tests runs code Claude wrote, so they narrow what a fooled Claude can do but are not the boundary: the read-only token and the publish gate are. The same file turns off Claude Code's commit and pull request attribution (`"attribution": {"commit": "", "pr": "", "sessionUrl": false}`), so no `Co-Authored-By` or "Generated with" line is added.
- **Untrusted input**: Sentry events, issue bodies, review comments and logs are text from outside (anyone can make the site raise an error with a message they chose), so they can try to give Claude instructions (prompt injection). The inputs are scrubbed and fenced as above, the prompt tells Claude to treat them as data, never follow instructions in them, and report any that try. This is a reduced risk, not a removed one, which is why everything still goes through your review.
- **Network**: Claude's job (`maintain`) starts with `step-security/harden-runner` (pinned to a commit) with `egress-policy: block`: the job can connect only to the hosts in its `allowed-endpoints` list, so code Claude writes and runs as a test can't send Claude's credential (or anything else) elsewhere. The list is Claude's API and installer (`api.anthropic.com`, `claude.ai`, `downloads.claude.ai`), GitHub (`github.com`, `api.github.com`, `*.githubusercontent.com` and `*.actions.githubusercontent.com` for release downloads, artifacts and the cache, `*.blob.core.windows.net` behind them), `nodejs.org`, and the npm and PyPI registries (`registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`), all on port 443. It was set before the first run, from what the steps are known to fetch, so the first runs may show a host it misses. **To allow a host**: open the run, look at harden-runner's summary (and StepSecurity's insights page linked there) for the blocked connections, check that the host is one a step really needs, and add `<host>:443` to `allowed-endpoints` in `maintainer-run.yml` in a normal pull request (the maintainer can't change `.github/`). A blocked host fails the step that needed it, so watch the run after a change. The `prepare` and `publish` jobs run no model and aren't restricted. If you use `ANTHROPIC_API_KEY` rather than a subscription token, also set a monthly spend limit in the Claude Console (*Settings → Limits*), so a leaked key or a runaway run can only cost that much.
- **The PAT**: the `token` job learns only whether each secret is set (`secrets.X != ''`), never their values. The `publish` job's checkout keeps no credentials (`persist-credentials: false`); `maintainer_publish.py` hands the write token to its one `git push`, in git's environment rather than its command line.
- **Permissions**: the `prepare` and `maintain` jobs ask for read permissions only. The `publish` job gets what `daily-maintainer.yml` grants: read only when the PAT is set (the `with-pat` job), write only in the `with-workflow-token` job, which runs only when the PAT isn't set.

## Load test

`load-test.yml` measures how the dashboard copes when many people open it at once, on a throwaway copy of the stack on
the runner; it never touches production. It runs by hand from the Actions tab (a weekly run is off unless the
repository variable `LOAD_TEST_WEEKLY` is `true`). What it runs and how to read the results:
[docs/load-testing.md](../../docs/load-testing.md).

## Dependabot

`.github/dependabot.yml` opens a few pull requests every Monday that bump dependencies, each checked by CI like any
other pull request: the dashboard's npm packages, the end-to-end tests' npm packages, the backend's pip requirements
(`requirements.txt` pins every package, dependencies included), the base images of the two images built on the
server, the images `docker-compose.yml` runs as they are (MySQL, WordPress, Redis; changes to that file are deployed by
hand, since `--auto` holds them), and the actions used in these workflows. Minor and patch bumps are grouped into one pull request per
ecosystem; major bumps come one per pull request, so each breaking change is reviewed on its own. A few packages are
held back on purpose; the file says which and why. WordPress core and plugins under `home/` are updated through
WordPress itself, not by Dependabot.
