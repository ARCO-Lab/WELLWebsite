# Configuration

Every setting the code reads from the environment, where it goes, and its default. No env file is committed: on the
VM they sit in the checkout, ignored by git. Longer explanations of some groups are in the README (linked below).

| File | Read by |
|---|---|
| `.env` (repository root) | `docker compose`, which substitutes its values into `docker-compose.yml`. |
| `dashboard/backend/app/.env` | The `backend`, `worker` and `export_worker` containers (`env_file`). Scripts run outside Docker read it too: `config.py` calls `load_dotenv()`, which finds the file next to it. |
| `dashboard/frontend/.env.local` | The `dashboard` container at run time (`env_file`). It must exist for `docker compose` to start, but it can be empty. |

A variable that a service's `environment:` block in `docker-compose.yml` sets wins over the same name in
`dashboard/backend/app/.env`. So the variables in the first table below are set in the root `.env`, not in `app/.env`.

After changing an env file, recreate the containers that read it, e.g. `docker compose up -d --no-deps backend worker
export_worker`. `NEXT_PUBLIC_*` values are built into the dashboard, so they need a rebuild
(`docker compose up -d --build --no-deps dashboard`).

## Root `.env` (docker compose)

| Variable | Default | Meaning |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | required | Root password of the WordPress MySQL container (`db`). |
| `WORDPRESS_DB_PASSWORD` | required | Password of the MySQL user `wordpress`, used by `db` and `wordpress`. |
| `DEPLOYMENT` | `DEV` | `PROD` makes the WordPress theme force HTTPS URLs (`home/wp-content/themes/well/functions.php`). |
| `WP_HOME`, `WP_SITEURL` | none | Passed into the `wordpress` container. The stock image doesn't apply them by itself; they only take effect if `home/wp-config.php` (not in the repository) reads them. |
| `DASHBOARD_URL` | `https://welldash.mcmaster.ca` | The dashboard address the WordPress theme links to and embeds. |
| `BACKEND_DATABASE_URL` | required | PostgreSQL URL for `backend`, `worker` and `export_worker` (it becomes their `DATABASE_URL`). PostgreSQL runs on the VM itself, not in Docker, so this points at the host (see "Host firewall" in the README). |
| `BACKEND_PORT` | must be `5000` | Only feeds the backend's `expose:` line. Gunicorn always listens on 5000 (`dashboard/backend/Dockerfile`), so any other value breaks the stack. |
| `BACKEND_INTERNAL_URL` | none (use `http://backend:5000`) | How the dashboard's API routes reach Flask. It becomes the dashboard's `FLASK_API_URL`. |
| `NEXT_PUBLIC_FLASK_API_URL` | none | Passed to the dashboard build and container, but no code reads it. |
| `DASHBOARD_PORT` | none (use `8081`) | Host port of the dashboard. `deploy.sh`'s health checks assume 8081. |
| `TRUSTED_PROXY_IPS` | `130.113.68.30` | Reverse proxies whose `X-Forwarded-For` the dashboard believes, comma-separated. The default is McMaster's `haproxy.cas.mcmaster.ca`. Set but empty trusts none. See `dashboard/frontend/src/lib/clientIp.ts`. |
| `DB_STATEMENT_TIMEOUT_MS` | `25000` | API queries running longer are cancelled (the API answers 504). Backend container only; `0` turns it off. Don't put it in `app/.env`: there it would also limit ingestion and exports. |
| `API_CACHE_REDIS_URL` | `redis://redis:6379/2` | Redis database for the short `/api/series` response cache. Empty turns the cache off. |
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

**API and exports**

| Variable | Default | Meaning |
|---|---|---|
| `DATA_MAX_ROWS` | `300000` | Most readings one `/api/data` request may return; more gets a 413 (see the README). |
| `EXPORT_SYNC_ROW_THRESHOLD` | `100000` | Downloads up to this many readings are built while the visitor waits; larger ones are queued for `export_worker`. |
| `EXPORT_MAX_ROWS` | `5000000` | Largest queued export, in readings. |
| `EXPORT_MAX_ACTIVE_JOBS` | `6` | Queued or running exports at once, in total. |
| `EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER` | `2` | The same, per visitor (by IP address). |
| `EXPORT_SOFT_TIME_LIMIT_SECONDS`, `EXPORT_HARD_TIME_LIMIT_SECONDS` | `900`, `1200` | An export past the soft limit is stopped and marked failed; past the hard limit its process is killed. |
| `EXPORT_WORKER_MAX_MEMORY_KB` | `512000` | An export worker process is replaced once a task leaves it using more memory than this. |
| `EXPORT_FILE_TTL_MINUTES` | `60` | How long a finished export can be downloaded before the hourly cleanup deletes it. |
| `EXPORT_POLL_INTERVAL_SECONDS` | `3` | How often the API tells the dashboard to check on a queued export. |

