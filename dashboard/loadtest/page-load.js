// k6 load test of the dashboard: virtual visitors doing what a browser does on a page view, through the Next.js
// server (the same path as real visitors) to the backend, Redis and PostgreSQL. Run by
// .github/workflows/load-test.yml against a throwaway copy seeded by seed.sql. Never point it at production:
// BASE_URL defaults to localhost, and the exports it queues would compete with real visitors' exports.
//
// Each iteration is one page view by a new visitor (no browser cache, its own IP address):
//   1. the page, then /api/latest and /api/recent at once, as the page does on load;
//   2. a few seconds later, the chart overview for the groups and days picked: half the time a range ending today
//      (1 day, 1 week, 1 month or 1 year: views many visitors share, so mostly answered from the Redis cache),
//      otherwise the same lengths ending on a random day of the history (almost always computed afresh);
//   3. 3-5 zooms, each a detail request for the window plus half its width either side, as useChartSeries makes
//      (only when the window needs finer buckets than the overview, as in the browser);
//   4. sometimes (15%) the wind rose's raw readings (/api/data, weather only, for ranges up to a month);
//   5. sometimes (10%) a small CSV export through the export queue: estimate, job, status polls, download.
//      The page uses the direct (sync) export for anything this small; the queue is used here on purpose, to
//      see its limits under load. 429 answers (too many queued exports) are expected and counted on their own.
//
// Scenarios, one after another:
//   burst30  30 visitors open the page at the same moment (a class told to open it), one page view each;
//   class30  1 -> 30 visitors over RAMP_S, then 30 for CLASS_HOLD_S;
//   peak50   30 -> 50 visitors over RAMP_S, then 50 for PEAK_HOLD_S.
// Every request is tagged with an endpoint name; handleSummary writes per-endpoint, per-scenario tables
// (summary.md) and the warnings below. Thresholds never fail the run: they are reported as warnings.

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const OUT = (__ENV.OUT_DIR || ".").replace(/\/$/, ""); // where handleSummary writes summary.md and summary.json
const BASE = (__ENV.BASE_URL || "http://127.0.0.1:3000").replace(/\/$/, "");
const num = (name, fallback) => Number(__ENV[name] || fallback);
const BURST_VUS = num("BURST_VUS", 30);
const CLASS_VUS = num("CLASS_VUS", 30);
const PEAK_VUS = num("PEAK_VUS", 50);
const BURST_S = num("BURST_S", 120); // longest the burst may take
const RAMP_S = num("RAMP_S", 60);
const CLASS_HOLD_S = num("CLASS_HOLD_S", 180);
const PEAK_HOLD_S = num("PEAK_HOLD_S", 120);
const GAP_S = 30; // between scenarios, so the previous one's last page views (gracefulStop) are done
const EXPORT_SHARE = num("EXPORT_SHARE", 0.1);
const WINDROSE_SHARE = num("WINDROSE_SHARE", 0.15);
const EXPORT_WAIT_S = 90; // a visitor gives up on an export after this long

// Start and end of each scenario, in seconds from the start of the run; the resource sampler's summary
// (resources-summary.sh) uses the same windows, passed to it by the workflow.
const CLASS_START = BURST_S + GAP_S;
const PEAK_START = CLASS_START + RAMP_S + CLASS_HOLD_S + GAP_S;
const SCENARIOS = {
  burst30: { label: `${BURST_VUS} visitors at once`, seconds: BURST_S },
  class30: { label: `ramp to ${CLASS_VUS}, then ${CLASS_VUS} for ${CLASS_HOLD_S} s`, seconds: RAMP_S + CLASS_HOLD_S },
  peak50: { label: `ramp to ${PEAK_VUS}, then ${PEAK_VUS} for ${PEAK_HOLD_S} s`, seconds: RAMP_S + PEAK_HOLD_S },
};

const ENDPOINTS = [
  ["page", "GET / (HTML)"],
  ["latest", "/api/latest"],
  ["recent", "/api/recent"],
  ["series_shared", "/api/series overview, range ending today (shared, mostly cached)"],
  ["series_unique", "/api/series overview, range ending on a random day (cold)"],
  ["series_zoom", "/api/series zoom detail (cold)"],
  ["data_windrose", "/api/data wind rose"],
  ["export_estimate", "POST /api/exports/estimate"],
  ["export_create", "POST /api/exports/jobs (202 or 429)"],
  ["export_status", "GET /api/exports/jobs/<id>"],
  ["export_download", "GET /api/exports/jobs/<id>/download"],
];

// Warnings, at 30 visitors (class30); the run passes regardless.
const WARN = {
  latest: { p95: 300 },
  series_shared: { p95: 2000 },
  series_unique: { p95: 5000 },
  series_zoom: { p95: 5000 },
  errorRate: 0.01,
};

