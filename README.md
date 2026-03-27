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

---

## Data Sources & APIs

| Source | Type |
|---|---|
| HoboLink (Licor Cloud API) | Automated ingestion & scheduled updates |
| WQData Live API | Automated ingestion & scheduled updates |
| OpenAI API | AI analysis over downsampled series |
| Borealis | Nightly cron export/upload |
| SharePoint | Nightly cron export/upload |

---

## Automation

Cron orchestrates all scheduled tasks:
- **Ingestion**: HoboLink and WQData pulls on schedule
- **Historical backfills**: Retroactive data imports
- **Downsampling**: Bucket-based reduced-resolution series for chart performance
- **Exports**: Nightly CSV exports to Borealis and SharePoint with checksum verification and logging
- **Health checks**: Readiness endpoints for external monitors

---

## AI Analysis

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

## Data Upload (Manual)

```bash
python upload_data.py --year 2023 --month 7
```

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

Recommended follow-up production tasks:

- [ ] Add public Terms & Conditions page to WordPress
- [ ] Add public Privacy Policy page to WordPress
- [ ] Link legal/privacy pages from the WordPress footer and any dashboard embed entry points
- [ ] Document cookies, logging, AI processing, and third-party data sharing more explicitly before launch
- [ ] Confirm institutional/legal review for final published wording

---

## Known Issues & TODOs

### High Priority
- [ ] UI visual bugs: fix SVG arrows on the About page
- [ ] UI visual bugs: fix share-option post icons (X/Facebook/LinkedIn rendering)
- [ ] Fix modal behavior on mobile, especially chart/graph usability (consider landscape-oriented layout)
- [ ] Document local PostgreSQL setup for prod parity: database/user creation, environment variables, and exact migration/seed scripts to create all tables
- [ ] Update `config.py` to use `os.getenv` for all Borealis and SharePoint config instead of hardcoding
- [ ] Add shared-secret header between dashboard and backend (`X-Internal-Auth`) for extra protection
- [ ] Check all backend injection scripts (historical and scheduled)
- [ ] Verify CORS configuration for backend API
- [ ] Add authentication/authorization model for API and admin operations (service-to-service + operator access)
- [ ] Move download generation/streaming to backend APIs; keep frontend as trigger-only to reduce UI lag on large exports
- [ ] Add server-side resolution-aware downsampling so large chart requests return display-ready data instead of raw million-point payloads
- [ ] Add precomputed rollups/materialized views for common time windows (1 min / 5 min / hourly / daily)
- [ ] Add indexes on DB for query speed
- [ ] Check if multiple concurrent users on the website are handled correctly
- [ ] Remove first Borealis upload on script start; schedule uploads only on specific months/years (manual trigger or cron)
- [ ] Split dashboard Docker services into separate frontend and backend containers for independent restart capability
- [ ] Enhance Highcharts rendering: add Boost Module with native data grouping, lazy loading, and dynamic grouping intervals based on date range (e.g., 5-min for 2-month windows, hourly for 1-year windows, daily for multi-year)
- [ ] Build GitHub Actions CI/CD pipeline with per-commit quality gates: **Backend** (unit tests for routes/services/config, integration tests for `/api/data`, `/api/analysis`, export endpoints, linting, type checking, Docker build validation); **Frontend/Next.js** (unit tests for hooks/components, E2E tests for filter/download flows, Lighthouse accessibility/performance checks, responsive design tests across mobile/tablet/desktop, ESLint/TypeScript checks); **WordPress** (accessibility audit, responsive design tests, theme/plugin security scan, smoke tests for iframe embedding); **Infrastructure** (Docker image security scan, compose validation, dependency vulnerability checks)

