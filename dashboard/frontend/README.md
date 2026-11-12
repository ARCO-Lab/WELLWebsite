# WELL dashboard (Next.js)

The dashboard at [welldash.mcmaster.ca](https://welldash.mcmaster.ca), also shown inside the WordPress site's Dashboard
page. Its data comes from the [backend](../backend/README.md); its settings are in
[docs/configuration.md](../../docs/configuration.md#dashboard-nextjs).

## Stack

- **Next.js** 16 (pages router) with **TypeScript**, **React** 19 and **Tailwind CSS**, built as a standalone Node
  server (`dashboard/frontend/Dockerfile`).
- **Highcharts** for the time-series charts (`src/components/graphs/`) and the wind rose; the station map is
  **MapLibre GL** with OpenFreeMap tiles (`src/components/map/Map.tsx`).
- No server-side data fetching: custom React hooks (`src/hooks/`) load the data in the browser, from the dashboard's
  own API routes (`src/pages/api/`). Each route passes the request on to Flask (`src/lib/proxyBackend.ts`), so the
  browser never talks to Flask directly. The routes and what the backend answers are listed in
  [the backend README](../backend/README.md#api).

## Charts

Each chart zooms and pans on its own (`src/hooks/useChartWindow.ts`, `src/lib/chartController.ts`, with a slider and
toolbar per chart). Charts read `/api/series` in fixed tiles of a few hundred buckets at the resolution they show
(`src/lib/seriesTiles.ts`). One loader for the whole page (`src/lib/seriesLoader.ts`) caches tiles, asks for each
missing tile once, batches neighbouring tiles and charts that need the same ones into one request, keeps at most two
requests in flight (the visible charts first), drops queued requests no chart wants any more, and refetches a tile
still filling with new readings after a minute. Each series says what its `avg` array holds (`mean`; `sum` for Rain;
`vector_mean` for Wind Direction, whose `min`/`max` are null). The wind rose (`src/hooks/useWindRose.ts`) reads
`/api/windrose`, which the backend counts in PostgreSQL, so any range is a few hundred numbers. Picked days and
chart times are Toronto (site) time whatever the visitor's time zone (`src/utils/siteTime.ts` and
`src/utils/chartWindow.ts`, tested by `scripts/*.test.mjs`).

## Development

```bash
cd dashboard/frontend
npm ci
FLASK_API_URL=http://localhost:5000 npm run dev    # FLASK_API_URL: your backend
npx tsc --noEmit                                    # type check
npm test                                            # unit tests: chart helpers, site time, the tile loader, the backend proxy,
                                                    # sampling fetches, export polling, shared-link ticks
npm run lint
npm run build
```

`FLASK_API_URL` is inlined at build time (`next.config.ts`), so set it before `next dev` or `next build`. CI runs the
type check, the unit tests, the build and the lint on every pull request ("Dashboard build"), and builds and starts
the image ("Dashboard image").

## Error reporting

Browser and Next.js server errors go to Sentry (`src/lib/sentry.ts`, `src/instrumentation*.ts`), with the same filters
as the backend: no request bodies, cookies, headers, query strings or IP addresses. `NEXT_PUBLIC_SENTRY_DSN` and
`NEXT_PUBLIC_SENTRY_ENVIRONMENT` are build args; build local images with
`--build-arg NEXT_PUBLIC_SENTRY_ENVIRONMENT=development` (or `--build-arg NEXT_PUBLIC_SENTRY_DSN=` to send nothing).
What is sent, quotas and key rotation are in
[the backend README](../backend/README.md#error-reporting-sentry).

## Visitor counts (GoatCounter)

Page views on both sites are counted with [GoatCounter](https://www.goatcounter.com), in one GoatCounter site,
`well` (statistics at https://well.goatcounter.com; welldash²'s Visitors page shows them once
`OPS_GOATCOUNTER_TOKEN` is set). GoatCounter sets no cookies and stores nothing in the browser; it keeps aggregated
counts of pages, referrers, browsers, screen sizes and countries, and no IP addresses or other personal data.

- **Paths start with the host**, since both sites have a `/`: `welldash.mcmaster.ca/` is the dashboard,
  `well.mcmaster.ca/news/` a WordPress page. Query strings are left out of the path. (GoatCounter's script still
  sends the query string separately; GoatCounter reads only campaign parameters such as `utm_source` from it.)
- **Dashboard:** `src/components/VisitorCount.tsx` loads GoatCounter's script and counts the first page load and each
  move to another page; a change of query alone (`?from=&to=`) or a chart zoom isn't a page view. It counts only in a
  production build with `NEXT_PUBLIC_GOATCOUNTER_ENDPOINT` set (the Dockerfile's default) and only when the page is
  served from welldash.mcmaster.ca, so local, preview, CI and e2e runs send nothing. The dashboard shown inside
  WordPress's Dashboard page isn't counted a second time: GoatCounter's script skips pages shown in a frame, and the
  WordPress page around it is counted.
- **WordPress:** `well_goatcounter_script()` in the theme's `functions.php` adds the script to every public page,
  except for logged-in users and previews, and counts only on well.mcmaster.ca. Theme files are mounted into the
  container, so a change is live once it is pulled, with no restart.
- **Turning it off:** build the dashboard with `--build-arg NEXT_PUBLIC_GOATCOUNTER_ENDPOINT=`, and remove the
  `add_action('wp_footer', 'well_goatcounter_script')` line from the theme. One browser can opt out of a site by
  opening its address with `#toggle-goatcounter` at the end (GoatCounter's switch, kept in that browser).

## End-to-end tests

`dashboard/e2e/` checks that what the vendors send is exactly what the dashboard shows: in the database, in the charts'
data and tooltip, in the Latest Data tiles and in the downloaded CSV. The CI job "End-to-end data (vendors to browser)"
(`.github/workflows/ci.yml`) runs it on every pull request:

1. `vendor_stub.py` answers as LI-COR and WQData from `fixtures/licor.json` and `fixtures/wqdata.json`, accepting only
   the made-up keys and ids the job configures.
2. `ingest.py` runs the real 10-minute ingestion against the stub, at the times in `fixtures/expected.json`, into a
   throwaway PostgreSQL 13 in UTC (so any dependence on the session time zone fails).
3. The backend image and the built dashboard (`next start`) are started, and Playwright (`data.spec.ts`) checks the
   page in Toronto, Tokyo and London browsers, which must all see the same Toronto times. `charts-stress.spec.ts`
   (one browser zone) checks that fast zooming and panning, with `/api/series` slowed down, sends few requests, never
   more than two at a time, and keeps charts independent; `STRESS_MINUTES=5 npx playwright test charts-stress
   --project=toronto` runs a longer soak. `sampling.spec.ts` answers every API call itself (no data needed, so it also
   runs against `next dev` alone with `E2E_BASE_URL`): the sampling tab's charts and legend, replies arriving out of
   order, a shared link's ticks, the Download button leaving its tab, and an axe accessibility scan of both tabs.

`fixtures/expected.json` lists every expected row and tile, with notes on the cases they cover (the clocks going back,
duplicates, re-reads, N/A values, readings near midnight). To run it yourself, start the same pieces as the CI job and
run `npm ci && npx playwright test` in `dashboard/e2e`, with `E2E_DATABASE_URL` and `E2E_BASE_URL` pointing at them.
