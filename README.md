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

## Known Issues & TODOs

### High Priority
- [ ] Update `config.py` to use `os.getenv` for all Borealis and SharePoint config instead of hardcoding
- [ ] Add shared-secret header between dashboard and backend (`X-Internal-Auth`) for extra protection
- [ ] Check all backend injection scripts (historical and scheduled)
- [ ] Verify CORS configuration for backend API
- [ ] Add indexes on DB for query speed
- [ ] Check if multiple concurrent users on the website are handled correctly

### Backend
- [ ] Use webhooks with Flask to automate redeployments on push to repo
- [ ] Add rate limiting and background queues for heavy AI/aggregation tasks
- [ ] Add Flask-RestX for API documentation
- [ ] Add script to remove old PostgreSQL logs from `C:\Program Files\PostgreSQL\17\data\log`
- [ ] Cron job for monthly Borealis retrieval (add to existing export script)
- [ ] Ensure `/api/analysis` calls are only triggered by valid frontend requests

### Frontend
- [ ] Fix all TypeScript/ESLint errors (currently suppressed via config)
- [ ] Fix responsiveness of header logos on iPhone dimensions
- [ ] Add Highcharts Boost Module for faster rendering on large datasets
- [ ] Make Highcharts metric colours consistent across all loggers
- [ ] Refactor download function to send from backend
- [ ] Upgrade frontend to handle lag on large dataset renders

### WordPress
- [ ] Fix WordPress site images to be responsive
- [ ] Remove unused CSS/JS files from theme; clean up unused classes
- [ ] Restyle so it no longer resembles the MacSites/Lovable default theme
- [ ] Disable search and menu where not needed
- [ ] Once `wp-admin` is accessible via correct path/IP, redirect login attempts to home

### Infrastructure
- [ ] Switch to long-term Google Maps API key (remove dev-purposes key)
- [ ] Update OpenAI API key to Matt's account
- [ ] Setup CSV sampling upload template for researchers
- [ ] Add sampling template/guidelines for researchers
- [ ] Extend caching with revalidation strategies and window-aware materialized views
- [ ] Expand download options (Parquet, GeoJSON) with provenance metadata
- [ ] Add end-to-end tests for filters, downloads, and AI analysis workflows
- [ ] Add automated Lighthouse checks for accessibility and performance (WordPress)
- [ ] Tighten proxy headers (CSP, X-Frame-Options) while preserving embed behavior

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