### Backend
- [ ] Use webhooks with Flask to automate redeployments on push to repo
- [ ] Add rate limiting and background queues for heavy AI/aggregation tasks
- [ ] Add Flask-RestX for API documentation
- [ ] Add backend unit tests for Flask routes, services, config parsing, sampling imports, and Borealis/export logic
- [ ] Add integration tests for critical API endpoints (`/api/data`, `/api/latest`, `/api/analysis`, download/export paths)
- [ ] Add async export jobs for large downloads with job status, retry handling, and downloadable artifact links
- [ ] Add request-size/query-budget limits so very large ranges automatically aggregate instead of returning excessive raw data
- [ ] Add Redis caching for latest metrics, recent data, and common aggregate queries with TTL/invalidation rules
- [ ] Add email alerts for failed ingestion, failed exports/uploads, stale data pulls, and scheduled job exceptions
- [ ] Add script to remove old PostgreSQL logs from `C:\Program Files\PostgreSQL\17\data\log`
- [ ] Cron job for monthly Borealis retrieval (add to existing export script)
- [ ] Fix sampling-data Excel import flow and align it with Borealis pull/export formats
- [ ] Ensure `/api/analysis` calls are only triggered by valid frontend requests

### Frontend
- [ ] Fix all TypeScript/ESLint errors (currently suppressed via config)
- [ ] Add frontend unit tests for hooks, filter/query-state logic, data transforms, and API error/loading states
- [ ] Cancel stale in-flight requests when filters/date ranges change quickly
- [ ] Add chart-resolution logic so the UI requests aggregated data for wide date ranges and only fetches raw detail on zoom
- [ ] Fix responsiveness of header logos on iPhone dimensions
- [ ] Make Highcharts metric colours consistent across all loggers
- [ ] Update download UI to use backend export endpoints with progress/error states
- [ ] Move any heavy client-side data transforms/parsing into Web Workers if profiling shows UI blocking
- [ ] Upgrade frontend to handle lag on large dataset renders

### WordPress
- [ ] Fix WordPress site images to be responsive
- [ ] Remove unused CSS/JS files from theme; clean up unused classes
- [ ] Restyle so it no longer resembles the MacSites/Lovable default theme
- [ ] Disable search and menu where not needed
- [ ] Once `wp-admin` is accessible via correct path/IP, redirect login attempts to home
- [ ] Add smoke tests for dashboard iframe embedding, mobile responsiveness, and cross-site navigation

### Infrastructure
- [ ] Switch to long-term Google Maps API key (remove dev-purposes key)
- [ ] Update OpenAI API key to Matt's account
- [ ] Setup CSV sampling upload template for researchers
- [ ] Add sampling template/guidelines for researchers
- [ ] Define and document production server baseline (OS patching cadence, fail2ban/SSH hardening, least-privilege user accounts)
- [ ] Define and enforce network controls (host firewall rules, allowed ingress/egress, DB not publicly exposed)
- [ ] Create cloud/VM infrastructure runbook (provisioning, scaling limits, incident escalation, ownership)
- [ ] Add container hardening and image scanning in pipeline (base image pinning, vulnerability scan, signed images)
- [ ] Add automated backend/database backups with restore testing and retention policy
- [ ] Add file-level backup + restore plan for WordPress assets/theme/uploads and dashboard artifacts
- [ ] Partition large measurement tables by time and benchmark query performance against current schema
- [ ] Add database reliability tasks (index review, query plan checks, vacuum/analyze schedule, connection limits)
- [ ] Add load testing and benchmark targets for common dashboard flows, heavy chart queries, exports, and concurrent usage
- [ ] Extend caching with revalidation strategies and window-aware materialized views
- [ ] Expand download options (Parquet, GeoJSON) with provenance metadata
- [ ] Add end-to-end tests for filters, downloads, and AI analysis workflows
- [ ] Add automated Lighthouse checks for accessibility and performance (WordPress)
- [ ] Tighten proxy headers (CSP, X-Frame-Options) while preserving embed behavior
- [ ] Add and maintain `.env.template` documenting required environment variables for local/dev/prod deployments
- [ ] Triage and resolve GitHub Dependabot vulnerabilities from the repository security dashboard (`https://github.com/ARCO-Lab/WELLWebsite/security/dependabot`)
- [ ] Build CI/CD pipeline for frontend, backend, and WordPress theme/plugin changes with required quality gates (unit tests, smoke tests, lint, type checks, build, deploy, rollback); use Netlify only for frontend preview builds, not final integration signoff
- [ ] Add a secure GitHub webhook deploy flow that triggers only after CI checks pass, then pulls latest code and redeploys only affected Docker services
- [ ] Refactor `git_pull.sh` into a modular, environment-driven deploy script that uses GitHub-provided/env-configured variables (branch, environment, changed services, compose profile)
- [ ] Document the full CI/CD + webhook auto-deploy workflow in this README once implemented (inputs, secrets, rollback, and service selection logic)
- [ ] Implement observability stack: Prometheus + Alertmanager + Grafana for metrics/alerts (or Sentry/Posthog/Resend for emails on downloads, and errors), and Loki + Promtail for centralized logs across Nginx, Flask, Next.js, WordPress, cron jobs, and PostgreSQL
- [ ] Route Alertmanager notifications to email for ingestion failures, export/upload failures, stale-data windows, API 5xx spikes, and host/database health incidents
- [ ] Define SLOs/SLIs and alert thresholds (availability, latency, error rate, data freshness, cron success)
- [ ] Add synthetic monitoring for the full WordPress → iframe dashboard journey and key API health checks

