// What the vendors sent (fixtures/licor.json, fixtures/wqdata.json) must be exactly what the dashboard shows:
// in the database, in the charts' data and tooltip, in the Latest Data tiles and in the downloaded CSV.
// fixtures/expected.json lists every row and tile, with notes on the cases they cover (the clocks going back,
// duplicates, re-reads, N/A values, readings near midnight). See playwright.config.ts for how it runs.

import fs from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { Client } from "pg";

type Row = { group_type: string; station_id: string; measurement_type: string; unit: string; recorded_at: string; value: number };
type Tile = { label: string; caption?: string; value: string; unit: string; last_reading?: string };
type Section = { as_of: string; tiles: Tile[]; no_data?: string[]; no_data_captions?: string[] };

const EXPECTED = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "expected.json"), "utf-8"));
const ROWS: Row[] = EXPECTED.rows;
const NOW = new Date(EXPECTED.browser_now_utc);
const LOGGER_NAMES: Record<string, string> = { "2577531": "Logger 1" };

// The picked days (Oct 31 and Nov 1, the default) as the charts must ask for them: from Toronto midnight, to no
// later than the last millisecond before the next Toronto midnight (Nov 1 is 25 hours long). The charts may stop
// earlier, at "now", but never before it.
const RANGE_START = "2026-10-31T04:00:00.000Z";
const RANGE_END_LATEST = "2026-11-02T04:59:59.999Z";

const key = (r: Pick<Row, "group_type" | "station_id" | "measurement_type" | "unit" | "recorded_at">) =>
  `${r.group_type} | ${r.station_id} | ${r.measurement_type} | ${r.unit} | ${r.recorded_at}`;

/** Compares two {key: value} maps: the same keys, and values equal to within `tolerance`. */
function expectSameValues(actual: Map<string, number>, expected: Map<string, number>, tolerance: number) {
  expect([...actual.keys()].sort()).toEqual([...expected.keys()].sort());
  for (const [k, v] of expected) {
    expect(Math.abs((actual.get(k) as number) - v), `${k}: ${actual.get(k)} vs ${v}`).toBeLessThanOrEqual(tolerance);
  }
}

