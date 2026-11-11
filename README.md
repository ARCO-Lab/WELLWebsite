# WELL Environmental Data Platform

Part of the McMaster Watershed Ecosystems Living Lab (WELL). This platform fetches, stores, and visualizes environmental sensor data from weather and water quality stations, serving near real-time insights through an interactive web dashboard.

**Live:** [welldash.mcmaster.ca](https://welldash.mcmaster.ca) | **WordPress Home:** [well.mcmaster.ca](https://well.mcmaster.ca)

---

## Overview

The platform consists of two main components:

1. **WELL Environmental Sensor Dashboard** — A standalone Next.js dashboard with a Flask backend, hosted at `welldash.mcmaster.ca` and embedded into the WordPress site via iframe.
2. **WELL WordPress Home Page** — A custom PHP WordPress theme at `well.mcmaster.ca` with a banner carousel, responsive imagery, and links to the dashboard.

Both apps run as separate Docker containers on a Linux VM, fronted by a single Nginx reverse proxy with unified TLS.

---

## Architecture
<img width="1024" height="559" alt="image" src="https://github.com/user-attachments/assets/ad6d07d8-6c18-4ddd-8cef-f761087d6675" />

### Frontend (Dashboard)
- **Next.js** (pages router) with **TypeScript**, **React**, and **TailwindCSS**
- **Highcharts** for rich visualizations: time-series charts, wind-rose, and interactive station map
- Custom React hooks encapsulate data fetching and memoized filter state (station, parameter, date range)
- Performance: SSR, code-splitting, memoization, debounced inputs, optimized static assets
- Frontend state synchronized via URL query parameters (shareable/linkable views)

### Backend
- **Flask** WSGI app served by **Gunicorn** (3 workers)
- REST endpoints for: `stations`, `parameters`, `metrics`, `aggregate`, `download`, `ai/analyze`, `health`
- Smart caching: DB-level query tuning + application caching + HTTP cache headers (ETag/Cache-Control)
- Optional Nginx proxy cache for heavy CSV/static responses
- Config via environment variables; request/ingestion activity logging for observability

### Storage
- **PostgreSQL** primary datastore for time-series and sampling data
- Indexes on station identifiers, parameters, and timestamps for fast queries
- Downsampling jobs materialize reduced-resolution series for commonly requested windows
- Staging area supports CSV/Excel imports; logs area persists operational logs

### WordPress Home Page
- Custom PHP template under `wp-content/themes/well`
- **Bootstrap** grid and utility classes for responsive layout
- **Flickity** banner carousel with adaptive height
- Responsive images via `srcset/sizes`; accessible alt text throughout
- Links to a dedicated page that embeds the dashboard via iframe

### Hosting & Infrastructure
- Both apps containerized with **Docker**
- **Nginx** reverse proxy: TLS termination, host/path routing to WordPress or dashboard container
- `frame-ancestors` / CSP configured to permit iframe embedding between apps
- CORS constrained to trusted origins; secrets injected via environment variables

**Host firewall (required).** PostgreSQL runs on the VM itself, not in Docker, and the containers connect to it on the host's IP, port 5432. The host's iptables service loads `/etc/sysconfig/iptables` at boot, and that file must contain this line above its final `-A INPUT -j REJECT` line:

```
-A INPUT -s 10.20.0.0/16 -p tcp -m tcp --dport 5432 -m comment --comment "WELL dashboard: Docker containers to host PostgreSQL (required)" -j ACCEPT
```

Without it, every container fails with "No route to host" after the next reboot, and ingestion stops. To add it without a reboot as well, run `sudo iptables -I INPUT -s 10.20.0.0/16 -p tcp --dport 5432 -j ACCEPT`. Never run `systemctl restart iptables`, which wipes Docker's own rules until Docker restarts. Never run `iptables-save > /etc/sysconfig/iptables` either, which would save Docker's temporary rules into the file.

---

## Data Sources & APIs

| Source | Type |
|---|---|
| HoboLink (Licor Cloud API) | Automated ingestion & scheduled updates |
| WQData Live API | Automated ingestion & scheduled updates |
| OpenAI API | AI analysis over downsampled series |
| Borealis | Nightly cron export/upload |
| SharePoint | Nightly cron export/upload |

### API canary

`.github/workflows/canary.yml` runs `dashboard/backend/app/scripts/api_canary.py` every day at 11:17 UTC. It makes one small request to each source and checks both the HTTP status and that the response still has the fields ingestion reads:

- **LI-COR**: the last 6 hours for the first logger in `HOBOLINK_LOGGERS` (`data[]` records with `sensor_sn`, and a `timestamp` and numeric `value` on every record ingestion stores; battery and unknown logger channels are skipped, as ingestion skips them).
- **WQData**: the last 6 hours for `WQ_DEVICE_ID`, as exactly one request, because WQData's hourly quota is shared with the 10-minute ingestion (`data[]` points with `timestamp` and `values[].parameterId`, plus `info` for paging).
- **Borealis**: the metadata of both datasets (`DEMO_BOREALIS_AW_PERSISTENT_ID`, which downloads read, and `DEMO_BOREALIS_WC_PERSISTENT_ID`, which uploads add to) with `BOREALIS_API_TOKEN` (`data.latestVersion` with `versionState` and `files[].dataFile`). This proves the token is accepted and can read both datasets, not that it may still add files: the monthly upload also needs edit rights on the upload dataset, which the canary doesn't test.

It prints one `OK` or `FAIL` line per source (HTTP status and reason only, never URLs, keys or response bodies) and fails the run if any source fails. An empty response counts as a failure too, since ingestion would have nothing to store. Every failure shows on the repository's Actions tab. Who GitHub emails about it (if their notification settings include Actions):

- A scheduled run: the person who last changed the workflow's `cron` line, or, once the workflow has been disabled and re-enabled, the person who re-enabled it.
- A manual run: whoever started it.
- Nobody, once GitHub has disabled the schedule: it turns scheduled workflows off after 60 days without activity in the repository, and a disabled schedule sends nothing. After a quiet period, check the Actions tab and re-enable the workflow there.

Using it:

- **Run it by hand**: Actions → API canary → Run workflow. On the VM, once the image includes the script: `docker compose exec worker python scripts/api_canary.py`.
- **When a key is rotated**, update the matching repository secret (Settings → Secrets and variables → Actions) as well as `dashboard/backend/app/.env` on the VM, then run the canary by hand. The secrets are `HOBOLINK_API_URL`, `HOBOLINK_API_TOKEN`, `HOBOLINK_LOGGERS`, `WQ_API_URL`, `WQ_API_KEY`, `WQ_DEVICE_ID`, `DEMO_BOREALIS_URL`, `BOREALIS_API_TOKEN`, `DEMO_BOREALIS_AW_PERSISTENT_ID` and `DEMO_BOREALIS_WC_PERSISTENT_ID`. The Borealis token and the WQData key are both due for rotation.
- **Tests**: `dashboard/backend/tests/test_api_canary.py` (no network). The canary keeps copies of a few constants from `utils/parsers.py` so the workflow needs only `requests`; CI runs the tests that check those copies still match on every pull request, with the rest of the backend tests (by hand, from `dashboard/backend`: `python -m unittest discover -s tests -t .`).

---

## Automation

Cron orchestrates all scheduled tasks:
- **Ingestion**: HoboLink and WQData pulls on schedule
- **Historical backfills**: Retroactive data imports
- **Downsampling**: Bucket-based reduced-resolution series for chart performance
- **Exports**: Nightly CSV exports to Borealis and SharePoint with checksum verification and logging
- **Health checks**: Readiness endpoints for external monitors

### Deploying

The VM runs `main`. On the VM, `./deploy.sh`:
- pulls `main`;
- rebuilds only the services whose files changed:
  - `dashboard/frontend/` → `dashboard`;
  - `dashboard/backend/` → `backend`, `worker`, `export_worker`;
  - `docker-compose.yml` → everything;
  - `home/` needs nothing: the `wordpress` service is the stock `wordpress` image with `home/` bind-mounted, so it's live once pulled.
- checks the site: `/api/latest`, the dashboard home page (both on port 8081) and the WordPress home page (port 8080). If `worker` or `export_worker` was rebuilt, it also checks a minute later that the container is still running and hasn't restarted (compose restarts crashing workers, so "running" alone proves nothing);
- rolls back to the previous commit if any check fails.

If the site is already unhealthy before a deploy, `--auto` doesn't deploy (so the new commit isn't blamed and rolled back); `./deploy.sh` by hand deploys anyway and doesn't roll back.