// Submetrics only appear in the summary data when a threshold names them; these always pass.
const thresholds = { http_req_failed: ["rate>=0"], unexpected_errors: ["rate>=0"] };
for (const scenario of Object.keys(SCENARIOS)) {
  thresholds[`http_req_failed{scenario:${scenario}}`] = ["rate>=0"];
  thresholds[`http_reqs{scenario:${scenario}}`] = ["count>=0"];
  thresholds[`unexpected_errors{scenario:${scenario}}`] = ["rate>=0"];
  thresholds[`first_chart{scenario:${scenario}}`] = ["max>=0"];
  for (const [endpoint] of ENDPOINTS) {
    thresholds[`http_req_duration{scenario:${scenario},endpoint:${endpoint}}`] = ["max>=0"];
    thresholds[`http_req_failed{scenario:${scenario},endpoint:${endpoint}}`] = ["rate>=0"];
  }
  for (const name of ["exports_queued", "exports_rejected_429", "exports_ready", "exports_failed", "exports_gave_up"]) {
    thresholds[`${name}{scenario:${scenario}}`] = ["count>=0"];
  }
  thresholds[`export_wait{scenario:${scenario}}`] = ["max>=0"];
}

export const options = {
  scenarios: {
    burst30: {
      executor: "per-vu-iterations", vus: BURST_VUS, iterations: 1, maxDuration: `${BURST_S}s`, gracefulStop: "30s",
    },
    class30: {
      executor: "ramping-vus", startTime: `${CLASS_START}s`, startVUs: 1, gracefulRampDown: "30s", gracefulStop: "30s",
      stages: [{ duration: `${RAMP_S}s`, target: CLASS_VUS }, { duration: `${CLASS_HOLD_S}s`, target: CLASS_VUS }],
    },
    peak50: {
      executor: "ramping-vus", startTime: `${PEAK_START}s`, startVUs: CLASS_VUS, gracefulRampDown: "30s",
      gracefulStop: "30s",
      stages: [{ duration: `${RAMP_S}s`, target: PEAK_VUS }, { duration: `${PEAK_HOLD_S}s`, target: PEAK_VUS }],
    },
  },
  thresholds,
  summaryTrendStats: ["med", "p(95)", "p(99)", "max", "count"],
  discardResponseBodies: false,
};

const unexpectedErrors = new Rate("unexpected_errors"); // a status the page would show as an error
const firstChart = new Trend("first_chart", true); // page request to overview chart data, without think time
const exportWait = new Trend("export_wait", true); // job queued to ready
const exportsQueued = new Counter("exports_queued");
const exportsRejected = new Counter("exports_rejected_429");
const exportsReady = new Counter("exports_ready");
const exportsFailed = new Counter("exports_failed");
const exportsGaveUp = new Counter("exports_gave_up");

const HOUR = 3600e3;
const DAY = 24 * HOUR;
const LADDER = [600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600]; // as api/routes/series.py
const pickBucket = (ms) => LADDER.find((b) => ms / 1000 / b <= 2000) || LADDER[LADDER.length - 1];
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const between = (lo, hi) => lo + Math.random() * (hi - lo);
const HISTORY_DAYS = num("HISTORY_DAYS", 4 * 365); // how far back seed.sql goes

// Toronto's offset, close enough for load: EST, -5 h (summer time would move every range by an hour).
const OFFSET = -5 * HOUR;
const torontoMidnight = (ms) => Math.floor((ms + OFFSET) / DAY) * DAY - OFFSET;
const snapDown = (ms, s) => Math.floor((ms + OFFSET) / (s * 1000)) * s * 1000 - OFFSET;
const snapUp = (ms, s) => Math.ceil((ms + OFFSET) / (s * 1000)) * s * 1000 - OFFSET;
const iso = (ms) => new Date(ms).toISOString();

function headers() {
  // One address per virtual user: the Next.js server trusts X-Forwarded-For from 127.0.0.1 in this test only
  // (TRUSTED_PROXY_IPS), so the backend's per-visitor export limit sees 30-50 visitors, not one.
  return { "X-Forwarded-For": `10.${Math.floor(__VU / 250) % 250}.${__VU % 250}.7` };
}

function get(url, endpoint, extra = {}) {
  const res = http.get(`${BASE}${url}`, { headers: headers(), tags: { endpoint, name: endpoint }, ...extra });
  record(res, endpoint);
  return res;
}

function record(res, endpoint, ok = [200]) {
  const good = ok.includes(res.status);
  unexpectedErrors.add(!good, { endpoint });
  check(res, { [`${endpoint} answered ${ok.join("/")}`]: () => good });
}

