// The Ancaster Watershed (sampling) tab, the Download button and an accessibility scan, in the browser.
//
// These checks need no data in the database: every API call the page makes is answered here (page.route), so they
// can also run against `next dev` alone (E2E_BASE_URL). They cover what the vendor-data spec doesn't: the sampling
// tab's charts and legend, replies that arrive out of order, a shared link's ticks, the Download button's range line
// and what happens to a queued export when its tab is left, and axe's WCAG checks on both tabs.

import { test, expect, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type Sample = { site_id: string; creek_id: string; measurement_type: string; value: number; unit: string; recorded_at: string };

const CREEK_IDS: Record<string, string> = { ancaster: "19431905", coldwater: "336415129" };
const CREEK_SITES: Record<string, string[]> = { ancaster: ["2", "5"], coldwater: ["8", "9"] };
const METRICS: [string, string][] = [
  ["E. coli", "CFU/100 mL"], ["Total coliform", "CFU/100 mL"], ["Chloride", "mg/L"], ["Conductivity", "µS/cm"],
  ["Total nitrogen", "mg/L"], ["Nitrate nitrogen", "mg/L"], ["pH", "pH units"],
];

// Three monthly campaigns in summer 2025 for each site of the creek.
function samplesFor(creek: string): Sample[] {
  const rows: Sample[] = [];
  for (const site of CREEK_SITES[creek]) {
    for (const [i, month] of ["06", "07", "08"].entries()) {
      METRICS.forEach(([m, unit], j) => rows.push({
        site_id: site, creek_id: CREEK_IDS[creek], measurement_type: m, unit,
        value: 10 + i + j, recorded_at: `2025-${month}-0${j % 3 + 1}T00:00:00`,
      }));
    }
  }
  return rows;
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

// Answers every API call: no latest readings, no recent samples, and the ticked creeks' samples (after `delayMs`
// for the request whose creeks are `slow`). Returns the /api/samples URLs asked for.
async function mockApis(page: Page, opts: { slow?: string; delayMs?: number; empty?: boolean } = {}) {
  const asked: URL[] = [];
  await page.route("**/api/latest", (r) => json(r, []));
  await page.route("**/api/recent", (r) => json(r, []));
  await page.route("**/api/series**", (r) => json(r, { bucket_seconds: 600, aggregated: false, series: [] }));
  await page.route("**/api/samples?**", async (route) => {
    const url = new URL(route.request().url());
    asked.push(url);
    const creeks = Object.keys(CREEK_IDS).filter((c) => url.searchParams.get(c) === "true");
    if (opts.slow && creeks.join(",") === opts.slow) await new Promise((r) => setTimeout(r, opts.delayMs ?? 0));
    await json(route, opts.empty ? [] : creeks.flatMap(samplesFor)).catch(() => {}); // aborted by the page: fine
  });
  return asked;
}

async function openSampling(page: Page, path = "/") {
  await page.goto(path);
  await page.getByRole("tab", { name: "Ancaster Watershed" }).click();
}

// Errors thrown in the page (a hydration mismatch, say) fail the test that saw them.
const pageErrors = new WeakMap<Page, string[]>();
test.beforeEach(({ page }) => {
  const errors: string[] = [];
  pageErrors.set(page, errors);
  page.on("pageerror", (e) => errors.push(String(e)));
});
test.afterEach(({ page }) => {
  expect(pageErrors.get(page) ?? []).toEqual([]);
});

const graphsCard = (page: Page) => page.getByRole("heading", { level: 2, name: "Graphs" }).locator("xpath=..");

// Series drawn in the sampling charts on the page (not in the modal), with their colour and visibility.
const sampleSeries = (page: Page) => page.evaluate(() => {
  type Chart = { renderTo: HTMLElement; title?: { textStr?: string }; series: { name: string; color: string; visible: boolean }[] };
  // Highcharts' UMD build puts itself on window._Highcharts
  const H = (window as unknown as { _Highcharts?: { charts: (Chart | undefined)[] } })._Highcharts;
  return (H?.charts ?? []).filter((c) => !!c && c.renderTo.isConnected).map((c) => ({
    title: c!.title?.textStr ?? "",
    series: c!.series.map((s) => ({ name: s.name, color: String(s.color), visible: s.visible })),
  }));
});

test("sampling charts: one colour per measurement, one legend per creek that shows and hides", async ({ page }) => {
  await mockApis(page);
  await openSampling(page);
  // The picked days start at the first samples (May 1, 2025)
  await expect(page.getByRole("button", { name: /May 1, 2025/ }).first()).toBeVisible();
  await page.getByRole("checkbox", { name: "Ancaster Creek", exact: true }).click();

  const card = graphsCard(page);
  const legend = card.getByRole("button", { name: /^E\. coli/ });
  await expect(legend).toHaveAttribute("aria-pressed", "true");
  await expect(card.getByText("Loading data…")).toHaveCount(0);
  await expect.poll(async () => (await sampleSeries(page)).length).toBe(2); // Maple Lane Pk and Sherman Falls

  for (const chart of await sampleSeries(page)) {
    expect(chart.series.length).toBe(METRICS.length);
    expect(new Set(chart.series.map((s) => s.color)).size, `${chart.title}: a colour each`).toBe(chart.series.length);
    expect(chart.series.map((s) => s.name)).toContain("Conductivity (µS/cm)");
    expect(chart.series.map((s) => s.name)).toContain("pH"); // pH has no unit
  }
  // The same measurement has the same colour in every chart
  const [a, b] = await sampleSeries(page);
  expect(a.series.find((s) => s.name.startsWith("E. coli"))?.color).toBe(b.series.find((s) => s.name.startsWith("E. coli"))?.color);

  // No legend inside a chart takes room from its plot
  expect(await page.locator(".highcharts-legend").count()).toBe(0);

  await legend.click();
  await expect(legend).toHaveAttribute("aria-pressed", "false");
  await expect.poll(async () => (await sampleSeries(page)).every((c) => c.series.find((s) => s.name.startsWith("E. coli"))?.visible === false)).toBe(true);
});

test("a slow reply to an older selection doesn't leave the charts loading", async ({ page }) => {
  // The first request (Ancaster alone) answers 3 s late, after the second (Ancaster and Coldwater)
  const asked = await mockApis(page, { slow: "ancaster", delayMs: 3000 });
  await openSampling(page);
  await page.getByRole("checkbox", { name: "Ancaster Creek", exact: true }).click();
  await page.getByRole("checkbox", { name: "Coldwater Creek", exact: true }).click();

  const card = graphsCard(page);
  await expect(card.getByText("Loading data…")).toHaveCount(0);
  await expect(card.getByRole("heading", { name: "Coldwater Creek" })).toBeVisible();
  await page.waitForTimeout(3500); // the late reply has arrived (or been aborted) by now
  await expect(card.getByText("Loading data…")).toHaveCount(0);
  await expect(card.locator("[aria-busy=true]")).toHaveCount(0);
  expect(await sampleSeries(page)).toHaveLength(4);
  expect(asked.length).toBeGreaterThanOrEqual(2);
});

test("an empty range says so, and a shared link ticks what it names", async ({ page }) => {
  await mockApis(page, { empty: true });
  await openSampling(page, "/?tab=sampling&creeks=coldwater");
  await expect(page.getByRole("tab", { name: "Ancaster Watershed" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("checkbox", { name: "Coldwater Creek", exact: true })).toBeChecked();
  await expect(graphsCard(page).getByText(/^No samples from May 1, 2025 to /)).toBeVisible();

  // Ticking another creek is written back into the link
  await page.getByRole("checkbox", { name: "Ancaster Creek", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("creeks")).toBe("ancaster,coldwater");
});

test("Download names the days it exports, and stops polling when its tab is left", async ({ page }) => {
  await mockApis(page);
  let jobChecks = 0;
  let ready = false;
  await page.route("**/api/exports/estimate", (r) => json(r, { recommended_mode: "async" }));
  await page.route("**/api/exports/jobs", (r) => json(r, { job_id: "job-1", poll_interval_seconds: 1 }, 202));
  await page.route("**/api/exports/jobs/job-1", (r) => {
    jobChecks++;
    return json(r, ready ? { status: "ready" } : { status: "running", progress_pct: 12.5 });
  });
  await page.route("**/api/exports/jobs/job-1/download", (r) =>
    r.fulfill({ status: 200, contentType: "text/csv", headers: { "content-disposition": 'attachment; filename="samples.csv"' }, body: "a,b\n1,2\n" }));

  await openSampling(page);
  await page.getByRole("checkbox", { name: "Ancaster Creek", exact: true }).click();
  const button = page.getByRole("button", { name: /Download Data|Preparing export/ }).last();
  await expect(page.getByText(/^Exports May 1, 2025 – \w{3} \d{1,2}, \d{4} \(Eastern Time\)/).last()).toBeVisible();

  await button.click();
  await expect(page.getByRole("button", { name: /Preparing export \(running 12\.5%\)/ })).toBeVisible();

  // Leaving the tab unmounts the button: no status checks after that
  await page.getByRole("tab", { name: "West Campus" }).click();
  const atLeave = jobChecks;
  await page.waitForTimeout(2500);
  expect(jobChecks).toBe(atLeave);

  // Back on the tab, the export can be picked up, and finishes as one file
  await page.getByRole("tab", { name: "Ancaster Watershed" }).click();
  await expect(page.getByText(/An export was still being prepared when you left this tab/)).toBeVisible();
  ready = true;
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Data" }).last().click();
  expect((await downloading).suggestedFilename()).toBe("samples.csv");
});

test("axe finds no serious WCAG problems on either tab", async ({ page }) => {
  await mockApis(page);
  await page.goto("/");
  await page.getByRole("checkbox", { name: "Weather Station", exact: true }).waitFor();
  const scan = async (label: string) => {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      // Third-party drawing surfaces: the map's canvas and controls are MapLibre's
      .exclude(".maplibregl-map")
      .analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${label}: ${v.id} (${v.nodes.length}) ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`)).toEqual([]);
  };
  await scan("West Campus");
  await page.getByRole("tab", { name: "Ancaster Watershed" }).click();
  await page.getByRole("checkbox", { name: "Ancaster Creek", exact: true }).click();
  await expect(graphsCard(page).getByText("Loading data…")).toHaveCount(0);
  await expect.poll(async () => (await sampleSeries(page)).length).toBe(2);
  await scan("Ancaster Watershed");
});