Each run is logged in `deploy.log` (best effort: a log it can't write never stops a deploy halfway), and any failure, expected or not, logs a `FAILED:` line. Over 5 MB, `deploy.log` is moved to `deploy.log.1` and a new one started. `./deploy.sh --dry-run` only shows what would happen: no log, no pings, no state. It refuses to run over local edits to tracked files, so change the VM only through `main`.

`./deploy.sh --auto` deploys a new commit on `main` only once all its CI checks have passed (`.github/workflows/ci.yml`). It holds changes that need a person, logging them and leaving them for you:
- a new database migration;
- `docker-compose.yml`;
- a WordPress core update, which needs its database update run from wp-admin.

Deploy those with `./deploy.sh`. `--auto` reports each problem once, not every 5 minutes: a held commit, failed CI, local edits, a non-fast-forward or a merge git refuses, a GitHub API error or unreadable reply, a fetch error, an already-unhealthy site, or any other command failing (keyed by its line). A commit that was deployed and rolled back isn't retried, whatever else fails in between; a newer commit on `main`, or `./deploy.sh` by hand, moves past it.

#### Before adding the cron line

Check these on the VM first; each is something `--auto` relies on:
- The tracked tree is clean (`git status --porcelain --untracked-files=no` prints nothing) and `find home ! -user elankuml | head` prints nothing, so a pull can update every file.
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

`DEPLOY_HEALTHCHECK_URL` is optional. The script pings it on success (up to date, or deployed and healthy) and pings `<url>/fail` on a failure or a held commit. Runs that are waiting (CI still running, a problem already reported, another deploy in progress) don't ping. So set the Healthchecks period to 5 minutes and the grace time longer than CI takes (30 minutes is safe), or a slow CI run will look like an outage.

---

## AI Analysis

> **Currently disabled.** The UI entry points and API routes are commented out, each marked `AI ANALYSIS DISABLED`. To turn the feature back on, search the code for that marker, uncomment those blocks, delete the four 404 stubs at the top of `dashboard/frontend/src/pages/api/analysis/*.ts`, and set `OPENAI_API_KEY`.

An API endpoint aggregates/downsamples a series and sends a bounded prompt to the OpenAI API to generate human-readable summaries of trends, anomalies, and ranges. The frontend renders the output inside an analysis modal and allows exporting the narrative.

---

## Python Environment Setup

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate
# or
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
HOBOLINK_API_URL=https://api.hobolink.licor.cloud/v1/data
HOBOLINK_API_TOKEN=your-api-token-here
HOBOLINK_LOGGERS=weatherlogger,waterlogger1,waterlogger2,...,waterlogger5

WQDATA_API_URL=https://www.wqdatalive.com/api/v1
WQDATA_API_KEY=your-api-key-here
WQDATA_DEVICE_ID=your-device-id-here
```

> `HOBOLINK_LOGGERS` should be the serial number of each logger, comma-separated.

---

## Monitoring

Three simple pieces, all optional and all off until configured. On the VM their settings go in `dashboard/backend/app/.env` (the backend and worker read it); recreate the containers after changing it (`docker compose up -d --no-deps backend worker`).

**Data freshness check.** `GET /health/data` on the backend, passed through by the dashboard at `https://welldash.mcmaster.ca/api/health/data`, lists for each group (Weather, Logger, Quality) and each series (station and measurement) the newest `recorded_at` and its age in minutes. It answers **200** when every live series is within its limit and **503** with a `stale` list otherwise (also 503 if the database can't be read or a setting below is invalid). It walks the same index as `/api/latest`, so polling it every few minutes costs nothing noticeable.

| Variable | Default | Meaning |
|---|---|---|
| `HEALTH_MAX_AGE_HOURS` | `3` | Limit for any group without its own. LI-COR data (Weather, Logger) arrives about an hour late, so 3 h means two missed uploads. |
| `HEALTH_MAX_AGE_HOURS_WEATHER`, `_LOGGER`, `_QUALITY` | the above | Limit for one group. |
| `HEALTH_QUIET_HOURS_QUALITY` | `18-12` | Site-time hours (`START-END`, may wrap midnight) when the group's device is known to go silent. During them a series counts as fresh if its newest reading is at most `HEALTH_QUIET_MARGIN_HOURS_QUALITY` older than their start. The WQData sonde usually stops between 18:10 and 22:30 and resumes between 08:20 and 11:30. `off` disables it. `HEALTH_QUIET_HOURS_WEATHER` and `_LOGGER` work the same way and are off by default. |
| `HEALTH_QUIET_MARGIN_HOURS_QUALITY` | `1` | The margin for the quiet hours: with the defaults, a sonde whose last reading was before 17:00 is reported as stale all night (one that stopped at 15:30 is caught; one that stopped for the night at 18:10 isn't). Also `_WEATHER`, `_LOGGER`. |
| `HEALTH_EXCLUDED_SERIES` | `2577535:*` | Series that are reported but never count as stale: `station:measurement` or `station:*`, comma-separated. The default is Logger 5, whose readings stopped in 2025. Set it to an empty value to check everything. |

**Job heartbeats.** The worker pings a [Healthchecks.io](https://healthchecks.io) check after each job, and Healthchecks emails the account owner when a check reports a failure or stops being pinged, so no SMTP is needed for these. A ping times out after 5 s and never stops the job. Unset variables mean no ping.

| Variable | Pinged |
|---|---|
| `HEALTHCHECK_URL_INGESTION` | After every 10-minute ingestion run; `/fail` when LI-COR or WQData raised an error. |
| `HEALTHCHECK_URL_UPLOAD` | After the monthly Borealis upload (02:00 on the 1st, and daily retries); `/fail` if a month didn't go up. Days with nothing to upload don't ping. |
| `HEALTHCHECK_URL_DIGEST` | After the daily digest; `/fail` if it crashed or couldn't send. |
| `HEALTHCHECK_URL_BACKUP` | Reserved for the database backup job on the host, which is outside the containers: end it with `curl -fsS -m 10 --retry 3 -o /dev/null "$HEALTHCHECK_URL_BACKUP"`. |

To set them up, sign in to Healthchecks.io with the address that should get the alerts (the free plan is enough), create one check per job, and copy each check's ping URL into the matching variable:
- **WELL ingestion**: Simple schedule, period 10 minutes, grace 30 minutes.
- **WELL monthly upload**: Cron `0 2 1 * *`, time zone America/Toronto, grace 4 hours (an upload may take up to 2 h).
- **WELL daily digest**: Cron `0 7 * * *` (or your `DIGEST_HOUR`), time zone America/Toronto, grace 1 hour.
- **WELL backup**, if the backup job pings it: its own schedule, grace about an hour.

**Uptime monitor.** Point any external HTTP monitor that alerts on a non-2xx status (e.g. UptimeRobot's free plan, 5-minute interval) at `https://welldash.mcmaster.ca/api/health/data`, with the owner's email as the alert contact. It goes red both when the site is down and when data stops arriving.

**Daily digest.** `scripts/daily_digest.py` (run by the worker every day at `DIGEST_HOUR`, Toronto time) writes a plain-text summary of the last 24 h: stale series; implausible values (dissolved oxygen about 0 mg/L, a logger with about 0 m of water over its sensor, readings outside physical ranges, a quality probe stuck on one value, except TSS and turbidity at exactly 0, which is normal in clear water); rows and time slots per group against the 10-minute cadence, with gaps over 30 minutes; WQData primary power min/max and last contact (one WQData request, since WQData's hourly quota is shared with ingestion); and every series' newest reading. It emails the digest when SMTP is configured and prints it otherwise (the worker logs it to `logs/daily_digest.log`). Run it by hand with `python scripts/daily_digest.py --dry-run` (print only) or `--no-wqdata` (no WQData request).

| Variable | Default | Meaning |
|---|---|---|
| `ALERT_EMAILS` | none | Recipients, comma-separated. |
| `SMTP_HOST`, `SMTP_PORT` | none | Mail relay. The digest is emailed only when both are set (and `ALERT_EMAILS` isn't empty). Port 465 uses TLS; other ports use STARTTLS when the server offers it. A login (`SMTP_USER` and `SMTP_PASSWORD`) is only sent over TLS: if the relay offers no STARTTLS, the digest refuses to log in and fails. With SMTP set but no valid address in `ALERT_EMAILS`, the digest also fails, so the digest heartbeat reports it. |
| `SMTP_USER`, `SMTP_PASSWORD` | none | Login, used only when both are set. |
| `SMTP_FROM` | `SMTP_USER` | Sender address; required if there's no `SMTP_USER`. |
| `DIGEST_HOUR` | `7` | Hour (0-23, Toronto time) the worker builds the digest. Not 1 or 2: clocks change at 02:00, so on those days the hour happens twice or not at all. An invalid value is logged and no digest runs. |

```bash
# dashboard/backend/app/.env (example)
HEALTHCHECK_URL_INGESTION=https://hc-ping.com/your-check-uuid
HEALTHCHECK_URL_UPLOAD=https://hc-ping.com/your-check-uuid
HEALTHCHECK_URL_DIGEST=https://hc-ping.com/your-check-uuid
ALERT_EMAILS=someone@mcmaster.ca,someone-else@mcmaster.ca
# SMTP_HOST=smtp.example.mcmaster.ca
# SMTP_PORT=587
# SMTP_FROM=welldash@mcmaster.ca
```

---

## Data Upload (Manual)

```bash
python upload_data.py --year 2023 --month 7
```

---

## Database migrations

New tables are created by `db.create_all()` (`dashboard/backend/app/db/init_db.py`), which never changes a table that already exists. Changes to existing tables (an index, a new column) go in a numbered SQL file in `dashboard/backend/app/db/migrations/` (`0001_name.sql`, `0002_name.sql`, ...), applied with `scripts/migrate.py`. It runs the files that haven't run yet, in order, and records each in the `schema_migrations` table so none runs twice. Nothing applies them automatically; on the VM, run them by hand:

```bash
cd ~/WELLWebsite
./git_pull.sh && docker compose up -d --build --no-deps backend   # the migration files are baked into the image
pg_dump "<database url>" -Fc -f ~/welldb-$(date +%F).dump        # a backup first, kept outside the repo
docker compose exec backend python scripts/migrate.py --status   # what has run and what is pending
docker compose exec backend python scripts/migrate.py --dry-run  # the SQL that would run
docker compose exec backend python scripts/migrate.py            # apply
```

- The first step is needed because `docker compose exec backend` only sees the files in the running image. Rebuilding restarts gunicorn, so the API returns errors for a few seconds.
- Each file runs in one transaction, so a failed migration leaves nothing half-done. A file whose first line is `-- migrate: no-transaction` runs outside a transaction instead, as `CREATE INDEX CONCURRENTLY` requires; such a file holds one statement.
- Indexes are built with `CONCURRENTLY`, which doesn't block reads or inserts, so the index build itself needs no downtime: the site and the ingestion keep running while it builds.
- If a concurrent index build fails part way, PostgreSQL leaves an INVALID index behind. When that index is one the migration names, the runner refuses to record the migration, names the index and exits with an error: drop it with `DROP INDEX CONCURRENTLY <name>;` and run the migration again. Invalid indexes the migration doesn't name only get a warning.
- A second run at the same time refuses to start ("another migrate.py run holds the lock", a PostgreSQL advisory lock) and exits with an error; run it again once the first has finished. It doesn't wait, because a waiting run would stall the first run's concurrent index build.
- Never rename or renumber a file once it has been applied: the runner identifies migrations by file name and would run it again. Two files with the same number are refused.
- Dated files such as `2026-11-10_swap_air_soil_temperature.sql` are one-off data fixes, run by hand with `psql` as their comments describe; the runner ignores them.
- When a migration changes the schema, change `db/models.py` to match, so a fresh database built by `create_all()` gets the same result.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript, TailwindCSS, Highcharts |
| Backend | Python, Flask, Gunicorn (WSGI) |
| Database | PostgreSQL |
| Infrastructure | Docker, Nginx, Linux VM |
| CMS | WordPress (PHP, Bootstrap, Flickity) |
| APIs | HoboLink, WQData, OpenAI, Borealis, SharePoint |
| Automation | Cron, shell scripts |

---

## Terms & Conditions

The WELL Environmental Data Platform and the associated WordPress site are intended to provide environmental monitoring information, research support, and public-facing project communication.

- **Informational use only:** Data, charts, summaries, and downloadable files are provided for informational, educational, and research-support purposes and should not be treated as legal, regulatory, engineering, safety-critical, or emergency-response advice.
- **No guarantee of uninterrupted service:** While the platform is designed for near real-time availability, uptime, data freshness, and feature availability are not guaranteed at all times because of scheduled maintenance, upstream API outages, network issues, or infrastructure failures.
- **Data accuracy and completeness:** Sensor readings, derived metrics, AI-generated summaries, and exports may contain delays, gaps, approximations, processing errors, or third-party source inconsistencies. Users should independently validate important findings before relying on them.
- **Acceptable use:** Users must not misuse the dashboard, APIs, iframe integration, or WordPress site, including by attempting unauthorized access, bypassing rate limits, scraping protected content, interfering with service availability, or introducing malicious content.
- **Third-party services:** The platform depends on external providers including HoboLink, WQData Live, OpenAI, Borealis, SharePoint, WordPress, and hosting/network services. Their availability and terms may affect platform behavior.
- **Intellectual property:** Project branding, code, visual assets, and original content remain subject to the rights and licenses defined by the WELL project, McMaster University, and any third-party licensors.
- **Changes to the service:** Features, APIs, visualizations, exports, and access controls may be updated, restricted, or removed without notice as the platform evolves.

> These terms are a project-level draft for documentation purposes and should be reviewed by McMaster/WELL stakeholders before being published as the official site terms.

---

## Privacy Policy

The platform should publish a simple privacy notice covering both the dashboard and the WordPress site.

- **Operational data collected:** The system may log request metadata such as IP address, timestamp, requested path, response status, browser/user-agent details, and application errors for security, troubleshooting, and performance monitoring.
- **Analytics and observability:** Monitoring tools, logs, metrics, and alerts may be used to understand uptime, failures, and performance across Nginx, Flask, Next.js, WordPress, and PostgreSQL.
- **User-submitted or uploaded files:** Research uploads such as CSV or Excel sampling files may contain user-supplied content and should be handled as institutional research data, with access limited to authorized project administrators.
- **Third-party processing:** Data sent to third-party services, such as OpenAI for AI analysis or external APIs for ingestion/export workflows, is subject to those providers' terms and privacy practices.
- **Cookies and WordPress behavior:** The WordPress site may set essential cookies related to login state, session handling, security, or embedded content. If analytics or non-essential cookies are added later, a cookie notice/consent flow should be considered.
- **Data retention:** Application logs, backups, exports, and uploaded files should follow a defined retention and deletion policy appropriate for operational, institutional, and research needs.
- **Access and protection:** Secrets should be stored securely, admin access should be restricted, backups should be protected, and production systems should use TLS and least-privilege access controls.
- **Contact and governance:** The public site should identify the responsible WELL/McMaster contact or team for privacy questions, correction requests, and operational issues.

---

## FAQ

**How does routing work end-to-end?**
Nginx terminates TLS and routes by host/path to either the dashboard container or WordPress. The frontend encodes filter state in URL query params. The API exposes versioned REST paths for stations, parameters, metrics, aggregate, download, ai, and health.

**How are backups automated?**
Nightly cron jobs export curated CSVs from PostgreSQL and upload them to Borealis and SharePoint, recording checksums and outcomes in logs.

**How does the AI analysis feature work safely?**
The API aggregates and downsamples the series first, then sends a bounded prompt with metadata to OpenAI. Responses are rendered in the UI and can be exported.

**What keeps the dashboard responsive with large datasets?**
Indexed PostgreSQL queries, precomputed downsampled series, cached API responses, and client-side SSR/memoization.

**How is the dashboard embedded and secured?**
It's embedded via iframe on a dedicated WordPress page. CSP `frame-ancestors` and CORS rules allow only the trusted WordPress origin.



