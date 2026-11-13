# Configuration

Every setting the code reads from the environment, where it goes, and its default. No env file is committed: on the
VM they sit in the checkout, ignored by git. Longer explanations of some groups are in the folder READMEs (linked below).

| File | Read by |
|---|---|
| `.env` (repository root) | `docker compose`, which substitutes its values into `docker-compose.yml`. |
| `dashboard/backend/app/.env` | The `backend`, `worker` and `export_worker` containers (`env_file`). Scripts run outside Docker read it too: `config.py` calls `load_dotenv()`, which finds the file next to it. |
| `dashboard/frontend/.env.local` | The `dashboard` container at run time (`env_file`). It must exist for `docker compose` to start, but it can be empty. |

A variable that a service's `environment:` block in `docker-compose.yml` sets wins over the same name in
`dashboard/backend/app/.env`. So the variables in the first table below are set in the root `.env`, not in `app/.env`.

After changing an env file, recreate the containers that read it, e.g. `docker compose up -d --no-deps backend worker
export_worker`. `NEXT_PUBLIC_*` values and `FLASK_API_URL` (from `BACKEND_INTERNAL_URL`) are built into the
dashboard, so they need a rebuild (`docker compose up -d --build --no-deps dashboard`).

## Root `.env` (docker compose)

| Variable | Default | Meaning |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | required | Root password of the WordPress MySQL container (`db`). |
| `WORDPRESS_DB_PASSWORD` | required | Password of the MySQL user `wordpress`, used by `db` and `wordpress`. |
| `DEPLOYMENT` | `DEV` | `PROD` makes the WordPress theme force HTTPS URLs (`home/wp-content/themes/well/functions.php`). |
| `WP_HOME`, `WP_SITEURL` | none | Passed into the `wordpress` container. The stock image doesn't apply them by itself; they only take effect if `home/wp-config.php` (not in the repository) reads them. |
| `DASHBOARD_URL` | `https://welldash.mcmaster.ca` | The dashboard address the WordPress theme links to and embeds. |
| `BACKEND_DATABASE_URL` | required | PostgreSQL URL for `backend`, `worker` and `export_worker` (it becomes their `DATABASE_URL`). PostgreSQL runs on the VM itself, not in Docker, so this points at the host (see [Host firewall](hosting.md#host-firewall-required)). Use the `well_app` role, not `postgres` ([Database roles](../dashboard/backend/README.md#database-roles)). |
| `BACKEND_PORT` | must be `5000` | Only feeds the backend's `expose:` line. Gunicorn always listens on 5000 (`dashboard/backend/Dockerfile`), so any other value breaks the stack. |
| `BACKEND_INTERNAL_URL` | none (use `http://backend:5000`) | How the dashboard's API routes reach Flask. It becomes the dashboard's `FLASK_API_URL`, which is fixed when the image is built, so a change needs a dashboard rebuild. |
| `NEXT_PUBLIC_FLASK_API_URL` | none | Passed to the dashboard build and container, but no code reads it. |
| `DASHBOARD_PORT` | none (use `8081`) | Host port of the dashboard. `deploy.sh`'s health checks assume 8081. |
| `WORDPRESS_BIND`, `DASHBOARD_BIND` | none (every address) | Publish port 8080 (WordPress) or the dashboard's port on this one host address only, e.g. the address haproxy connects to. Then set `DEPLOY_SITE_HOST` for `deploy.sh`. See [who can reach the published ports](hosting.md#who-can-reach-the-published-ports). |
| `BACKEND_UID`, `BACKEND_GID` | `10001` | The user and group `backend`, `worker`, `export_worker` and `ops` run as. Set them to the VM user that owns the checkout (`id -u`, `id -g`), so the files the worker writes into `dashboard/backend/app/logs/` and `backups/` are that user's. See [containers run unprivileged](hosting.md#containers-run-unprivileged). |
| `TRUSTED_PROXY_IPS` | `130.113.68.30` | Reverse proxies whose `X-Forwarded-For` the dashboard believes, comma-separated. The default is McMaster's `haproxy.cas.mcmaster.ca`. Set but empty trusts none. See `dashboard/frontend/src/lib/clientIp.ts`. |
| `DB_STATEMENT_TIMEOUT_MS` | `25000` | API queries running longer are cancelled (the API answers 504). Backend container only; `0` turns it off. Don't put it in `app/.env`: there it would also limit ingestion and exports. |
| `API_CACHE_REDIS_URL` | `redis://redis:6379/2` | Redis database for the short `/api/series` and `/api/windrose` response cache. Empty turns the cache off. |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | `redis://redis:6379/0`, `redis://redis:6379/1` | The export queue (Celery on Redis). |
| `EXPORTS_DIR` | `/app/app/exports` | Where export CSVs are written, inside the shared `exports_data` volume. |
| `WORKER_LOG_TO_STDOUT` | off | `1` also prints the worker's logs to `docker compose logs worker`; they always go to `dashboard/backend/app/logs/`. |

## `dashboard/backend/app/.env` (backend, worker, export worker)

**Vendors and database**

| Variable | Default | Meaning |
|---|---|---|
| `HOBOLINK_API_URL` | required | LI-COR (HOBOlink) data API, e.g. `https://api.hobolink.licor.cloud/v1/data`. |
| `HOBOLINK_API_TOKEN` | required | LI-COR API token. |
| `HOBOLINK_LOGGERS` | required | LI-COR logger serial numbers, comma-separated. Only the first is queried: it is the weather station, and the water-level loggers report through it. |
| `WQ_API_URL` | required | WQData Live API, e.g. `https://www.wqdatalive.com/api/v1`. |
| `WQ_API_KEY` | required | WQData API key. |
| `WQ_DEVICE_ID` | required | WQData device (the water quality sonde). |
| `DATABASE_URL` | none | PostgreSQL URL. In Docker it is set from `BACKEND_DATABASE_URL` above; set it here only to run the backend or scripts outside Docker. |
| `RESTORE_CHECK_DATABASE_URL` | `DATABASE_URL` | The role the restore drill (`scripts/restore_check.py`, in `worker`) creates, restores into and drops its throwaway database with: the `well_restore` role's URL on the `postgres` maintenance database (`postgresql://well_restore:<password>@<the host in BACKEND_DATABASE_URL>/postgres`); it has `CREATEDB` and no access to the live tables ([Database roles](../dashboard/backend/README.md#database-roles)). `well_app` has no `CREATEDB`, so without it the drill stops. |

**API and exports**

| Variable | Default | Meaning |
|---|---|---|
| `DATA_MAX_ROWS` | `100000` | Most readings one `/api/data` request may return; more gets a 413 (see [the backend README](../dashboard/backend/README.md#api)). |
| `EXPORT_SYNC_ROW_THRESHOLD` | `100000` | Downloads up to this many readings are built while the visitor waits; larger ones are queued for `export_worker`. |
| `EXPORT_MAX_ROWS` | `5000000` | Largest queued export, in readings. |
| `EXPORT_MAX_ACTIVE_JOBS` | `6` | Queued or running exports at once, in total. |
| `EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER` | `2` | The same, per visitor (by IP address). |
| `EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER` | `6` | Jobs one visitor may start in an hour, finished ones included. |
| `EXPORT_MIN_FREE_MB` | `2048` | Free space to keep on the exports disk after an export's estimated size; exports that would go below it get a 507, and a file that grows into it is stopped and deleted. |
| `EXPORT_MAX_FILE_MB` | `1024` | Largest file one export may write; a larger one is stopped and deleted. `0`: no limit besides the free space. |
| `EXPORT_SYNC_MAX_SECONDS` | `45` | Longest a direct download may take to build (under gunicorn's 60 s timeout); a slower one is stopped (504). |
| `EXPORT_SOFT_TIME_LIMIT_SECONDS`, `EXPORT_HARD_TIME_LIMIT_SECONDS` | `900`, `1200` | An export past the soft limit is stopped and marked failed; past the hard limit its process is killed. |
| `EXPORT_WORKER_MAX_MEMORY_KB` | `512000` | An export worker process is replaced once a task leaves it using more memory than this. |
| `EXPORT_FILE_TTL_MINUTES` | `60` | How long a finished export can be downloaded before the hourly cleanup deletes it. |
| `EXPORT_POLL_INTERVAL_SECONDS` | `3` | How often the API tells the dashboard to check on a queued export. |

**Borealis and SharePoint** (details in [the backend README](../dashboard/backend/README.md#off-vm-copies-borealis-and-sharepoint))

`BOREALIS_URL` (the server, e.g. `https://borealisdata.ca`; a collection page such as
`https://borealisdata.ca/dataverse/WELL` also works, and only its scheme and host are used for API calls),
`BOREALIS_API_TOKEN` (made on the same server as `BOREALIS_URL`: demo and production tokens are separate),
`BOREALIS_UPLOAD_PERSISTENT_ID`, `BOREALIS_SAMPLING_PERSISTENT_ID`,
`BOREALIS_UPLOAD_DATAVERSE`, `BOREALIS_SAMPLING_DATAVERSE` (preflight only; no default), `BOREALIS_PUBLISH` (default `1`),
`BOREALIS_UPLOAD_FIRST_MONTH` (default `2026-10`); the older `DEMO_BOREALIS_URL`, `DEMO_BOREALIS_WC_PERSISTENT_ID` and
`DEMO_BOREALIS_AW_PERSISTENT_ID` are read when the new names are unset. `SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID`,
`SHAREPOINT_CLIENT_SECRET`, `SHAREPOINT_SITE` (the SharePoint copy is off while none of these four is set),
`SHAREPOINT_LIBRARY` (default `Documents`), `SHAREPOINT_FOLDER` (default `WELL sensor data`),
`SHAREPOINT_UPLOAD_FIRST_MONTH` (default: the Borealis one).

**Monitoring** (details in [the backend README](../dashboard/backend/README.md#monitoring); all off until set)

- Freshness check (`/health/data`): `HEALTH_MAX_AGE_HOURS` (default `3`), `HEALTH_MAX_AGE_HOURS_<GROUP>`,
  `HEALTH_QUIET_HOURS_<GROUP>` (Quality `18-12`, others off), `HEALTH_QUIET_MARGIN_HOURS_<GROUP>` (default `1`),
  `HEALTH_EXCLUDED_SERIES` (default `2577535:*`). `<GROUP>` is `WEATHER`, `LOGGER` or `QUALITY`.
- Heartbeats (Healthchecks.io ping URLs): `HEALTHCHECK_URL_INGESTION`, `_UPLOAD`, `_SHAREPOINT`, `_DOWNLOAD`,
  `_DIGEST`, `_ALERTS`. `HEALTHCHECK_URL_BACKUP` is for the nightly database backup and `HEALTHCHECK_URL_RESTORE`
  for the monthly restore drill (`RESTORE_CHECK_DAY`, default `2`; `RESTORE_CHECK_TOLERANCE_PCT`, default `2`; `RESTORE_CHECK_DATABASE_URL`, the role that creates and drops the throwaway database, e.g. a `well_restore` role where there is one)
  ([Database backups](../dashboard/backend/README.md#database-backups)). The worker logs a warning at start-up, and
  the daily digest lists, every one of these that isn't set.
- Email (digest and alerts): `ALERT_EMAILS`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`,
  `DIGEST_HOUR` (default `7`, Toronto time).
- Alert rules: `ALERT_STALE_HOURS`, `ALERT_STALE_HOURS_<GROUP>` (`3`, `3`, `2`), `ALERT_VENDOR_FAILURES` (`3`),
  `ALERT_REMINDER_HOURS` (`24`), `ALERT_SUSPECT_HOURS` (`6`), `ALERT_SUSPECT_VALUES` (`on`), `ALERT_CLEAR_MINUTES`
  (`30`), `ALERT_FLAP_CLEAR_MINUTES` (`180`), `ALERT_REOPEN_HOURS` (`6`), `ALERT_EXCLUDED_SERIES`,
  `ALERT_DASHBOARD_URL` (`https://welldash.mcmaster.ca/`).
- Sentry: `SENTRY_DSN` (unset turns reporting off), `SENTRY_ENVIRONMENT` (default `production`), `GIT_SHA` (optional
  release name). `SENTRY_COMPONENT` is set by `docker-compose.yml` for `worker` and `export_worker`.

**Set for one command only, never in a file**

| Variable | Meaning |
|---|---|
| `ALLOW_WIPE` | `1` lets a script that deletes every row of a table run (`clear_sampling_db.py`, `inject_sampling.py --full-reload`), e.g. `docker compose exec -e ALLOW_WIPE=1 worker python scripts/...`. Take a `pg_dump` first. |

`OPENAI_API_KEY` is unused while the AI analysis is disabled; it is only needed if that feature is turned back on (see [AI analysis](../dashboard/backend/README.md#ai-analysis-disabled)).

## Dashboard (Next.js)

| Variable | Kind | Default | Meaning |
|---|---|---|---|
| `FLASK_API_URL` | build time only | from `BACKEND_INTERNAL_URL` | Where the API routes in `src/pages/api/` send requests. The `env` block in `next.config.ts` inlines it into the build, server code included, so the run-time value compose also sets is never read: after changing `BACKEND_INTERNAL_URL`, rebuild with `docker compose up -d --build --no-deps dashboard`. For `next dev` outside Docker, set it to your backend, e.g. `http://localhost:5000`. |
| `TRUSTED_PROXY_IPS` | run time | see above | Set by `docker-compose.yml` from the root `.env`. |
| `RATE_LIMIT_BURST`, `RATE_LIMIT_PER_MINUTE` | run time | `600`, `600` | API requests one visitor's address may make at once, and per minute after that ([Rate limits](../dashboard/frontend/README.md#rate-limits-and-security-headers)). Not set by `docker-compose.yml`: add them to the dashboard's `environment:` to change them. `0` turns a limit off. |
| `RATE_LIMIT_SLOW_BURST`, `RATE_LIMIT_SLOW_PER_MINUTE` | run time | `120`, `120` | The same for slow requests (wind rose, `/api/data`, `/api/samples`, `/api/series` without `bucket=`, export estimates, direct exports, new export jobs). |
| `RATE_LIMIT_SLOW_CONCURRENT` | run time | `6` | Slow requests one address may have in flight at once, each until the backend has finished with it. |
| `RATE_LIMIT_DOWNLOAD_CONCURRENT` | run time | `2` | Export downloads one address may have in flight at once. |
| `PROXY_BODY_MAX_MS` | run time | `1800000` | The longest a response may take to send before it is cut off. |
| `NEXT_PUBLIC_WP_HOME` | build arg | `https://well.mcmaster.ca` | The WordPress site the header links to. |
| `NEXT_PUBLIC_SENTRY_DSN` | build arg | the dashboard project's key | Empty turns browser and server error reporting off. |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | build arg | `production` | Use `development` for local images. |
| `NEXT_PUBLIC_GOATCOUNTER_ENDPOINT` | build arg | `https://well.goatcounter.com/count` | Where page views are counted ([Visitor counts](../dashboard/frontend/README.md#visitor-counts-goatcounter)). Counts are sent only from welldash.mcmaster.ca, whatever the value; empty leaves counting out of the build. |

`docker-compose.yml` passes only two build args, `FLASK_API_URL` (from `BACKEND_INTERNAL_URL`) and
`NEXT_PUBLIC_FLASK_API_URL`. The other four come from the `ARG` defaults in `dashboard/frontend/Dockerfile`. To change
one, edit that default, build by hand with `docker build --build-arg NAME=value dashboard/frontend`, or add it under
the dashboard's `build: args:` in `docker-compose.yml`. Env files are kept out of the image build (`.dockerignore`),
so `.env.local` can't set any of them.

## WordPress backup (`wordpress/backup.sh`, set in the crontab line)

| Variable | Default | Meaning |
|---|---|---|
| `HEALTHCHECK_URL_WP_BACKUP` | none | Healthchecks.io ping URL: `<url>/start` when a backup begins, `<url>` on success, `<url>/fail` on a failure. |
| `WP_BACKUP_DIR` | `wp-backups/` in the repository root | Where backups go. |
| `WP_BACKUP_KEEP_DAILY`, `WP_BACKUP_KEEP_WEEKLY`, `WP_BACKUP_KEEP_MONTHLY` | `7`, `8`, `12` | Retention: the newest backup of each of that many days, ISO weeks and months is kept. |
| `WP_BACKUP_MIN_FREE_MB` | `2048` | Free space to leave after a backup the size of the last one; the run refuses to start otherwise. |

Details in [wordpress/README.md](../wordpress/README.md#backups).

## Deploy script (`deploy.sh`, set in the crontab line)

| Variable | Default | Meaning |
|---|---|---|
| `DEPLOY_HEALTHCHECK_URL` | none | Healthchecks.io ping URL: pinged on success, `<url>/fail` on a failure or a held commit. |
| `DEPLOY_BRANCH`, `DEPLOY_REMOTE` | `main`, `origin` | What is deployed. |
| `DEPLOY_LOG` | `deploy.log` next to the script | Log file. |
| `DEPLOY_STATE_DIR` | `.deploy-state` next to the script (git-ignored) | The lock, the last problem reported, the commit the containers were last built from, a marker while a deploy runs, and the last commit rolled back. Earlier versions kept the lock and state in `/tmp`; the first run moves them here, and once a run has ended well the old `/tmp` files are ignored. |
| `DEPLOY_SITE_HOST` | `127.0.0.1` | The address the health checks call ports 8080 and 8081 on. Set it when `WORDPRESS_BIND` and `DASHBOARD_BIND` publish those ports on one address that isn't the loopback. |
| `DEPLOY_CI_WAIT_HOURS` | `3` | How long `--auto` waits for CI to finish on a commit before it reports it (a `/fail` ping and a `FAILED` line). |
| `GITHUB_REPO` | `ARCO-Lab/WELLWebsite` | Where `--auto` reads CI results. |

## Tests

| Variable | Meaning |
|---|---|
| `TEST_POSTGRES_URL`, `MIGRATE_TEST_DATABASE_URL` | Throwaway PostgreSQL databases for the backend tests that need one; without them those tests are skipped locally (CI fails if they are skipped). |
| `E2E_DATABASE_URL`, `E2E_BASE_URL` | Database and dashboard address for the end-to-end tests in `dashboard/e2e/`. |

The API canary's GitHub repository secrets are listed in [the API canary section](../.github/workflows/README.md#api-canary),
and the daily maintainer's (`CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`, `WELL_MAINTAINER_PAT`, `SENTRY_API_TOKEN`,
the SMTP settings and `ALERT_EMAILS`, and the `MAINTAINER_MODEL` variable) in [its section](../.github/workflows/README.md#daily-maintainer).
welldash²'s `OPS_*` settings (root `.env`) are in [its README](../dashboard/backend/app/ops/README.md#settings).