**Borealis and SharePoint** (details in the README's "Off-VM copies" section)

`BOREALIS_URL`, `BOREALIS_API_TOKEN`, `BOREALIS_UPLOAD_PERSISTENT_ID`, `BOREALIS_SAMPLING_PERSISTENT_ID`,
`BOREALIS_UPLOAD_DATAVERSE`, `BOREALIS_SAMPLING_DATAVERSE`, `BOREALIS_PUBLISH` (default `1`),
`BOREALIS_UPLOAD_FIRST_MONTH` (default `2026-10`); the older `DEMO_BOREALIS_URL`, `DEMO_BOREALIS_WC_PERSISTENT_ID` and
`DEMO_BOREALIS_AW_PERSISTENT_ID` are read when the new names are unset. `SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID`,
`SHAREPOINT_CLIENT_SECRET`, `SHAREPOINT_SITE` (the SharePoint copy is off while none of these four is set),
`SHAREPOINT_LIBRARY` (default `Documents`), `SHAREPOINT_FOLDER` (default `WELL sensor data`),
`SHAREPOINT_UPLOAD_FIRST_MONTH` (default: the Borealis one).

**Monitoring** (details in the README's "Monitoring" section; all off until set)

- Freshness check (`/health/data`): `HEALTH_MAX_AGE_HOURS` (default `3`), `HEALTH_MAX_AGE_HOURS_<GROUP>`,
  `HEALTH_QUIET_HOURS_<GROUP>` (Quality `18-12`, others off), `HEALTH_QUIET_MARGIN_HOURS_<GROUP>` (default `1`),
  `HEALTH_EXCLUDED_SERIES` (default `2577535:*`). `<GROUP>` is `WEATHER`, `LOGGER` or `QUALITY`.
- Heartbeats (Healthchecks.io ping URLs): `HEALTHCHECK_URL_INGESTION`, `_UPLOAD`, `_SHAREPOINT`, `_DOWNLOAD`,
  `_DIGEST`, `_ALERTS`. `HEALTHCHECK_URL_BACKUP` is for a backup job on the host; no code here reads it.
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
| `ALLOW_WIPE` | `1` lets a script that deletes every row of a table run (`inject_historical.py`, `clear_sampling_db.py`, `inject_sampling.py --full-reload`), e.g. `docker compose exec -e ALLOW_WIPE=1 worker python scripts/...`. Take a `pg_dump` first. |

`OPENAI_API_KEY` is only needed if the disabled AI analysis is turned back on (see the README's "AI Analysis").

## Dashboard (Next.js)

| Variable | Kind | Default | Meaning |
|---|---|---|---|
| `FLASK_API_URL` | build arg and run time | from `BACKEND_INTERNAL_URL` | Where the API routes in `src/pages/api/` send requests. For `next dev` outside Docker, set it to your backend, e.g. `http://localhost:5000`. |
| `TRUSTED_PROXY_IPS` | run time | see above | Set by `docker-compose.yml` from the root `.env`. |
| `NEXT_PUBLIC_WP_HOME` | build arg | `https://well.mcmaster.ca` | The WordPress site the header links to. |
| `NEXT_PUBLIC_SENTRY_DSN` | build arg | the dashboard project's key | Empty turns browser and server error reporting off. |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | build arg | `production` | Use `development` for local images. |

Build args are set in `dashboard/frontend/Dockerfile` and `docker-compose.yml`; env files are kept out of the image
build (`.dockerignore`), so `.env.local` can't set them.

## Deploy script (`deploy.sh`, set in the crontab line)

| Variable | Default | Meaning |
|---|---|---|
| `DEPLOY_HEALTHCHECK_URL` | none | Healthchecks.io ping URL: pinged on success, `<url>/fail` on a failure or a held commit. |
| `DEPLOY_BRANCH`, `DEPLOY_REMOTE` | `main`, `origin` | What is deployed. |
| `DEPLOY_LOG` | `deploy.log` next to the script | Log file. |
| `GITHUB_REPO` | `ARCO-Lab/WELLWebsite` | Where `--auto` reads CI results. |

## Tests

| Variable | Meaning |
|---|---|
| `TEST_POSTGRES_URL`, `MIGRATE_TEST_DATABASE_URL` | Throwaway PostgreSQL databases for the backend tests that need one; without them those tests are skipped locally (CI fails if they are skipped). |
| `E2E_DATABASE_URL`, `E2E_BASE_URL` | Database and dashboard address for the end-to-end tests in `dashboard/e2e/`. |

The API canary's GitHub repository secrets are listed in the README's "API canary" section.