function seriesUrl(range, groups) {
  const p = [`start=${encodeURIComponent(iso(range.start))}`, `end=${encodeURIComponent(iso(range.end - 1))}`];
  for (const g of groups) p.push(`${g}=true`);
  return `/api/series?${p.join("&")}`;
}

function pickGroups() {
  if (Math.random() < 0.5) return ["weather", "quality", "gauges"];
  const groups = ["weather", "quality", "gauges"].filter(() => Math.random() < 0.5);
  return groups.length ? groups : [pick(["weather", "quality", "gauges"])];
}

export default function () {
  const t0 = Date.now();
  // 1. The page, then what it fetches on load (in parallel, like the browser).
  get("/", "page");
  const onLoad = http.batch([
    ["GET", `${BASE}/api/latest`, null, { headers: headers(), tags: { endpoint: "latest", name: "latest" } }],
    ["GET", `${BASE}/api/recent`, null, { headers: headers(), tags: { endpoint: "recent", name: "recent" } }],
  ]);
  record(onLoad[0], "latest");
  record(onLoad[1], "recent");
  const loadedAt = Date.now();

  // 2. Pick groups and days (the page starts with none), then the overview.
  const think = between(2, 5);
  sleep(think);
  const groups = pickGroups();
  const days = pick([2, 7, 31, 365]); // "1 day" is the default view: yesterday and today
  const shared = Math.random() < 0.5;
  const tomorrow = torontoMidnight(Date.now()) + DAY;
  const end = shared ? tomorrow : tomorrow - Math.floor(between(1, HISTORY_DAYS - days)) * DAY;
  const range = { start: end - days * DAY, end };
  const overviewEndpoint = shared ? "series_shared" : "series_unique";
  const overviewStarted = Date.now();
  const overview = get(seriesUrl(range, groups), overviewEndpoint);
  firstChart.add(loadedAt - t0 + (Date.now() - overviewStarted));
  const bucket = overview.status === 200 ? overview.json("bucket_seconds") : pickBucket(range.end - range.start);

  // 3. Zooms: each to about a third of the window, somewhere inside it.
  let w = { start: range.start, end: range.end };
  const zooms = 3 + Math.floor(Math.random() * 3);
  for (let i = 0; i < zooms; i++) {
    sleep(between(1, 3));
    const width = Math.max((w.end - w.start) / 3, HOUR);
    if (width >= range.end - range.start) break;
    const start = Math.min(Math.max(between(w.start, w.end - width), range.start), range.end - width);
    w = { start, end: start + width };
    const pad = width / 2;
    const r = { start: Math.max(range.start, snapDown(w.start - pad, bucket)), end: Math.min(range.end, snapUp(w.end + pad, bucket)) };
    if (pickBucket(r.end - r.start) >= bucket) continue; // the overview is already this fine: the page loads nothing
    get(seriesUrl(r, groups), "series_zoom");
  }

  // 4. The wind rose: raw weather readings for the picked days (the page caps it; a year would be refused).
  if (Math.random() < WINDROSE_SHARE && days <= 31) {
    sleep(between(1, 3));
    get(`/api/data?start=${encodeURIComponent(iso(range.start))}&end=${encodeURIComponent(iso(range.end - 1))}&weather=true`,
      "data_windrose", { responseType: "none" });
  }

  // 5. A small export: the last full week, for the picked groups.
  if (Math.random() < EXPORT_SHARE) {
    sleep(between(2, 5));
    exportCsv(groups, { start: tomorrow - 8 * DAY, end: tomorrow - DAY });
  }

  sleep(between(3, 8)); // reading the charts before leaving
}

function exportCsv(groups, range) {
  const groupTypes = groups.map((g) => ({ weather: "Weather", quality: "Quality", gauges: "Logger" })[g]);
  const body = JSON.stringify({ domain: "sensor", start: iso(range.start), end: iso(range.end - 1), group_types: groupTypes });
  const json = { headers: { ...headers(), "Content-Type": "application/json" } };

  const estimate = http.post(`${BASE}/api/exports/estimate`, body, { ...json, tags: { endpoint: "export_estimate", name: "export_estimate" } });
  record(estimate, "export_estimate");
  if (estimate.status !== 200) return;

  const created = http.post(`${BASE}/api/exports/jobs`, body, {
    ...json, tags: { endpoint: "export_create", name: "export_create" }, responseCallback: http.expectedStatuses(202, 429),
  });
  record(created, "export_create", [202, 429]);
  if (created.status === 429) {
    exportsRejected.add(1);
    return;
  }
  if (created.status !== 202) return;
  exportsQueued.add(1);

  const id = created.json("job_id");
  const queuedAt = Date.now();
  for (;;) {
    if (Date.now() - queuedAt > EXPORT_WAIT_S * 1000) {
      exportsGaveUp.add(1);
      return;
    }
    sleep(3); // the page polls every poll_interval_seconds (3)
    const status = get(`/api/exports/jobs/${id}`, "export_status");
    if (status.status !== 200) return;
    const state = status.json("status");
    if (state === "ready") break;
    if (state === "failed" || state === "expired") {
      exportsFailed.add(1);
      return;
    }
  }
  exportWait.add(Date.now() - queuedAt);
  exportsReady.add(1);
  get(`/api/exports/jobs/${id}/download`, "export_download", { responseType: "none" });
}