/** An instant as Toronto wall-clock time, "YYYY-MM-DDTHH:MM:SS", as recorded_at stores it. */
function torontoWallClock(ms: number): string {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}`;
}

/** Minimal CSV parser (quoted fields, doubled quotes). */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows;
}

const expectedValues = () => new Map(ROWS.map((r) => [key(r), r.value]));

// --- the database: checked once, not per browser ---

test("the database holds exactly the expected readings", async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "toronto", "the database is the same for every browser");
  const client = new Client({ connectionString: process.env.E2E_DATABASE_URL });
  await client.connect();
  try {
    const { rows } = await client.query(`
      SELECT group_type, station_id::text AS station_id, measurement_type, unit,
             to_char(recorded_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS recorded_at, value
      FROM sensor_measurements`);
    expect(rows.length).toBe(ROWS.length);
    expectSameValues(new Map(rows.map((r) => [key(r), Number(r.value)])), expectedValues(), 1e-9);
  } finally {
    await client.end();
  }
});

// --- the dashboard, in each browser time zone ---

async function openDashboard(page: Page) {
  await page.clock.setFixedTime(NOW); // Date is frozen; timers still run
  // The charts' request once all three groups are ticked (each tick before it asks for fewer groups).
  const series = page.waitForResponse((r) => {
    const url = new URL(r.url());
    return url.pathname === "/api/series" && ["weather", "quality", "gauges"].every((g) => url.searchParams.get(g) === "true");
  });
  await page.goto("/");
  for (const group of ["Weather Station", "Water Quality", "Water Loggers"]) {
    await page.getByRole("checkbox", { name: group, exact: true }).click();
  }
  return series;
}

// The Latest Data group with this title: the innermost block holding its heading.
const metricGroup = (page: Page, title: string) =>
  page.locator("div.space-y-2", { has: page.getByRole("heading", { level: 3, name: title, exact: true }) }).last();

function tile(group: Locator, label: string, caption?: string): Locator {
  let t = group.locator("div.rounded-lg").filter({ has: group.page().getByText(label, { exact: true }) });
  if (caption) t = t.filter({ has: group.page().getByText(caption, { exact: true }) });
  return t.first(); // a scrolling strip repeats its tiles in a hidden second copy
}

/** "2026-11-01T02:40:00" -> "2:40 a.m." (today) or "Oct 31, 12:00 p.m.", as the tiles write site times. */
function siteTime(wall: string): RegExp {
  const [date, time] = wall.split("T");
  const [h, m] = time.split(":").map(Number);
  const clock = `${h % 12 || 12}:${String(m).padStart(2, "0")}\\s${h < 12 ? "a" : "p"}\\.m\\.`;
  const today = torontoWallClock(NOW.getTime()).slice(0, 10);
  if (date === today) return new RegExp(clock);
  const [, month, day] = date.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return new RegExp(`${months[month - 1]} ${day},\\s${clock}`);
}

test("charts, tooltip, Latest Data and download match the vendor data", async ({ page }) => {
  const seriesResponse = await openDashboard(page);

  await test.step("the charts ask for Toronto's days and get every reading", async () => {
    const response = await seriesResponse;
    const url = new URL(response.url());
    expect(url.searchParams.get("start")).toBe(RANGE_START);
    const end = Date.parse(url.searchParams.get("end") ?? "");
    expect(end).toBeLessThanOrEqual(Date.parse(RANGE_END_LATEST));
    expect(end).toBeGreaterThanOrEqual(NOW.getTime());
    const body = await response.json();
    expect(body.aggregated).toBe(false); // 10-minute buckets: one point per reading
    const points = new Map<string, number>();
    for (const s of body.series) {
      s.t.forEach((t: number, i: number) => {
        if (s.avg[i] === null) return;
        points.set(key({ ...s, station_id: String(s.station_id), recorded_at: torontoWallClock(t) }), s.avg[i]);
      });
    }
    expectSameValues(points, expectedValues(), 1e-4); // the API rounds to 4 decimals
  });

  await test.step("the air temperature tooltip shows Toronto time", async () => {
    await expect(page.getByText("Loading data…")).toHaveCount(0);
    // Noon in Toronto on Oct 31 (16:00Z, 9.5 °C): its neighbours are hours away, so the tooltip can't snap to
    // another point. A chart in the browser's zone would say 01:00 Nov 1 in Tokyo, 16:00 in London.
    // Highcharts places the point, so this doesn't depend on chart titles, layout or the x-axis range.
    const at = Date.parse("2026-10-31T16:00:00Z");
    const where = async () => page.evaluate((x) => {
      type HPoint = { x: number; plotX?: number; plotY?: number };
      type HChart = { container: HTMLElement; plotLeft: number; plotTop: number;
        series: { name: string; type: string; points: HPoint[] }[] };
      const H = (window as unknown as { _Highcharts?: { charts: (HChart | undefined)[] } })._Highcharts;
      if (!H) throw new Error("Highcharts isn't on window._Highcharts (its UMD build puts it there)");
      for (const chart of H.charts) {
        // The line, not a min-max band drawn with it
        const line = chart?.series.find((s) => s.name === "Air Temperature (°C)" && s.type === "line");
        const point = line?.points.find((p) => p.x === x);
        if (!chart || point?.plotX === undefined || point.plotY === undefined) continue;
        chart.container.scrollIntoView({ block: "center" });
        const box = chart.container.getBoundingClientRect();
        return { x: box.left + chart.plotLeft + point.plotX, y: box.top + chart.plotTop + point.plotY };
      }
      return null;
    }, at);
    await expect.poll(where, { message: "the 16:00Z air temperature point is drawn" }).not.toBeNull();
    const point = (await where())!;
    await page.mouse.move(point.x - 40, point.y);
    await page.mouse.move(point.x, point.y, { steps: 5 });
    const tooltip = page.locator(".highcharts-tooltip", { hasText: "Air Temperature" });
    await expect(tooltip).toContainText("9.50");
    await expect(tooltip).toContainText(/Oct 31\b/);
    await expect(tooltip).toContainText(/\b12:00\b/);
  });

  await test.step("Latest Data shows the newest readings, in Toronto time", async () => {
    const sections: Record<string, Section> = EXPECTED.latest_data;
    for (const [title, section] of Object.entries(sections)) {
      const group = metricGroup(page, title);
      await expect(group.locator("p", { hasText: /^as of / })).toHaveText(new RegExp(`^as of ${siteTime(section.as_of).source}$`));
      for (const t of section.tiles) {
        const shown = tile(group, t.label, t.caption);
        await expect(shown).toContainText(t.value);
        await expect(shown).toContainText(t.unit);
        if (t.last_reading) await expect(shown).toContainText(new RegExp(`Last reading ${siteTime(t.last_reading).source}`));
        else await expect(shown).not.toContainText("Last reading");
      }
      for (const label of section.no_data ?? []) await expect(tile(group, label)).toContainText("No data");
      for (const caption of section.no_data_captions ?? []) {
        const tiles = group.locator("div.rounded-lg").filter({ has: page.getByText(caption, { exact: true }) });
        await expect(tiles.first()).toContainText("No data");
        await expect(tiles.filter({ hasNotText: "No data" })).toHaveCount(0);
      }
    }
  });

  await test.step("the download is named for Toronto's days and holds every reading", async () => {
    const downloading = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download Data" }).click();
    const download = await downloading;
    expect(download.suggestedFilename()).toBe(EXPECTED.download_filename);
    const [header, ...lines] = parseCsv(fs.readFileSync((await download.path())!, "utf-8"));
    // Columns run Group, metrics..., (blank), Group, ..., and for loggers Sensor, metrics... per logger.
    const cells = new Map<string, number>();
    for (const line of lines) {
      if (line.length === 1 && line[0] === "") continue;
      let group = "", station = "";
      header.forEach((name, i) => {
        if (name === "Group") { group = line[i]; station = ""; return; }
        if (name === "Sensor") { station = line[i]; return; }
        if (!name || name === "ID" || name === "Timestamp" || line[i] === "") return;
        cells.set(`${group} | ${station} | ${name} | ${line[1]}`, Number(line[i]));
      });
    }
    const expected = new Map(ROWS.map((r) => [
      `${r.group_type} | ${r.group_type === "Logger" ? LOGGER_NAMES[r.station_id] : ""} | ${r.measurement_type}: ${r.unit.replace(" asl", "")} | ${r.recorded_at}`,
      r.value,
    ]));
    expectSameValues(cells, expected, 1e-9);
  });
});
