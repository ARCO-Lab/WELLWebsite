# GitHub Actions and repository automation

What runs on GitHub: CI on every pull request, the daily API canary, the daily Sentry check, the load test and
Dependabot. The workflows are in this folder; their scripts are in [`.github/scripts/`](../scripts/).

## CI

`ci.yml` checks every pull request and every push to `main`, close to production: the backend is tested inside the same
Docker image the VM builds. Its jobs:

| Job | What it checks |
|---|---|
| Backend image and tests | The backend image builds and its packages are consistent (`pip check`); the unit tests run inside it with throwaway PostgreSQL 13 databases (the run fails if a PostgreSQL test was skipped); every migration applies to a fresh database and a second run finds nothing to apply; the app, worker, scheduler and export modules import. |
| Dashboard build | `npx tsc --noEmit`, `npm test` (chart helpers, site time, the backend proxy), `npm run build` and `npm run lint`. |
| Dashboard image | The dashboard image builds and starts and serves the dashboard. |
| End-to-end data (vendors to browser) | Vendor fixtures through the real ingestion, PostgreSQL, the backend and the built dashboard, to what a browser shows and downloads, in three browser time zones ([dashboard/frontend/README.md](../../dashboard/frontend/README.md#end-to-end-tests)). |
| Lint Python, shell and compose | ruff's pyflakes rules on the backend and the CI scripts, the `.github/scripts` unit tests, shellcheck on `deploy.sh` and the CI and load-test scripts, `docker compose config`, and the WordPress Apache/PHP config files in the image compose runs. |
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