// ---- Summary ---------------------------------------------------------------------------------------------------

const ms = (v) => (v === undefined || v === null ? "–" : v >= 10000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);
const pct = (v) => (v === undefined ? "–" : `${(v * 100).toFixed(2)}%`);
const metric = (data, name) => data.metrics[name] && data.metrics[name].values;

export function handleSummary(data) {
  const lines = [];
  const warnings = [];
  lines.push("## Load test results", "");
  lines.push(`Synthetic data, never production. Each virtual user is a new visitor on its own IP address; ` +
    `requests go through the Next.js server as a browser's do. Times are per request, as k6 measured them.`, "");

  for (const [scenario, { label, seconds }] of Object.entries(SCENARIOS)) {
    const reqs = metric(data, `http_reqs{scenario:${scenario}}`);
    if (!reqs || !reqs.count) continue;
    const failed = metric(data, `http_req_failed{scenario:${scenario}}`);
    const unexpected = metric(data, `unexpected_errors{scenario:${scenario}}`);
    const first = metric(data, `first_chart{scenario:${scenario}}`);
    lines.push(`### ${scenario}: ${label}`, "");
    lines.push(`${reqs.count} requests, ${(reqs.count / seconds).toFixed(1)} requests/s on average; ` +
      `failed (k6: unexpected status or no answer) ${pct(failed && failed.rate)}, ` +
      `error answers (anything the page would show as an error) ${pct(unexpected && unexpected.rate)}. ` +
      `Page request to overview data (no think time): median ${ms(first && first.med)}, p95 ${ms(first && first["p(95)"])}.`, "");
    lines.push("| Endpoint | Requests | p50 | p95 | p99 | max | Failed |", "|---|---:|---:|---:|---:|---:|---:|");
    for (const [endpoint, title] of ENDPOINTS) {
      const d = metric(data, `http_req_duration{scenario:${scenario},endpoint:${endpoint}}`);
      if (!d || !d.count) continue;
      const f = metric(data, `http_req_failed{scenario:${scenario},endpoint:${endpoint}}`);
      lines.push(`| ${title} | ${d.count} | ${ms(d.med)} | ${ms(d["p(95)"])} | ${ms(d["p(99)"])} | ${ms(d.max)} | ${pct(f && f.rate)} |`);
      const limit = WARN[endpoint];
      if (scenario === "class30" && limit && d["p(95)"] > limit.p95) {
        warnings.push(`p95 of ${title} at ${CLASS_VUS} visitors is ${ms(d["p(95)"])}, over ${ms(limit.p95)}`);
      }
    }
    const count = (name) => {
      const v = metric(data, `${name}{scenario:${scenario}}`);
      return v ? v.count : 0;
    };
    const wait = metric(data, `export_wait{scenario:${scenario}}`);
    lines.push("", `Exports: ${count("exports_queued")} queued, ${count("exports_rejected_429")} refused with 429 ` +
      `(the queue's limits, expected under load), ${count("exports_ready")} ready ` +
      `(queued to ready: median ${ms(wait && wait.med)}, max ${ms(wait && wait.max)}), ` +
      `${count("exports_failed")} failed, ${count("exports_gave_up")} still not ready after ${EXPORT_WAIT_S} s.`, "");
    if (scenario === "class30" && unexpected && unexpected.rate > WARN.errorRate) {
      warnings.push(`error answers at ${CLASS_VUS} visitors: ${pct(unexpected.rate)}, over ${pct(WARN.errorRate)}`);
    }
  }

  lines.push("### Warnings", "");
  lines.push(`Targets at ${CLASS_VUS} visitors (class30): p95 /api/latest < 300 ms, /api/series < 2 s for shared ` +
    `(cached) ranges and < 5 s for cold ones, error answers < 1%. They don't fail the run.`, "");
  if (warnings.length) for (const w of warnings) lines.push(`- :warning: ${w}`);
  else lines.push("- None: every target was met.");
  lines.push("");

  const md = lines.join("\n");
  return {
    stdout: `${md}\n`,
    [`${OUT}/summary.md`]: md,
    [`${OUT}/summary.json`]: JSON.stringify(data, null, 1),
  };
}
