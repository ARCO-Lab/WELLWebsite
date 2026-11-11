# Load testing the dashboard

How the dashboard copes when many people open it at once (a class of 30, say), measured on a throwaway copy of
the stack in GitHub Actions. **It never touches production**: the workflow starts its own PostgreSQL, Redis,
backend, export worker and dashboard on the runner, filled with synthetic readings.

## What it runs

`.github/workflows/load-test.yml` (Actions > **Load test**):

1. PostgreSQL 13 (the production version, default settings) seeded by `dashboard/loadtest/seed.sql` with the real
   layout: 29 series (11 weather, 8 water quality, 5 loggers x 2), one reading every 10 minutes. The default
   4 years is about 6.1M rows, more than the site holds, so the table and indexes are bigger than in production.
2. Redis, the backend image as the VM builds it, with its own gunicorn command (3 workers x 4 threads), the
   25 s statement timeout and the `/api/series` cache, and the export worker (celery, 2 at a time), as
   `docker-compose.yml` runs them.
3. The dashboard, built and served by `next start`. k6 talks to it, as browsers do, so every API request goes
   through the Next.js proxy to the backend.
4. k6 (`dashboard/loadtest/page-load.js`) plays page views. Each virtual user is a new visitor with its own
   IP address (sent as `X-Forwarded-For`, which the test's Next.js server is told to trust) and no browser cache:
   the page, `/api/latest` and `/api/recent`; a few seconds later the chart overview for a 1-day, 1-week,
   1-month or 1-year range (half ending today, which visitors share and the cache answers; half ending on a random
   day, computed afresh); 3-5 zooms (detail requests, only when finer than the overview, as the page does);
   sometimes the wind rose's raw readings (`/api/data`); and 1 in 10 a small CSV export through the export queue
   (estimate, job, status polls, download).
5. Three phases: **30 at once** (everyone opens the page in the same second, one page view each), **30 steady**
   (ramp from 1 to 30 over a minute, then 3 minutes at 30) and **50 steady** (30 to 50 over a minute, then
   2 minutes at 50). Visitors pause 1-8 s between actions, as people do.
6. Every 5 s a sampler records CPU and memory of each container and of the Next.js server, PostgreSQL's
   connections and the export queue.

The whole job takes about 15 minutes.

## How to run it

From the Actions tab: **Load test > Run workflow**, choose the branch and, if you like, change the inputs:

| Input | Default | What it does |
|---|---|---|
| `years` | 4 | Years of synthetic history (about 1.5M rows a year) |
| `class_vus` | 30 | Visitors in "30 at once" and "30 steady" |
| `peak_vus` | 50 | Visitors in the peak phase |
| `backend_cpus` | (none) | A CPU limit for the backend container, e.g. `2`, to see how a smaller machine copes |

Or from a terminal: `gh workflow run load-test.yml --ref <branch> -f backend_cpus=2`.

A weekly run (Mondays 06:00 UTC) is off by default; set the repository variable `LOAD_TEST_WEEKLY` to `true`
(Settings > Secrets and variables > Actions > Variables) to turn it on.

## Reading the results

The run's **summary page** has everything; the artifact `load-test-results` has the details:
`report.html` (k6's charts over time; open it in a browser), `summary.json` (every k6 metric), `summary.md`,
`resources.csv` (the 5-second samples), and the backend, export worker and Next.js logs.

- **Per endpoint, per phase**: request count, p50/p95/p99/max latency and the share that failed. `/api/series`
  is split three ways: *shared* (ranges ending today, which the Redis cache answers after the first visitor),
  *cold* (ranges ending on a random day, which PostgreSQL computes) and *zoom* (detail requests, also cold).
- **Error answers**: any status the page would show as an error. Export requests refused with 429 are not errors:
  the queue's limits (2 per visitor, 6 in total, 2 built at a time) are meant to refuse them under load, and they
  are counted on their own line, with how long accepted exports waited.
- **Warnings** (they never fail the job), at 30 visitors: p95 of `/api/latest` under 300 ms, of shared
  `/api/series` under 2 s, of cold `/api/series` under 5 s, and error answers under 1%.
- **Resources**: CPU as % of one core, average and peak per phase, and memory. A backend CPU near
  `100% x cores` (or near the `backend_cpus` limit x 100%) means it is the bottleneck. PostgreSQL's active
  connections show how many queries ran at once; the backend's 12 threads (3 workers x 4) run at most 12, the
  export worker 2 more.

The runner is not the VM: GitHub's runners have 4 CPUs and 16 GB, and PostgreSQL runs in a container with its
default settings. Compare CPU in cores rather than percentages, and use `backend_cpus` to approximate a smaller VM.

## If the limits are hit

Look at which resource ran out first:

- **Requests queue in the backend while its CPU is low** (slow p95 everywhere, including `/api/latest`, while
  PostgreSQL is busy): all 12 gunicorn threads are waiting on slow queries. Raise `--threads` in
  `dashboard/backend/Dockerfile` (cheap; each thread can hold a database connection, so keep
  workers x threads well under PostgreSQL's `max_connections`, 100 by default, and SQLAlchemy's pool of 15 per
  worker).
- **The backend's CPU is at its limit** (JSON encoding of large `/api/series` answers is the main cost): add
  gunicorn workers (`-w`; about one per core, each ~150 MB), or run a second backend container. With Compose,
  `docker compose up -d --scale backend=2` gives two; the dashboard reaches them through Docker's DNS name
  `backend`, which returns both addresses (Node's fetch uses one per new connection, so the spread is rough).
  Remove `container_name` if one is ever set on the service, or scaling fails.
- **PostgreSQL's CPU is at its limit** (cold `/api/series` and zooms slow, cached ones fast): the cache is doing
  its job and the database is the limit. Lengthen the cache times in `dashboard/backend/app/api/routes/series.py`
  (`MAX_AGE_RECENT`, `MAX_AGE_PAST`) so more visitors share answers, or give PostgreSQL more memory
  (`shared_buffers`, `work_mem`) on the VM. More backend containers won't help here.
- **`/api/latest` is slow**: it is not cached on the server (browsers keep it for a minute). A short Redis cache
  like the one `/api/series` has would make it one query a minute however many visitors there are.
- **Many export 429s, or exports wait long**: that is the queue protecting the server. Raise
  `EXPORT_MAX_ACTIVE_JOBS` and the export worker's `--concurrency` together only if the VM has CPU and memory to
  spare while exports run.
- **Open PostgreSQL connections keep climbing while few queries run**: a process opens connections and keeps
  them. The summary lists which processes hold connections when the run ends; each gunicorn worker should hold
  only a handful.
- **The Next.js server's CPU is at 100% of one core**: it is a single Node process. Run a second dashboard
  container behind the front proxy.

After a change, run the workflow on its branch and compare the two summaries.
