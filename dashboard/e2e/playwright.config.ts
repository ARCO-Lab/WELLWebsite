// End-to-end data checks: vendor fixtures -> ingestion -> PostgreSQL -> Flask API -> Next.js -> browser.
//
// The CI job "End-to-end data" (.github/workflows/ci.yml) starts everything this needs, then runs `npm test` here:
//   - vendor_stub.py, answering as LI-COR and WQData from fixtures/
//   - ingest.py, the real ingestion run against the stub (three runs), into a throwaway PostgreSQL in UTC
//   - the backend (gunicorn) on :5000 and the built dashboard (next start) on :3000
// E2E_BASE_URL and E2E_DATABASE_URL point the tests at them.
//
// The same checks run in three browser time zones. The site's data is Toronto time whatever the visitor's zone is,
// so Tokyo (ahead of UTC, past midnight already) and London (UTC in November) must see exactly what Toronto sees.

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    locale: "en-US",
    reducedMotion: "reduce", // no chart animations or scrolling strips: the clock is frozen (see the spec)
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "toronto", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 }, timezoneId: "America/Toronto" } },
    { name: "tokyo", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 }, timezoneId: "Asia/Tokyo" } },
    { name: "london", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 }, timezoneId: "Europe/London" } },
  ],
});