---

## Potential Workflow: Highcharts At 5M+ Points

This is a proposed implementation workflow to make chart rendering fast at very large data volumes while preserving full-fidelity exports.

### 1. Fast Initial Load (Coarse Series)
- Request downsampled data for wide date ranges from backend (target ~300 to 2000 points per visible chart).
- Return metadata with each response: `original_count`, `downsampled_count`, `resolution`, `range_start`, `range_end`.
- Render immediately so users see a responsive chart without waiting for raw data.

### 2. Zoom-Triggered Detail Fetch
- Keep Highcharts zoom enabled on x-axis.
- On zoom selection, call backend for the selected time window at a finer resolution (or raw if the window is small).
- Replace only the visible series data after fetch, with debounce and request-cancel logic to avoid UI stalls.

### 3. Resolution Rules (Server-Side)
- Use range-aware buckets (example):
	- multi-month/year view: daily or weekly aggregates
	- multi-week view: hourly aggregates
	- short-range view: raw/minute-level data
- Prefer LTTB or min/max bucket-preserving downsampling for trend fidelity.

### 4. Download Strategy (Dual Path)
- **Instant browser download:** export currently visible dataset (fast, may be downsampled).
- **Async full export:** queue a background job for complete raw data, then provide email/download link when ready.
- Keep exports generated server-side so frontend remains responsive.

### 5. Caching + Queueing
- Add Redis cache for common chart queries (range + metrics + group + resolution key).
- Add Celery worker(s) for heavy exports and long-running data assembly.
- Add status endpoint for export progress (`queued`, `running`, `ready`, `failed`).

### 6. Database + API Performance Baseline
- Ensure composite indexes cover chart query pattern: `(group_type, measurement_type, recorded_at)`.
- Enforce query budgets/limits for extreme ranges.
- Stream/iterate large DB reads in chunks for export jobs.

### 7. UX Guardrails
- Show "displaying summarized data" badge when coarse data is shown.
- Show loading indicator only for zoom refinement region, not full-page blocking spinner.
- Keep tooltips/legend consistent between coarse and fine datasets.

### 8. Suggested Rollout Order
1. Server-side range-aware downsampling API.
2. Frontend zoom-refine fetch flow with request cancellation.
3. Redis caching for repeated chart windows.
4. Async full-data export (Celery + email/link delivery).
5. Profiling and tuning (p95 API latency, chart time-to-interactive, export completion time).

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



