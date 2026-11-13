# WELL dashboard backend

The Flask API, the ingestion worker and its scheduled jobs, and the export worker. One image
(`dashboard/backend/Dockerfile`) runs as four Docker Compose services: `backend` (the API), `worker` (the scheduler),
`export_worker` (Celery) and, when its profile is on, `ops` ([welldash²](app/ops/README.md)). Every setting is listed
in [docs/configuration.md](../../docs/configuration.md).

- [Local setup](#local-setup)
- [API](#api)
- [Data sources](#data-sources)
- [Ingestion and scheduled jobs](#ingestion-and-scheduled-jobs)
- [Exports](#exports)
- [Off-VM copies: Borealis and SharePoint](#off-vm-copies-borealis-and-sharepoint)
- [Monitoring](#monitoring)
- [Error reporting (Sentry)](#error-reporting-sentry)
- [Database backups](#database-backups)
- [Database migrations](#database-migrations)
- [AI analysis (disabled)](#ai-analysis-disabled)
- [Tests](#tests)

## Local setup

The backend needs Python 3.11, as in its image:

```bash
cd dashboard/backend
python -m venv venv

# Linux/macOS
source venv/bin/activate
# Windows
.\venv\Scripts\activate
# or
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

The settings go in `dashboard/backend/app/.env` (the `backend`, `worker` and `export_worker` containers read it, and so
do scripts run by hand). Docker Compose reads a second file, `.env` at the repository root, for the database URL,
passwords and ports. Neither is committed. The ones ingestion can't run without:

```bash
# dashboard/backend/app/.env
HOBOLINK_API_URL=https://api.hobolink.licor.cloud/v1/data
HOBOLINK_API_TOKEN=your-api-token-here
HOBOLINK_LOGGERS=weather-station-serial,logger-serial,...

WQ_API_URL=https://www.wqdatalive.com/api/v1
WQ_API_KEY=your-api-key-here
WQ_DEVICE_ID=your-device-id-here
```

`HOBOLINK_LOGGERS` is the LI-COR logger serial numbers, comma-separated. Only the first is queried: it must be the
weather station's, since the water-level loggers report through it. In Docker, `DATABASE_URL` comes from
`BACKEND_DATABASE_URL` in the root `.env`; set `DATABASE_URL` in `app/.env` only to run the backend or a script outside
Docker. `python server.py` (from `dashboard/backend/app`) starts the API on port 5000 in debug mode, for development
only; the image runs it with gunicorn.

CI's "Lint Python, shell and compose" job runs ruff's pyflakes rules on the backend (`ruff check --select F
dashboard/backend`), and GitHub's code-quality bot comments on pull requests. To keep both quiet: import a module one
way per file (`import unittest.mock`, or `from unittest import TestCase, mock`, not both), leave no unused imports or
variables, give an `except` that only passes a comment saying why, and put commas between strings in a list unless
they're meant to join.

## API

A **Flask** WSGI app served by **Gunicorn** (3 processes with 4 threads each, `dashboard/backend/Dockerfile`), with no
public port. The browser reaches each route through the dashboard's API route of the same path
(`dashboard/frontend/src/pages/api/`, which passes requests on with `src/lib/proxyBackend.ts`), except where noted.
Routes are in `app/api/routes/`:

- `/api/series`: the sensor charts (below)
- `/api/windrose`: the wind rose, counted in PostgreSQL: how often the wind blew from each of 16 directions at each
  speed class, for a range (details in `app/api/routes/windrose.py`)
- `/api/data`: raw readings for a range of at most 31 days (400 beyond it), capped by `DATA_MAX_ROWS` (413 beyond
  it). The dashboard page no longer calls it, but its API route still passes it through
- `/api/latest`: the newest reading of every series (the Latest Data panel)
- `/api/samples` and `/api/recent`: creek sampling results, and the newest of each measurement;
  `/api/samples/template.csv` (the dashboard's `/api/sampling-template`) is the sampling CSV template
- `/api/exports/estimate`, `/api/exports/sync`, `/api/exports/jobs`, `/api/exports/jobs/<id>` and
  `/api/exports/jobs/<id>/download`: CSV downloads (see [Exports](#exports))
- `/health` (the process is up; not passed through) and `/health/data` (data freshness, see
  [Monitoring](#monitoring); the dashboard's `/api/health/data`)
- The AI analysis routes (`/api/analysis/*`) are switched off; see [AI analysis](#ai-analysis-disabled)

**Chart data.** `/api/series?start=&end=&group_type=...` serves chart data aggregated in PostgreSQL for each request
(nothing is precomputed): about 2,000 points per series (raw 10-minute readings up to ~2 weeks, coarser buckets beyond;
ranges longer than ~5.5 years are capped at daily buckets, so they get more), using an index on (sensor group, time).
A chart can also ask for one series at a fixed bucket size (`bucket=`, `series=`): the dashboard loads each chart in
fixed tiles, and a request for more than `MAX_BUCKETS` buckets per series gets a 400.

The contract for a request with `bucket=` (what `dashboard/frontend/src/lib/seriesTiles.ts` sends): it asks for whole
tiles. A tile is 360 buckets (`TILE_BUCKETS`), and tiles start at multiples of their length counted on Toronto's wall
clock from 1970-01-01T00:00 (for 10-minute buckets, every 2.5 days: 2026-09-26T12:00, 2026-09-29T00:00, ...).
`start` must be a tile's start and `end` a later tile's start or one second before it, as times without an offset,
and the request may cover 1 to 8 tiles (`MAX_TILES`); anything else gets a 400 that names the nearest tile start. Only
these tile requests are kept in the Redis cache: there are only so many tiles, so asking for ranges shifted a few
minutes at a time can't fill Redis. Requests without `bucket=` take any range and are computed every time. A change to
the dashboard's tile size or batch size must change `TILE_BUCKETS` or `MAX_TILES` in `app/api/routes/series.py`
with it.
Times with an offset (`...Z`) are real instants, times without one are Toronto local time. Each series has an `agg`
field saying what its `avg` array holds: `mean` for most measurements, `sum` for Rain (the bucket total; `min`/`max`
stay the smallest and largest single reading), and `vector_mean` for Wind Direction (350° and 10° average to 0°;
`min`/`max` are null, since a linear min/max of angles means nothing). Details in `app/api/routes/series.py`.

**Raw readings.** `/api/data` refuses a range longer than 31 days with a 400 before counting anything, so it can't
be made to count the whole history. `DATA_MAX_ROWS` (default `100000`, about a month of every sensor group, ~17 MB
of JSON) is the most readings one request may return (the charts use `/api/series` and the wind rose
`/api/windrose`); a larger range gets a 413 asking the user to narrow it or use Download. It is read once by each
gunicorn worker when it starts. An empty value means the default; any other value that isn't a positive whole number
logs a warning and uses the default. The cap matters because the backend can't tell when a browser gives up: the
Next.js proxy stops waiting, but the backend thread stays busy until the query and JSON encoding finish.

**Origins.** Flask sends no CORS headers, so no page on another site may read its answers: browsers never call it
directly (it has no public port; the dashboard's API routes call it from the server). The dashboard's API routes also
limit how many requests each address may make (see the [dashboard README](../frontend/README.md#rate-limits-and-security-headers)).

### How the API stays responsive under load

Gunicorn runs 3 worker processes with 4 threads each, so a few slow chart requests don't hold up `/api/latest` or the
health checks. Two settings in the backend's `environment:` in `docker-compose.yml` (override them in the root `.env`,
not in `app/.env`, which they take precedence over):

| Variable | Default | Meaning |
|---|---|---|
| `DB_STATEMENT_TIMEOUT_MS` | `25000` | PostgreSQL cancels any API query that runs longer, and the API answers **504** with a message the dashboard shows. `0` turns it off. Only the `backend` container sets it: `worker` (ingestion, backfills) and `export_worker` have no limit, and `scripts/migrate.py` opens its own connection without one even when run in the backend container. A script run by hand with `docker compose exec backend` does get the limit; add `-e DB_STATEMENT_TIMEOUT_MS=0`, or run it in `worker`. |
| `API_CACHE_REDIS_URL` | `redis://redis:6379/2` | Where `/api/series` (tile requests only, see above) and `/api/windrose` keep answers (1 minute for a range that ends within the last hour, 5 minutes for one that ended earlier, an hour for one that ended over a day ago), shared by all gunicorn workers. The key is the range with start rounded up and end rounded down to 10-minute marks, where readings fall, so it selects the same readings as the request. Answers over 3 MB aren't stored (the largest tile request the dashboard makes is about 2.2 MB). If Redis is down the API skips the cache for 30 s at a time and queries the database. Empty turns the cache off. |

`/api/latest` and `/api/series` also tell browsers how long they may reuse an answer: `Cache-Control: public,
max-age=60` at most, and no longer than an answer from the Redis cache has left there; an `/api/series` range that
ended over a day ago may be reused for 3 hours (readings that old rarely change, so a chart panning back over them asks
again only now and then; not longer, since a backfill or cleanup can still change them); the Next.js proxy passes that
header through. There is no ETag and no proxy cache. Nothing on the server caches `/api/latest`, so the Latest Data
panel is never more than a minute behind the database. If the backend hasn't started answering after 65 s, the proxy
answers 504. How this holds up with many visitors at once is measured by the
[load test](../../docs/load-testing.md).

## Data sources

| Source | Type |
|---|---|
| HoboLink (Licor Cloud API) | Automated ingestion & scheduled updates |
| WQData Live API | Automated ingestion & scheduled updates |
| OpenAI API | AI analysis, currently disabled (see [AI analysis](#ai-analysis-disabled)) |
| Borealis | Monthly sensor CSV upload; weekly sampling download ([Off-VM copies](#off-vm-copies-borealis-and-sharepoint)) |
| SharePoint | Monthly sensor CSV upload, when configured ([Off-VM copies](#off-vm-copies-borealis-and-sharepoint)) |

A daily GitHub Actions job checks that each vendor API still answers in the shape ingestion reads: see the
[API canary](../../.github/workflows/README.md#api-canary).

## Ingestion and scheduled jobs

The scheduled jobs run inside the containers, not from cron. The `worker` container runs `scripts/scheduler_temp.py`,
one Python `schedule` loop that starts each job in its own thread, and never starts a job again while its last run is
still going:
- **Ingestion** every 10 minutes: new LI-COR (the weather station and the water-level loggers) and WQData (the water
  quality sonde) readings are written to PostgreSQL, then the alert check runs (see [Monitoring](#monitoring)). It
  also runs once when the worker starts, to catch up after a restart.
- **Sampling download** every Sunday at 00:00 by the container's clock (UTC unless `TZ` is set): new sampling CSVs from
  Borealis (see [Off-VM copies](#off-vm-copies-borealis-and-sharepoint)).
- **Monthly upload** at 02:00 Toronto time: each month that has ended and isn't uploaded yet goes to Borealis (so last
  month goes up on the 1st, and a failed month is retried the next day), then the same file to SharePoint, which stays
  off until its settings are filled in.
- **Daily digest** at `DIGEST_HOUR` (default 07:00 Toronto time).
- **Database backup** at 03:15 Toronto time: a checked `pg_dump` of the database, 7 daily and 8 weekly dumps kept (see
  [Database backups](#database-backups)).

The `export_worker` container (Celery with its beat scheduler) deletes expired download files every hour. Backfills of
missed vendor data aren't scheduled: run `scripts/licor_backfill.py` or `scripts/wqdata_backfill.py` by hand (their
headers explain how). The 10-minute ingestion fetches a LI-COR group's gap once, in the run that first sees it
again after more than a day of silence; older readings it resends in later uploads are left to `licor_backfill.py`.
The only cron jobs are the optional `deploy.sh --auto` line
([docs/deploying.md](../../docs/deploying.md)) and the WordPress backup
([wordpress/README.md](../../wordpress/README.md#backups)).

## Exports

A CSV export of up to `EXPORT_SYNC_ROW_THRESHOLD` readings is built while the visitor waits (`/api/exports/sync`). A
larger one is queued in Redis as an export job and built by the `export_worker` container (Celery); the dashboard polls
the job and then downloads the file, which stays in the `exports_data` volume for `EXPORT_FILE_TTL_MINUTES`. The
queue's limits (`EXPORT_MAX_ROWS`, `EXPORT_MAX_ACTIVE_JOBS`, `EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER` and the time and
memory limits) are in [docs/configuration.md](../../docs/configuration.md#dashboardbackendappenv-backend-worker-export-worker).

The exports share the VM's disk with the database, so three more limits keep them from filling it:

- **Free space.** An export that would leave less than `EXPORT_MIN_FREE_MB` (default 2048) free on the exports disk,
  counting its estimated size, is refused with a 507, both when it is asked for and again when the worker starts it.
- **Jobs per hour.** Each visitor (by IP address) may start `EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER` (default 6) jobs
  an hour, finished and failed ones included (429 with `Retry-After` beyond that).
- **Reuse.** A request for exactly the same export as a ready job (same normalised filters) gets that job back (200,
  `"reused": true`) instead of a new one, when its file has at least 10 minutes left and its data can't have changed:
  the range ended a day before the job was made, or the job finished in the last 10 minutes.

A body that isn't a JSON object, or start/end that aren't ISO date strings, gets a 400.
The file layouts are a public format, pinned by the [golden files](tests/golden/README.md).

## Off-VM copies: Borealis and SharePoint

The database lives on one VM, so each month's sensor data is also copied off it, twice:

- **Borealis** (`borealisdata.ca`, the Scholars Portal Dataverse that McMaster uses). This is the public, citable copy.
  On the 1st of each month at 02:00 Toronto time the worker runs `scripts/upload_data.py`. It exports the month that
  just ended as `WELLWestCampus_<Mon><YYYY>.csv` (the dashboard's CSV layout), adds it to the upload dataset in a
  folder for the year, and publishes a new major version of the dataset.
- **SharePoint**, a McMaster document library. Right after Borealis, `scripts/sharepoint_upload.py` uploads the same
  file to `<SHAREPOINT_FOLDER>/<year>/` through Microsoft Graph. The two copies are kept apart: each has its own record
  of uploaded months (`logs/uploaded_months.json` and `logs/sharepoint_uploaded_months.json`) and its own heartbeat
  (`HEALTHCHECK_URL_UPLOAD` and `HEALTHCHECK_URL_SHAREPOINT`). If one of them fails, it is retried every day at 02:00
  and the other isn't held up.

Borealis also carries data the other way. Creek **sampling** results are uploaded by people to a second dataset
([how to upload](app/scripts/README.md)), and the weekly download (`scripts/download_data.py`, Sundays 00:00 by the
container clock, UTC) checks each new file against [the sampling CSV format](../../docs/sampling-csv-format.md) and
imports it into the Ancaster Watershed tab.

### The monthly file's format

`WELLWestCampus_<Mon><YYYY>.csv` is UTF-8 CSV with one row per time a reading was taken, in time order. The
[golden files](tests/golden/README.md) pin it byte for byte.

- **Columns**, left to right: `ID` (the row number), `Timestamp (America/Toronto)`, then a Weather block (`Group`,
  `Latitude`, `Longitude`, then one column per measurement), a blank column, a Quality block laid out the same way,
  a blank column, and a Logger block: `Group`, then for each logger `Sensor`, `Latitude`, `Longitude` and one column
  per measurement. A measurement's header is `<name>: <unit>`, with the unit of its last reading that month. A file
  has only the blocks, measurements and loggers that have readings that month; measurements are sorted by name and
  loggers by id.
- **Times** are local wall-clock time at the site, America/Toronto (EST or EDT, whichever was in effect), written as
  ISO 8601 without an offset, e.g. `2026-10-01T00:10:00`; the header names the zone. In the hour repeated when the
  clocks fall back (01:00-02:00 on the first Sunday of November) one reading per time is stored, so those rows
  can't say whether they were EDT or EST. A month is the readings from 00:00 on the 1st up to, not including,
  00:00 on the 1st of the next month, Toronto time.
- **Values** are numbers as stored, unrounded (`0.30000000000000004`). A missing reading is an empty field (never
  `nan`). Text that a spreadsheet would run as a formula (starting with `=`, `+`, `-`, `@`, a tab or a carriage
  return) gets a leading `'`, as in the dashboard's Download Data. Numbers are never changed.
- If two readings share a cell (the same time and measurement from two stations of one group), the cell holds the
  first by station id, so the same month always gives the same file.

The dashboard's Download Data uses a similar layout without the `Latitude`/`Longitude` columns, and names its
time column the same way; its sampling download names it `recorded_at (America/Toronto)`.

### How the Borealis jobs behave

- **Publishing.** Adding a file only changes the dataset's *draft*, which only its editors can see, so the upload
  publishes the draft afterwards. It publishes only a draft that holds this month's file unpublished (added or
  replaced by this run, or left by a run that failed before publishing); a draft with only someone else's changes,
  such as a curator's metadata edit, is left for them to publish. Dataverse has only one draft per dataset, though, so
  **a draft that is open when the month's file is added (a curator's unfinished edit) is published together with that
  file**, and the log warns when that happens. Curators should finish or discard edits on the upload dataset before
  the 1st of the month (the upload runs at 02:00 Toronto time, and retries daily until it succeeds), or set
  `BOREALIS_PUBLISH=0` while they work. Any version that changes files has to be published as a **major** version
  (Dataverse refuses a minor one), so the dataset goes 1.0, 2.0, and so on, one version per month. The first publish
  also needs the dataset's collection to be published. Set `BOREALIS_PUBLISH=0` to leave each month as a draft for a
  curator to publish instead.
- **No tabular ingest.** Uploads are sent with `tabIngest=false`. That stores the CSV byte for byte, so its checksum
  matches the one the job computes, and no ingest lock delays publishing. (Ingest would turn it into a `.tab` file,
  and the CSV's blank separator columns and repeated headers don't convert well.)
- **Safe to re-run.** If a file with the same name and checksum is already in the dataset, nothing is sent, and if
  that file is still waiting in a draft, the draft is published. A changed file *replaces* the published one, and
  Dataverse keeps the old copy in the earlier version. A changed file that was never published is deleted and added
  again, because Dataverse can't replace an unpublished file. So a run that failed between upload and publish is
  finished by the next run, without a duplicate file.
- **Errors** name the cause without printing the token or URLs (the token is also scrubbed from anything Borealis says
  back, which can repeat it). 401 means the token is wrong or expired, 403 means the account lacks a role (Curator is
  needed), 404 means a wrong id or the demo server, and 409 means the dataset is locked or the collection isn't
  published. Each month's CSV is built in seconds.
- **The download reads only the published version.** A file someone uploaded but nobody has published yet is skipped,
  and the log says that a draft is waiting. It is imported on the first run after the dataset is published.
  Restricted files are skipped, so the download needs no token: a published sampling dataset works without one.

### Settings (`dashboard/backend/app/.env`, read by the worker)

| Variable | What |
|---|---|
| `BOREALIS_URL` | `https://borealisdata.ca`. A collection page such as `https://borealisdata.ca/dataverse/WELL` also works: the jobs and the canary use only its server part (the upload and download log the server they use), and the preflight checks the collection `WELL`. |
| `BOREALIS_API_TOKEN` | The API token of the account that uploads and publishes (it needs the Curator role on the upload dataset or its collection). It must be made on the same server as `BOREALIS_URL`: demo and production tokens are separate. |
| `BOREALIS_UPLOAD_PERSISTENT_ID` | The sensor dataset, e.g. `doi:10.5683/SP3/ABCDEF` (dataset page > Metadata > Persistent Identifier). |
| `BOREALIS_SAMPLING_PERSISTENT_ID` | The sampling dataset. |
| `BOREALIS_UPLOAD_DATAVERSE`, `BOREALIS_SAMPLING_DATAVERSE` | The aliases of the two collections. Only the preflight uses them. They don't default to the alias in `BOREALIS_URL`: the datasets sit in sub-collections of it, and the preflight already checks that one as the parent. |
| `BOREALIS_PUBLISH` | `1` (default) publishes each month; `0` leaves a draft. |
| `BOREALIS_UPLOAD_FIRST_MONTH` | The first month uploaded (default `2026-10`). |
| `SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET` | The Entra ID app registration (see below). |
| `SHAREPOINT_SITE` | e.g. `https://mcmaster.sharepoint.com/sites/WELL`. |
| `SHAREPOINT_LIBRARY`, `SHAREPOINT_FOLDER` | The document library (default `Documents`) and the folder in it (default `WELL sensor data`). |
| `SHAREPOINT_UPLOAD_FIRST_MONTH` | The first month copied to SharePoint (default: the Borealis one). |
| `HEALTHCHECK_URL_SHAREPOINT` | Heartbeat for the SharePoint copy (see [Monitoring](#monitoring)). |

The SharePoint copy is **off** while none of the first four `SHAREPOINT_*` variables is set. If only some are set, the
worker logs which ones are missing and reports a failure at 02:00. The older `DEMO_BOREALIS_URL`,
`DEMO_BOREALIS_WC_PERSISTENT_ID` (upload) and `DEMO_BOREALIS_AW_PERSISTENT_ID` (sampling) are still read when the new
names are unset. They point at `demo.borealisdata.ca`, a test server that is reset from time to time and is not a
backup, and the upload refuses to mix a production URL with a demo dataset id.

### Checking it

```sh
docker compose exec worker python scripts/borealis_check.py --check      # read-only: GET requests only
docker compose exec worker python scripts/sharepoint_upload.py --check   # read-only: sign-in, site, library, folder
docker compose exec worker python scripts/upload_data.py --year 2026 --month 10 --dry-run   # build the CSV only
```

`borealis_check.py` checks the settings, whether the token is valid and when it expires, whether each collection is
published and what your account may do in it, and each dataset's published version, licence, locks and permissions
(`canEditDataset` and `canPublishDataset` on the upload dataset). For the sampling dataset it also checks that it is
published and holds the template and a README. It ends with a numbered list of what is still missing, and exits 1
until that list is empty. It never prints the token.

### Uploading a month by hand

To upload one month to the live Borealis dataset now, instead of waiting for the scheduler:

```bash
docker compose exec worker python scripts/upload_data.py --year 2026 --month 10            # uploads and publishes
docker compose exec worker python scripts/upload_data.py --year 2026 --month 10 --dry-run  # builds the CSV only
```

A month uploaded by hand isn't recorded in `logs/uploaded_months.json`, so the scheduler may run it again; that is
safe, since an identical file isn't sent twice.

### What each service needs

**Borealis**

1. **An account with a role on the WELL collection**
   ([borealisdata.ca/dataverse/WELL](https://borealisdata.ca/dataverse/WELL), inside the McMaster University
   collection): **Curator** on `WELL` (or **Admin**, to also manage other people's access). Curator can create
   collections and datasets and add and publish files. A shared account keeps the token from depending on one person.
2. **An API token** for that account: your name (top right) > **API Token** > **Create Token** (or **Recreate
   Token**). Tokens expire, usually after a year; `borealis_check.py` prints the date.
3. **Two published sub-collections** in `WELL` (Add Data > New Dataverse), for example "WELL West Campus sensor data"
   (alias `WELL-sensors`) and "WELL Ancaster Creek sampling" (alias `WELL-sampling`), each with a contact email and a
   category such as Laboratory or Research Project. Datasets can't be published before their collection.
4. **One dataset in each** (Add Data > New Dataset). The citation metadata required to publish is the title, author
   (WELL / McMaster University), point-of-contact email, description and subject (Earth and Environmental Sciences).
   Keywords, geographic coverage (Hamilton, Ontario, Canada) and time period are recommended. Choose a licence under
   Terms (CC0 1.0 is the Dataverse default), the same for both datasets.
5. **The sampling dataset**, published, holding
   - the template, `dashboard/backend/app/sampling_template.csv`, under the name **`WELLAncasterWatershed_SAMPLE.csv`**.
     The import ignores that name.
   - a **README** (e.g. `README.md`) that tells uploaders to follow the format in `docs/sampling-csv-format.md` (or
     links to it on GitHub), to name files `WELLAncasterWatershed_<description>.csv`, to check them with
     `scripts/check_sampling_csv.py`, and to **publish the dataset after adding files** (otherwise they aren't
     imported).

   People who upload sampling files need the **Contributor** role on it (they can add files; a Curator publishes) or
   Curator (they publish themselves).
6. **The sensor dataset** can start empty: the first monthly upload publishes version 1.0. Its persistent id
   (`doi:10.5683/...`), like the sampling dataset's, goes in the settings above.
7. **On the VM**, set `BOREALIS_URL`, `BOREALIS_API_TOKEN`, `BOREALIS_UPLOAD_PERSISTENT_ID`,
   `BOREALIS_SAMPLING_PERSISTENT_ID`, `BOREALIS_UPLOAD_DATAVERSE` and `BOREALIS_SAMPLING_DATAVERSE` in
   `dashboard/backend/app/.env` (with no `DEMO_BOREALIS_*` lines left), recreate the worker so it reads them
   (`docker compose up -d --no-deps worker`), and run `borealis_check.py --check` until it says Ready. The canary reads
   the same names from its repository secrets (`BOREALIS_URL`, `BOREALIS_API_TOKEN`, `BOREALIS_UPLOAD_PERSISTENT_ID`
   and `BOREALIS_SAMPLING_PERSISTENT_ID`), before the older `DEMO_BOREALIS_*` ones.

**SharePoint**

8. **A destination:** a SharePoint site the lab owns, its document library (usually *Documents*), and a folder
   (default `WELL sensor data`; the job creates it and one subfolder per year).
9. **An app-only identity limited to that site**, registered by McMaster IT in the McMaster Entra ID tenant: a single
   tenant app registration with no redirect URI; the Microsoft Graph **application** permission `Sites.Selected`
   (not `Sites.ReadWrite.All`) with admin consent; a site-specific grant with the `write` role on the site (with
   Graph, `POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions` with `{"roles": ["write"],
   "grantedToIdentities": [{"application": {"id": "<app client id>", "displayName": "<app name>"}}]}`, or with PnP
   PowerShell, `Grant-PnPAzureADAppSitePermission -AppId <app client id> -DisplayName "<app name>" -Site <site URL>
   -Permissions Write`); and a client secret, whose expiry date is worth noting. The app signs in with the OAuth 2.0
   client-credentials flow, never as a user, and only creates and replaces files in its folder.
10. **On the VM**, set `SHAREPOINT_TENANT_ID`, `SHAREPOINT_CLIENT_ID`, `SHAREPOINT_CLIENT_SECRET`, `SHAREPOINT_SITE`
    (and `SHAREPOINT_LIBRARY` / `SHAREPOINT_FOLDER` if they differ from the defaults) in `dashboard/backend/app/.env`.
    Add a Healthchecks.io check, "WELL SharePoint copy" (cron `0 2 1 * *`, America/Toronto, grace 4 h), and set its
    ping URL as `HEALTHCHECK_URL_SHAREPOINT`. Then recreate the worker. Run `sharepoint_upload.py --check`, then
    `sharepoint_upload.py --year <year> --month <month>` once by hand to prove write access.

## Monitoring

A few simple pieces, all optional and all off until configured. On the VM their settings go in
`dashboard/backend/app/.env` (the backend and worker read it); recreate the containers after changing it
(`docker compose up -d --no-deps backend worker`). Unresolved Sentry errors also become GitHub issues every day (see
[Sentry issues](../../.github/workflows/README.md#sentry-errors-as-github-issues)).

### Data freshness check

`GET /health/data` on the backend, passed through by the dashboard at `https://welldash.mcmaster.ca/api/health/data`,
lists for each group (Weather, Logger, Quality) and each series (station and measurement) the newest `recorded_at` and
its age in minutes. It answers **200** when every live series is within its limit and **503** with a `stale` list
otherwise (also 503 if the database can't be read or a setting below is invalid). It walks the same index as
`/api/latest`, so polling it every few minutes costs nothing noticeable.

| Variable | Default | Meaning |
|---|---|---|
| `HEALTH_MAX_AGE_HOURS` | `3` | Limit for any group without its own. LI-COR data (Weather, Logger) arrives about an hour late, so 3 h means two missed uploads. |
| `HEALTH_MAX_AGE_HOURS_WEATHER`, `_LOGGER`, `_QUALITY` | the above | Limit for one group. |
| `HEALTH_QUIET_HOURS_QUALITY` | `18-12` | Site-time hours (`START-END`, may wrap midnight) when the group's device is known to go silent. During them a series counts as fresh if its newest reading is at most `HEALTH_QUIET_MARGIN_HOURS_QUALITY` older than their start. The WQData sonde usually stops between 18:10 and 22:30 and resumes between 08:20 and 11:30. `off` disables it. `HEALTH_QUIET_HOURS_WEATHER` and `_LOGGER` work the same way and are off by default. |
| `HEALTH_QUIET_MARGIN_HOURS_QUALITY` | `1` | The margin for the quiet hours: with the defaults, a sonde whose last reading was before 17:00 is reported as stale all night (one that stopped at 15:30 is caught; one that stopped for the night at 18:10 isn't). Also `_WEATHER`, `_LOGGER`. |
| `HEALTH_EXCLUDED_SERIES` | `2577535:*` | Series that are reported but never count as stale: `station:measurement` or `station:*`, comma-separated. The default is Logger 5, whose readings stopped in 2025. Set it to an empty value to check everything. |

### Job heartbeats

The worker pings a [Healthchecks.io](https://healthchecks.io) check after each job, and Healthchecks emails the account
owner when a check reports a failure or stops being pinged, so no SMTP is needed for these. A ping times out after 5 s
and never stops the job. Unset variables mean no ping.

| Variable | Pinged |
|---|---|
| `HEALTHCHECK_URL_INGESTION` | After every 10-minute ingestion run; `/fail` when LI-COR or WQData raised an error. |
| `HEALTHCHECK_URL_UPLOAD` | After the monthly Borealis upload (02:00 on the 1st, and daily retries); `/fail` if a month didn't go up. Days with nothing to upload don't ping. |
| `HEALTHCHECK_URL_DIGEST` | After the daily digest; `/fail` if it crashed or couldn't send. |
| `HEALTHCHECK_URL_SHAREPOINT` | After the monthly SharePoint copy (right after the Borealis upload), only when `SHAREPOINT_*` is set; `/fail` if a month didn't go up or the settings are incomplete. |
| `HEALTHCHECK_URL_ALERTS` | After every alert check (every 10 minutes, see below); `/fail` if it crashed or its email couldn't be sent. |
| `HEALTHCHECK_URL_DOWNLOAD` | After the weekly Borealis sampling download (Sundays 00:00 by the container clock, UTC); `/fail` if it failed, or if a file was refused as invalid (`REJECTED_<n>_FILES`, problems listed in `logs/download_injections.log`) or couldn't be imported. A refused file isn't retried, so the next run is a success unless something else fails: act on the first `/fail`. |
| `HEALTHCHECK_URL_BACKUP` | `/start` when the nightly database backup begins (03:15 Toronto time), then success, or `/fail` if the dump failed or didn't pass its check ([Database backups](#database-backups)). |

To set them up, sign in to Healthchecks.io with the address that should get the alerts (the free plan is enough),
create one check per job, and copy each check's ping URL into the matching variable:
- **WELL ingestion**: Simple schedule, period 10 minutes, grace 30 minutes.
- **WELL monthly upload**: Cron `0 2 1 * *`, time zone America/Toronto, grace 4 hours (an upload may take up to 2 h).
- **WELL SharePoint copy**, when SharePoint is configured: the same schedule and grace.
- **WELL daily digest**: Cron `0 7 * * *` (or your `DIGEST_HOUR`), time zone America/Toronto, grace 1 hour.
- **WELL alerts**: Simple schedule, period 10 minutes, grace 30 minutes.
- **WELL backup**: Cron `15 3 * * *`, time zone America/Toronto, grace 2 hours (the job is stopped after 2 h).

**Uptime monitor.** Point any external HTTP monitor that alerts on a non-2xx status (e.g. UptimeRobot's free plan,
5-minute interval) at `https://welldash.mcmaster.ca/api/health/data`, with the owner's email as the alert contact. It
goes red both when the site is down and when data stops arriving.

### Daily digest

`scripts/daily_digest.py` (run by the worker every day at `DIGEST_HOUR`, Toronto time) writes a summary of the last
24 h, in the same Markdown-plus-HTML format as the [email alerts](#email-alerts): the open alerts, the alerts that
recovered (including the low-priority recoveries that weren't emailed on their own, `ALERT_QUIET_KINDS`); stale series; implausible values (dissolved oxygen about 0 mg/L, a logger with about 0 m of water over
its sensor, readings outside physical ranges, a quality probe stuck on one value, except TSS and turbidity at exactly
0, which is normal in clear water); rows and time slots per group against the 10-minute cadence, with gaps over 30
minutes; WQData primary power min/max and last contact (one WQData request, since WQData's hourly quota is shared with
ingestion); every series' newest reading; and yesterday's API traffic (requests, errors, p95 response time, data sent,
CSV downloads, busiest minute; see [welldash²](app/ops/README.md)). It emails the digest when SMTP is configured and
prints it otherwise (the worker logs it to `logs/daily_digest.log`). Run it by hand with
`python scripts/daily_digest.py --dry-run` (print only) or `--no-wqdata` (no WQData request).

| Variable | Default | Meaning |
|---|---|---|
| `ALERT_EMAILS` | none | Recipients, comma-separated. |
| `SMTP_HOST`, `SMTP_PORT` | none | Mail relay. The digest is emailed only when both are set (and `ALERT_EMAILS` isn't empty). Port 465 uses TLS; other ports use STARTTLS when the server offers it. A login (`SMTP_USER` and `SMTP_PASSWORD`) is only sent over TLS: if the relay offers no STARTTLS, the digest refuses to log in and fails. With SMTP set but no valid address in `ALERT_EMAILS`, the digest also fails, so the digest heartbeat reports it. |
| `SMTP_USER`, `SMTP_PASSWORD` | none | Login, used only when both are set. |
| `SMTP_FROM` | `SMTP_USER` | Sender address; required if there's no `SMTP_USER`. |
| `DIGEST_HOUR` | `7` | Hour (0-23, Toronto time) the worker builds the digest. Not 1 or 2: clocks change at 02:00, so on those days the hour happens twice or not at all. An invalid value is logged and no digest runs. |

### Email alerts

After every 10-minute ingestion run the worker checks the data and the vendor APIs (`scripts/check_alerts.py`, rules
in `utils/alerts.py`) and emails `ALERT_EMAILS` through the SMTP settings above when someone has to go and look. Each
problem is an incident: it is emailed once when it starts, again at most every `ALERT_REMINDER_HOURS` while it lasts,
and once when it clears, with how long it lasted. Everything one check finds goes in a single email, so there is never
more than one email per 10 minutes. The subject starts with the status and says what to do, e.g. `[WELL] New: Logger 4
silent 4 h — check the sensor` or `[WELL] Recovered: Logger 1 water level (20 h)`; an email about several things says
how many of each, e.g. `[WELL] 2 new, 1 recovered`.

Each email is plain Markdown text with the same content as simple HTML (`utils/email_format.py`: headings, lists and
bold names, inline styles, no images or colours, so it reads the same in Outlook and on a phone). It starts with a
one-line summary, then has a section per kind, in this order: New problems, Still open (reminder), Back again,
Recovered. Each item gives the station and sensor in plain words, its status, since when or from when to when in
Toronto time (`Wed Nov 11, 12:00 → Thu Nov 12, 08:03 (20 h)`), what to do and the details (problems only), and the
dashboard link. Then "Open right now" lists every open incident, so any one email shows the whole current state, and
the footer links the dashboard, `/api/health/data` and this section ("Why did I get this?").

#### Why did I get this email?

| Email | Subject starts with | Sent when |
|---|---|---|
| New problem | `[WELL] New:` | A check finds a problem that has no open incident (and didn't clear within the last `ALERT_REOPEN_HOURS`). Every kind, at once. |
| Reminder | `[WELL] Still open:` | An emailed problem is still there `ALERT_REMINDER_HOURS` after its last email. |
| Back again | `[WELL] Back again:` | A problem whose recovery was emailed came back within `ALERT_REOPEN_HOURS` and has stayed back `ALERT_CLEAR_MINUTES`. |
| Recovered | `[WELL] Recovered:` | An emailed problem has been gone for `ALERT_CLEAR_MINUTES` (longer after a "back again", see below). Not on its own for the kinds in `ALERT_QUIET_KINDS` (default `SUSPECT_VALUES`): their recovery is added to the next email that goes out anyway, within 24 h, and is listed in the daily digest either way. |
| Several at once | `[WELL] 2 new, 1 recovered` | One check has more than one thing to say: it is one email, never several. |
| Daily digest | `[WELL] Daily digest` | Once a day at `DIGEST_HOUR` ([Daily digest](#daily-digest)). |

The alert check and the digest send nothing else (Sentry and the job heartbeats have their own notifications). A
problem that hasn't changed sends nothing between reminders, and a check with nothing new sends nothing at all.

To keep flickering conditions (a vendor failing on and off, a value hovering at a limit) from emailing "new" and
"recovered" over and over: an incident clears, and "recovered" is emailed, once its condition has been gone for
`ALERT_CLEAR_MINUTES`. A condition that comes back within `ALERT_REOPEN_HOURS` of clearing reopens the same incident
instead of being emailed as new, and if its recovery had been emailed, "back again" is emailed once it has stayed back
`ALERT_CLEAR_MINUTES`. From then on the incident has to be gone for `ALERT_FLAP_CLEAR_MINUTES` before it clears again,
doubled with each further "back again" up to 12 h (flap damping). So a flapping problem sends at most one "recovered"
and one "back again" per window, and the last email about a problem is never wrong for longer than
`ALERT_CLEAR_MINUTES` or its current window. An incident that then stays present without a break for
`ALERT_REOPEN_HOURS` counts as steady again, and its real recovery is reported after `ALERT_CLEAR_MINUTES`. A problem
that comes back later than `ALERT_REOPEN_HOURS` is a new incident. While a vendor's latest call failed, its sensor
alerts are left as they are rather than cleared, and a suspect-values alert is left as it is while there are too few
readings to judge (e.g. the water quality sonde at night). When a single sensor's alert grows into a whole-station (or
whole-site) one, the sensor's incident is replaced without a "recovered" email. When it shrinks back (say the station
alert down to the one sensor still silent), the station incident closes without a "recovered" email too, and the
sensor's incident carries on without a "new" one: the partial recovery isn't emailed, because the remaining problem
was already reported and the next email (reminder or recovery) names it.

#### The alerts and their settings

| Alert | When | What to do |
|---|---|---|
| Vendor down (`VENDOR_DOWN`) | The LI-COR or WQData API call failed on the last `ALERT_VENDOR_FAILURES` runs in a row: an HTTP error, a timeout, a reply without data, or WQData paging that stops advancing. Also when the vendor answered but none of its records could be read (no timestamp, a garbled one, or one without a UTC offset). | Check the vendor's status; our sensors may be fine. Ingestion catches up by itself (up to 14 days back) once the API answers. Unreadable records say "sends records we can't read — check the ingestion log": most likely the vendor changed its format, so `utils/parsers.py` needs a fix. HTTP 401/403 says "rejects our credentials — rotate the API key" (set `HOBOLINK_API_TOKEN` or `WQ_API_KEY` in `.env` and in the repository secret), and WQData's 429 says "request quota exceeded" (stop any `wqdata_backfill.py` run). |
| Sensor silent (`STALE_SENSOR`) | The vendor answered on the latest run, but a station, or one of its sensors, has sent nothing for longer than its group's limit. If every LI-COR station is silent it is one alert for the site (the loggers report through the weather station). | Go to the sensor: its power, cable, telemetry (cellular modem, data plan). Not raised while the vendor's latest call failed, since then the vendor is the likelier cause. If the vendor's latest answer had records that couldn't be read (they are skipped, one at a time, and logged), the subject says "sent unreadable records, check the ingestion log" instead of "vendor OK", since the missing readings may be among them. |
| Suspect values (`SUSPECT_VALUES`) | Data arrives but looks wrong over the whole last `ALERT_SUSPECT_HOURS`: a water quality probe stuck on one value (not TSS/turbidity at 0), at least half the readings outside the physical range, dissolved oxygen about 0, or a logger with about 0 m of water over it. A single odd reading is never an alert. | Look at the chart, then check and clean the probe if it isn't a real event. |
| Recovered | The condition cleared, for an incident that was emailed. A suspect-values recovery waits for the next email or the digest (`ALERT_QUIET_KINDS`). | Nothing; the email says how long it lasted. |

The open incidents are also listed in the daily digest and under `alerts` in `GET /health/data` (with each vendor's
latest call outcome), so the dashboard can show them; they don't change its status code. They are listed by kind, key,
title and times only; the details and advice are in the emails. Without SMTP settings nothing is emailed: incidents are
still recorded and the email is written to `logs/alerts.log` instead (in full when its content changes, otherwise one
line per check), and once SMTP is set up the next check emails the incidents still open. To see what would be sent now
without recording or sending anything: `docker compose exec worker python scripts/check_alerts.py --dry-run`. The
state lives in two tables, `vendor_status` (written by every ingestion run) and `alert_incidents`, created by migration
`0003_monitoring_alerts.sql` (see [Database migrations](#database-migrations)); `0006_vendor_status_fetch_watermark.sql`
adds where the last LI-COR fetch ended and the latest answer's unreadable records; until it is applied the alert check
fails (logged, reported to Sentry and to `HEALTHCHECK_URL_ALERTS`) and ingestion carries on as before.

| Variable | Default | Meaning |
|---|---|---|
| `ALERT_STALE_HOURS_WEATHER`, `_LOGGER`, `_QUALITY` | `3`, `3`, `2` | Hours without a new reading before a sensor-silent alert. LI-COR uploads about hourly, so Weather and Logger readings are already up to an hour old when they arrive and 3 h means two missed uploads; WQData reports every 10 minutes during the day. The quiet hours and excluded series of the freshness check (`HEALTH_QUIET_HOURS_*`, `HEALTH_EXCLUDED_SERIES`) apply here too, so the sonde's usual night-time silence isn't an alert. |
| `ALERT_STALE_HOURS` | none | One limit for every group without its own `ALERT_STALE_HOURS_<GROUP>`. |
| `ALERT_VENDOR_FAILURES` | `3` | Failed ingestion runs in a row (10 minutes apart) before a vendor-down alert. |
| `ALERT_REMINDER_HOURS` | `24` | How often an ongoing incident is emailed again. |
| `ALERT_SUSPECT_HOURS` | `6` | The window of the suspect-values rules. `ALERT_SUSPECT_VALUES=off` turns those rules off. |
| `ALERT_CLEAR_MINUTES` | `30` | How long a condition must be gone before its incident clears and the "recovered" email goes out; also how long it must be back before "back again" goes out. |
| `ALERT_FLAP_CLEAR_MINUTES` | `180` | How long a condition must be gone before an incident that has had a "back again" clears; doubled with each further "back again", up to 12 h. |
| `ALERT_REOPEN_HOURS` | `6` | A condition that comes back within this long of clearing reopens its incident instead of being emailed as new. |
| `ALERT_EXCLUDED_SERIES` | none | Series to mute, e.g. during field work or while a sensor is out for the winter: `station:measurement` or `station:*`, comma-separated, like `HEALTH_EXCLUDED_SERIES` (e.g. `4501:*` or `2577533:Water Surface Elevation`). Only the alerts change; `/health/data` still reports the series. Open alerts for a muted series close without a "recovered" email. Remove the entry to unmute. |
| `ALERT_DASHBOARD_URL` | `https://welldash.mcmaster.ca/` | The dashboard link in the emails and the digest. |
| `ALERT_QUIET_KINDS` | `SUSPECT_VALUES` | Alert kinds whose recovery sends no email of its own, comma-separated (`VENDOR_DOWN`, `STALE_SENSOR`, `SUSPECT_VALUES`), or `none` to email every recovery. Such a recovery goes in the next email sent anyway (a new problem, reminder, back again or other recovery) within 24 h, and the daily digest lists it. New alerts of these kinds are still emailed at once. While a quiet recovery hasn't been emailed, a return of the same problem within `ALERT_REOPEN_HOURS` simply reopens it, without a "back again". |

An invalid value makes the alert check fail with a message naming the variable (in `logs/alerts.log`, Sentry and the
alerts heartbeat); recreate the worker after changing any of them.

```bash
# dashboard/backend/app/.env (example)
HEALTHCHECK_URL_INGESTION=https://hc-ping.com/your-check-uuid
HEALTHCHECK_URL_UPLOAD=https://hc-ping.com/your-check-uuid
HEALTHCHECK_URL_DIGEST=https://hc-ping.com/your-check-uuid
HEALTHCHECK_URL_ALERTS=https://hc-ping.com/your-check-uuid
ALERT_EMAILS=alerts@example.org,another@example.org
# SMTP_HOST=smtp.example.org
# SMTP_PORT=587
# SMTP_FROM=welldash@example.org
```

## Error reporting (Sentry)

Unexpected errors are reported to Sentry (organization `well-cs`, free tier), from the Flask API, the worker
scheduler, the Celery export worker and the dashboard (browser and Next.js server). Each backend event is tagged
`component` (`backend`, `worker` or `export_worker`); scheduler errors also carry `job` (e.g. `api_injection_job`)
and, for a vendor ingestion failure, `source` (`LI-COR` or `WQData`).

- **Sent:** the error type, message and stack trace (file and line, no local variables), the endpoint's method and
  path, the environment, and recent breadcrumbs (log lines, page changes and outgoing requests, with their query
  strings replaced by `[Filtered]`). For a failed scheduler subprocess, also its command, exit code and the last
  2,000 characters of its stderr (a traceback when the script crashed) and the `ERROR:` and `[ERROR]` lines it
  printed to stdout (its handled failures, e.g. "No sensor data found"; the rest of stdout is not sent).
- **Not sent:** request bodies, cookies, headers, query strings, IP addresses or any user identity
  (`send_default_pii` off, plus a `before_send` filter in `dashboard/backend/app/utils/sentry.py` and
  `dashboard/frontend/src/lib/sentry.ts`). No performance tracing and no session replay, so nothing counts against
  the free tier's transaction or replay quotas. Source maps are not uploaded, so dashboard stack traces show the
  minified code.

How backend failures are reported:
- The scheduler runs the Borealis download, the monthly upload and the daily digest as subprocesses with
  `SENTRY_DSN` emptied, so those scripts never report themselves. When one fails or times out, the scheduler sends
  a single event for it. Most of those scripts catch their errors and exit non-zero, so a script reporting
  itself would miss them, and a crash would be sent twice (the script's traceback plus the scheduler's
  `CalledProcessError`).
- A caught failure (a job, or one vendor's ingestion) is sent at most once an hour for the same job, vendor, error
  type and message (its first line with numbers collapsed, HTTP statuses kept; for a failed subprocess, its arguments
  such as the month, its exit code, and its last stderr line or, with no stderr, its last `ERROR:` or `[ERROR]`
  stdout line). So an outage that fails every 10-minute run sends about 24 events a day per vendor instead of 144,
  while a different error is still sent at once. This limit covers only these scheduler failures; Flask and Celery
  errors are sent each time.
- A script run by hand (`docker compose exec worker python scripts/...`) reports its own uncaught errors, tagged
  with the container's `SENTRY_COMPONENT`.

Settings:
- Backend, in `dashboard/backend/app/.env` (read by `backend`, `worker` and `export_worker`): `SENTRY_DSN` (unset or
  empty turns reporting off; tests and local runs leave it unset, and the test suite removes it), `SENTRY_ENVIRONMENT`
  (default `production`) and, optionally, `GIT_SHA` as the release. `SENTRY_COMPONENT` (the `component` tag, default
  `backend`) is set in `docker-compose.yml` for `worker` and `export_worker`.
- Dashboard: `NEXT_PUBLIC_SENTRY_DSN` and `NEXT_PUBLIC_SENTRY_ENVIRONMENT` (default `production`), build args in
  `dashboard/frontend/Dockerfile`. The DSN defaults to the dashboard project's key. It is inlined into the browser
  bundle at build time, which is fine: a DSN can only send events. When you build an image for local testing, use
  `docker build --build-arg NEXT_PUBLIC_SENTRY_ENVIRONMENT=development dashboard/frontend` (or
  `--build-arg NEXT_PUBLIC_SENTRY_DSN=` to send nothing), so its errors aren't filed as production. `next dev` and
  `next build` outside Docker send nothing unless `NEXT_PUBLIC_SENTRY_DSN` is set.

Quota: the free tier allows 5,000 errors a month. In Sentry, turn on *Settings > Spike Protection* for the
organization. Also give each project's key a rate limit under *Project Settings > Client Keys (DSN) > Configure > Rate
Limits*, for example 100 events an hour, so one noisy failure can't use up the month.

To rotate a key, create a new client key under the Sentry project's *Settings > Client Keys (DSN)*, put it in the
`.env` (backend) or the Dockerfile default (dashboard), redeploy (`docker compose up -d --build --no-deps backend
worker export_worker` or `dashboard`), then disable the old key. To turn reporting off, empty `SENTRY_DSN` and
recreate the three backend containers, or build the dashboard with `--build-arg NEXT_PUBLIC_SENTRY_DSN=`; disabling
the key in Sentry also stops everything at once. In the Sentry project settings, keep *Prevent storing of IP
addresses* on as a second guard.

## Database backups

The PostgreSQL database (on the VM host, outside Docker) is the only complete copy of the data, and some of it can't
be fetched again: LI-COR serves at most one year of history. So the worker backs it up every night.

- **When**: 03:15 Toronto time, every night (`scripts/backup_db.py`, run by the scheduler; its output goes to
  `logs/backup.log`). It pings `HEALTHCHECK_URL_BACKUP` when it starts and again when it ends (`/fail` if it failed),
  and a failure is reported to Sentry.
- **What**: `pg_dump -Fc` (PostgreSQL's compressed custom format) of every table the role in `DATABASE_URL` can read
  (on the VM that is `postgres`, so the whole database), made with `pg_dump` 13, the server's version (the backend
  image installs `postgresql-client-13` from the PostgreSQL apt repository). The password reaches `pg_dump` through a
  temporary 0600 password file, never its command line.
- **Where**: `~/WELLWebsite/backups/welldb-YYYYmmdd-HHMM.dump` on the VM (`/app/backups` in the worker; the folder is
  gitignored). The files are readable by root only (the container runs as root, and the job sets `umask 077`), so use
  `sudo` on the host.
- **Checked**: each dump is written as a hidden `.partial` file, then read back with `pg_restore --list` (it must list
  data for `sensor_measurements` and `sampling_measurements`, `BACKUP_EXPECT_TABLES`) and in full, and only then
  renamed. A failed run leaves no file that looks like a backup, and the next run deletes an unfinished one left by a
  run that was killed. Each step has its own time limit (dump 80 min, checks 10 and 15 min), within the scheduler's
  2 h for the whole run. Only one backup runs at a time (a lock file, `.backup.lock`). If deleting old dumps fails
  after a good backup, the run still counts as a success and logs a `WARNING:` line, which also goes to Sentry as a
  warning.
- **Row counts**: a dump of an emptied table still lists data for it, so before dumping, the job also counts the
  rows of those tables (exactly for tables under a million rows; for larger ones, PostgreSQL's estimate right after
  an `ANALYZE`, or the older estimate with a `WARNING:` line if `ANALYZE` waits more than 30 s for its lock) and compares them with the counts at the last good backup, kept in `backups/.row-counts.json`. If a
  table is empty or has more than 5% fewer rows (`BACKUP_MAX_SHRINK_PCT`; these tables only grow, and 5% is well
  above the estimate's error), the dump is still written and checked, but the run fails (`/fail` ping, Sentry) and
  the counts aren't recorded, so the following nights fail too until someone looks. Retention doesn't run then, so
  no good dump is deleted. Each failing dump is listed as such in `.row-counts.json`, and only those listed are
  deleted by the next failing night, so just the newest failing dump is kept next to all the good ones and they
  don't pile up. Every other successful dump is recorded as good, also while the comparison is off. If the rows
  were removed on
  purpose, run `docker compose exec worker python scripts/backup_db.py --accept-row-counts` once: it records the new
  counts, with a `WARNING:` line naming what was accepted. `BACKUP_MAX_SHRINK_PCT=off` turns the comparison off.
- **Retention**: the newest dump of each of the last 7 days (`BACKUP_KEEP_DAILY`) and of each of the last 8 ISO weeks
  (`BACKUP_KEEP_WEEKLY`), so at most 15 files. Only files named `welldb-YYYYmmdd-HHMM.dump` are ever deleted, and only
  after a new dump has passed its check; a dump you copy in under another name (e.g. `manual-before-migration.dump`)
  stays. The job refuses to start if a dump the size of the last one would leave less than `BACKUP_MIN_FREE_MB`
  (default 2048) free, since the database shares the disk.

**Tables the role can't read are left out, and named.** `pg_dump` locks and reads every table it dumps, so by default
(`BACKUP_EXCLUDE_TABLES` unset or `auto`) the job leaves out any table or sequence the connecting role can't read, and
prints a `WARNING:` line naming them (in `logs/backup.log`, and sent to Sentry as a warning); the backup still counts
as a success. On the VM the app connects as `postgres`, which reads everything, so nothing is left out. With a more
limited role, tables created by migrations or by hand as `postgres` (`schema_migrations`, `vendor_status`,
`alert_incidents`, `export_jobs`, `data_fixes`, `request_metrics`, `uptime_probes`) would be named. Grant that role
`SELECT` on them (and on any sequence they own), or dump them now and then as `postgres` on the host, e.g.
`sudo -u postgres pg_dump -Fc -t export_jobs -t data_fixes -f /tmp/well-postgres-tables.dump <database>`. Setting
`BACKUP_EXCLUDE_TABLES` to a comma-separated list leaves out exactly those, with no warning; an empty value leaves out
nothing, and the dump then fails if anything is unreadable.

**Run a backup by hand** (e.g. before a migration): `docker compose exec worker python scripts/backup_db.py
--no-prune`. `--prune-only` applies retention without dumping.

**Restore drill** (optional; once a month is plenty): `docker compose exec worker python scripts/restore_check.py`
restores the newest dump (or `--file /app/backups/<name>`) into a throwaway database, `welldb_restore_check` (another
name given with `--database` must start with that, since the drill drops it first), compares each table's row count
with the live database (read-only), and drops it again. Counts that grew since the dump are expected; a table missing
from the restore or restored empty fails the drill, unless it was left out on purpose (`BACKUP_EXCLUDE_TABLES`) or
because the role can't read it. Creating a database needs the `CREATEDB` privilege, which `postgres` (the app's role
on the VM) has; for another role, grant it once (as `postgres`: `ALTER ROLE <app role> CREATEDB;`), or set
`RESTORE_CHECK_DATABASE_URL` to a URL for a role that has it, which then creates, restores into and drops the
throwaway database. Without either, the drill stops with a message saying so. A restore takes about as much disk as
the live database, so the drill first checks that the backup folder's disk (the database's, on the VM) has that plus
`BACKUP_MIN_FREE_MB` free; `--no-space-check` skips this when the database is on another disk.

**Restoring for real.** Restore into a new, empty database, put back anything the dump left out, then point the app at
it. `<app role>` is the role in `BACKEND_DATABASE_URL` (`postgres` on the VM).

```bash
cd ~/WELLWebsite
docker compose stop worker export_worker      # nothing writes while you switch over
sudo -u postgres createdb -O <app role> welldb_restored
sudo cat backups/welldb-YYYYmmdd-HHMM.dump | sudo -u postgres pg_restore --no-owner --role=<app role> --exit-on-error -d welldb_restored
```

The next steps matter only if that night's `logs/backup.log` has a `WARNING:` line saying tables were left out. On the
VM the app connects as `postgres`, so normally nothing was. If `data_fixes` was left out and you kept a dump of it made
as `postgres` (see above), restore that:
`sudo cat /path/to/well-postgres-tables.dump | sudo -u postgres pg_restore --exit-on-error -d welldb_restored`. If
not, recreate it with a row for each dated fix that had run, so none can run a second time; without its row, running
`2026-11-10_swap_air_soil_temperature.sql` again would swap air and soil temperature back. Each fix's name is in the
`INSERT INTO data_fixes` line of its file in `dashboard/backend/app/db/migrations/`. These statements are safe to run
even if the table came back with the dump:

```bash
sudo -u postgres psql -d welldb_restored -v ON_ERROR_STOP=1 \
  -c "CREATE TABLE IF NOT EXISTS data_fixes (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())" \
  -c "INSERT INTO data_fixes (name) VALUES ('2026-11-10 swap air and soil temperature') ON CONFLICT (name) DO NOTHING"
```

Then switch over:

```bash
# In ~/WELLWebsite/.env, change the database name in BACKEND_DATABASE_URL to welldb_restored. Then create any of the
# app's tables still missing (e.g. export_jobs, if it was left out): db/init_db.py runs create_all(), which creates
# missing tables only and never changes existing ones, so it is harmless when nothing is missing.
docker compose run --rm --no-deps backend python db/init_db.py
# Recreate the containers so they read the new URL. Until then the backend keeps serving the old database.
docker compose up -d backend worker export_worker
```

The next ingestion runs continue from the newest reading in the restored database, within their look-back limit; fill
a longer gap with `scripts/licor_backfill.py` and `scripts/wqdata_backfill.py` (LI-COR only as far back as its one-year
limit).

**Off-VM copies.** These dumps sit on the VM's own disk, so they protect against mistakes (a bad migration or fix,
deleted rows), not against losing the VM. The monthly CSVs on Borealis and SharePoint
([Off-VM copies](#off-vm-copies-borealis-and-sharepoint)) hold the sensor readings off the VM. Borealis is public, so
dumps never go there. To keep a whole dump off the VM, copy one by hand to private storage, e.g.
`ssh <vm> 'sudo cat ~/WELLWebsite/backups/<name>.dump' > <name>.dump`.

## Database migrations

New tables are created by `db.create_all()` (`dashboard/backend/app/db/init_db.py`), which never changes a table that
already exists. Changes to existing tables (an index, a new column) go in a numbered SQL file in
`dashboard/backend/app/db/migrations/` (`0001_name.sql`, `0002_name.sql`, ...), applied with `scripts/migrate.py`. It
runs the files that haven't run yet, in order, and records each in the `schema_migrations` table so none runs twice.
Nothing applies them automatically; on the VM, run them by hand. The steps below are for online migrations, such as
adding an index, which the running code doesn't depend on. A migration whose notes (in this section or the file's
comments) give its own procedure, for example one the new code can't start without, follows those notes instead
(typically: stop the services, run `migrate.py` with the new image, then start them).

```bash
cd ~/WELLWebsite
./deploy.sh                                                       # pull main, rebuild backend (the migration files are baked into the image)
docker compose exec worker python scripts/backup_db.py --no-prune   # a backup first (see Database backups)
docker compose exec backend python scripts/migrate.py --status   # what has run and what is pending
docker compose exec backend python scripts/migrate.py --dry-run  # the SQL that would run
docker compose exec backend python scripts/migrate.py            # apply
```

- The first step is needed because `docker compose exec backend` only sees the files in the running image.
  `./deploy.sh` by hand deploys a commit that `--auto` held for its migration (see
  [docs/deploying.md](../../docs/deploying.md)); it rebuilds `backend`, `worker` and `export_worker`, which restarts
  gunicorn, so the API returns errors for a few seconds. Older notes use `./git_pull.sh`, a helper that exists only on
  the VM, not in this repository: it sets up the GitHub SSH key and runs `git pull`, without rebuilding anything or
  checking the site, so use `deploy.sh` instead.
- Each file runs in one transaction, so a failed migration leaves nothing half-done. A file whose first line is
  `-- migrate: no-transaction` runs outside a transaction instead, as `CREATE INDEX CONCURRENTLY` requires; such a
  file holds one statement.
- Indexes are built with `CONCURRENTLY`, which doesn't block reads or inserts, so the index build itself needs no
  downtime: the site and the ingestion keep running while it builds.
- If a concurrent index build fails part way, PostgreSQL leaves an INVALID index behind. When that index is one the
  migration names, the runner refuses to record the migration, names the index and exits with an error: drop it with
  `DROP INDEX CONCURRENTLY <name>;` and run the migration again. Invalid indexes the migration doesn't name only get a
  warning.
- A second run at the same time refuses to start ("another migrate.py run holds the lock", a PostgreSQL advisory
  lock) and exits with an error; run it again once the first has finished. It doesn't wait, because a waiting run
  would stall the first run's concurrent index build.
- Never rename or renumber a file once it has been applied: the runner identifies migrations by file name and would
  run it again. Two files with the same number are refused.
- Dated files such as `2026-11-10_swap_air_soil_temperature.sql` are one-off data fixes, run by hand with `psql` as
  their comments describe; the runner ignores them.
- When a migration changes the schema, change `db/models.py` to match, so a fresh database built by `create_all()`
  gets the same result.

## AI analysis (disabled)

> **Currently disabled; the code is kept.** Nothing calls OpenAI and the `openai` package is not installed. The UI
> entry points (`dashboard/frontend/src/pages/index.tsx`, `components/Modal.tsx`, `components/Information.tsx`) and
> the route registration in `dashboard/backend/app/api/routes/__init__.py` are commented out, each marked
> `AI ANALYSIS DISABLED`; the backend routes in `dashboard/backend/app/api/routes/analysis/` are not imported, and the
> four Next.js proxies in `dashboard/frontend/src/pages/api/analysis/` answer 404.

To turn it back on:

1. Search the code for `AI ANALYSIS DISABLED` and uncomment those blocks.
2. Delete the 404 stubs at the top of `dashboard/frontend/src/pages/api/analysis/*.ts` (their original handlers are
   commented out below them).
3. Add `openai` back to `dashboard/backend/requirements.txt` (it was pinned at `openai==2.30.0`, with its
   dependencies; see the note in that file) and set `OPENAI_API_KEY`.
4. Rebuild the summaries the analysis routes read. `latest_summaries` (filled after each `/api/data` request) and
   `latest_sampling_summaries` (after each `/api/samples` request) were deleted in commit `5b501eb`, not commented
   out, so uncommenting alone gives the routes nothing to summarise. The old code is in the commit before it:
   `git show 5b501eb^:dashboard/backend/app/api/routes/data.py` (and `samples.py`).
5. Rebuild the backend and dashboard images, and restore the OpenAI mentions in the privacy/disclaimer text.

When it was on, an API endpoint aggregated and downsampled a series (`scripts/downsample.py` was written for it and is
kept with it) and sent a bounded prompt with metadata to the OpenAI API to generate human-readable summaries of trends,
anomalies, and ranges. The frontend rendered the output inside an analysis modal and allowed exporting the narrative.

## Tests

From `dashboard/backend`, with the requirements installed:

```bash
python -m unittest discover -s tests -t .
```

CI runs them inside the backend image on every pull request ("Backend image and tests" in
[.github/workflows/README.md](../../.github/workflows/README.md#ci)), with throwaway PostgreSQL 13 databases in
`TEST_POSTGRES_URL` and `MIGRATE_TEST_DATABASE_URL`. Locally, the tests that need those are skipped when they are
unset (CI fails if they are skipped). The file formats people depend on are pinned by the
[golden files](tests/golden/README.md); `tests/test_api_canary.py` checks that the canary's copies of a few parser
constants still match ingestion.
