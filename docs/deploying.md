# Deploying

The VM runs `main`. On the VM, `./deploy.sh`:
- pulls `main`;
- rebuilds only the services whose files changed:
  - `dashboard/frontend/` → `dashboard`;
  - `dashboard/backend/` → `backend`, `worker`, `export_worker`, and `ops` (welldash²) when it is running. A minute
    later `ops` is checked like the workers, but a failing `ops` is only logged ("welldash² needs a look"): it isn't
    public, so it never rolls the site back;
  - `docker-compose.yml` → everything;
  - `wordpress/*.conf` or `*.ini` (Apache/PHP settings mounted into the `wordpress` container) → the `wordpress`
    container is recreated, since Apache and PHP read them only at start (`--auto` holds these for a person);
  - `home/` needs nothing: the `wordpress` service is the stock `wordpress` image with `home/` bind-mounted, so it's
    live once pulled (which is why `--auto` holds its PHP files for a person).
- checks the site: `/api/latest`, the dashboard home page (both on port 8081) and the WordPress home page (port 8080).
  If `worker` or `export_worker` was rebuilt, it also checks a minute later that the container is still running and
  hasn't restarted (compose restarts crashing workers, so "running" alone proves nothing);
- rolls back to the previous commit if any check fails;
- after a healthy deploy that rebuilt images, frees disk: it removes dangling images (old builds no longer tagged),
  except the ones the containers ran just before this deploy, which stay as rollback points, and trims the build
  cache to its 5 GB most recently used (`docker builder prune --reserved-space 5GB`). Volumes are never pruned. The
  log line "pruned ..." says how many images went and how much free disk changed; a failed prune is only logged.

Its lock, the last problem it reported and the last commit it rolled back are kept in `.deploy-state/` next to the
script (git-ignored), not in `/tmp`, which RHEL empties of files older than 10 days.

If the site is already unhealthy before a deploy, `--auto` doesn't deploy (so the new commit isn't blamed and rolled
back); `./deploy.sh` by hand deploys anyway and doesn't roll back.

Each run is logged in `deploy.log` (best effort: a log it can't write never stops a deploy halfway), and any failure,
expected or not, logs a `FAILED:` line. Over 5 MB, `deploy.log` is moved to `deploy.log.1` and a new one started.
`./deploy.sh --dry-run` only shows what would happen: no log, no pings, no state. It refuses to run over local edits to
tracked files, so change the VM only through `main`.

## Automatic deploys (`--auto`)

`./deploy.sh --auto` deploys a new commit on `main` only once the CI jobs listed in `REQUIRED_CHECKS` at the top of
`deploy.sh` have passed (`.github/workflows/ci.yml`): "Backend image and tests", "Dashboard build", "Dashboard image",
"Deploy script" and "End-to-end data (vendors to browser)". The "Lint Python, shell and compose" job isn't waited for,
so a lint failure alone doesn't stop a deploy. A job that is renamed in `ci.yml` but not in `REQUIRED_CHECKS` counts as
still running, so nothing deploys until both match. It holds changes that need a person, logging them and leaving them
for you:
- a new database migration;
- `docker-compose.yml`;
- a WordPress core update, which needs its database update run from wp-admin;
- anything under `.github/` (a changed workflow could also make a bad change pass CI), `deploy.sh` itself, PHP under
  `home/`, `wp-config*`, `.htaccess`, and the Apache/PHP config in `wordpress/` (`HOLD_PATHS` in `deploy.sh`). These
  are live as soon as they are pulled, with no rebuild or test, so a merged pull request alone doesn't put them on the
  VM: a person looks at the change and runs `./deploy.sh`.

Deploy those with `./deploy.sh`. `--auto` reports each problem once, not every 5 minutes: a held commit, failed CI,
local edits, a non-fast-forward or a merge git refuses, a GitHub API error or unreadable reply, a fetch error, an
already-unhealthy site, or any other command failing (keyed by its line). A commit that was deployed and rolled back
isn't retried, whatever else fails in between; a newer commit on `main`, or `./deploy.sh` by hand, moves past it.

### Before adding the cron line

Check these on the VM first; each is something `--auto` relies on:
- The tracked tree is clean (`git status --porcelain --untracked-files=no` prints nothing) and
  `find home ! -user "$USER" | head` prints nothing, so a pull can update every file.
- The three health checks return 200 now:
  ```
  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8081/api/latest
  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8081/
  curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: well.mcmaster.ca' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8080/
  ```
- `DASHBOARD_PORT` in `.env` is 8081 (the checks use that port).
- Fetching works without an SSH agent, as it will from cron: `env -i HOME=$HOME PATH=/usr/bin:/bin git fetch origin main`.
- Run `./deploy.sh` once by hand.

Then add this to your crontab (`crontab -e`):

```
*/5 * * * * cd ~/WELLWebsite && DEPLOY_HEALTHCHECK_URL=https://hc-ping.com/<uuid> ./deploy.sh --auto >/dev/null 2>>deploy.log
```

`DEPLOY_HEALTHCHECK_URL` is optional. The script pings it on success (up to date, or deployed and healthy) and pings
`<url>/fail` on a failure or a held commit. Runs that are waiting (CI still running, a problem already reported,
another deploy in progress) don't ping. So set the Healthchecks period to 5 minutes and the grace time longer than CI
takes (30 minutes is safe), or a slow CI run will look like an outage.

To show deploys on welldash²'s Overview page, point `DEPLOY_LOG` into its logs folder (see
[Showing deploys](../dashboard/backend/app/ops/README.md#showing-deploys)). The script's other settings are in
[configuration.md](configuration.md#deploy-script-deploysh-set-in-the-crontab-line).
