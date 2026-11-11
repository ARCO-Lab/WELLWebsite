// The charts under stress: however fast a chart is zoomed and panned, the page sends few requests, never more than
// two at a time, and the charts stay independent of each other. /api/series is slowed down here (each answer held
// for SLOW_MS, like a busy production server), so requests that pile up would show.
//
// Runs with the rest of the e2e suite (playwright.config.ts), in one browser zone only: what it checks doesn't depend
// on the zone. A longer soak (random zooming and panning, with the JS heap checked) runs when STRESS_MINUTES is set:
//   STRESS_MINUTES=5 npx playwright test charts-stress --project=toronto

import { expect, test, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const EXPECTED = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "expected.json"), "utf-8"));
const NOW = new Date(EXPECTED.browser_now_utc);
const SLOW_MS = 500;

interface Net { requests: string[]; inFlight: number; peak: number }

async function slowSeries(page: Page): Promise<Net> {
  const net: Net = { requests: [], inFlight: 0, peak: 0 };
  await page.route("**/api/series?**", async (route) => {
    net.requests.push(route.request().url());
    net.inFlight++;
    net.peak = Math.max(net.peak, net.inFlight);
    try {
      const response = await route.fetch();
      await new Promise((r) => setTimeout(r, SLOW_MS));
      await route.fulfill({ response });
    } catch {
      // the page closed first
    } finally {
      net.inFlight--;
    }
  });
  return net;
}

/** Wait until no request has been sent or answered for `quietMs`. */
async function settled(page: Page, net: Net, quietMs = 900) {
  let seen = -1, since = Date.now();
  for (let waited = 0; waited < 30_000; waited += 100) {
    await page.waitForTimeout(100);
    if (net.requests.length !== seen || net.inFlight > 0) {
      seen = net.requests.length;
      since = Date.now();
    } else if (Date.now() - since >= quietMs) return;
  }
  throw new Error("requests never settled");
}

const chart = (page: Page, id: string) => page.getByTestId(`chart-${id}`);
const label = (c: Locator) => c.getByTestId("chart-window-label").textContent();

async function open(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/maplibre|Worker/i.test(m.text())) errors.push(m.text()); });
  const net = await slowSeries(page);
  await page.clock.setFixedTime(NOW);
  await page.goto("/");
  for (const group of ["Water Loggers", "Weather Station"]) {
    await page.getByRole("checkbox", { name: group, exact: true }).click();
  }
  await expect(chart(page, "logger-2577531").getByTestId("chart-resolution")).toBeVisible();
  await settled(page, net);
  return { net, errors };
}

/** A burst of Ctrl+wheel events over a chart's plot, sent from inside the page every 16 ms as a real wheel or trackpad
 *  sends them (Playwright's own events each wait for a round trip, which on a busy machine can leave longer gaps than
 *  a person's scrolling ever does). */
async function ctrlWheelBurst(c: Locator, share: number, deltaY: number, count: number) {
  const p = await at(c, share);
  await c.getByRole("group", { name: /chart\. Arrow keys/ }).evaluate(async (el, { x, y, dy, n }) => {
    for (let i = 0; i < n; i++) {
      el.dispatchEvent(new WheelEvent("wheel", { deltaY: dy, clientX: x, clientY: y, ctrlKey: true, bubbles: true, cancelable: true }));
      await new Promise((r) => setTimeout(r, 16));
    }
  }, { x: p.x, y: p.y, dy: deltaY, n: count });
}

/** A point in a chart's plot area, as a share of its width and height. */
async function at(c: Locator, x: number, y = 0.4) {
  const plot = c.getByRole("group", { name: /chart\. Arrow keys/ });
  await plot.scrollIntoViewIfNeeded();
  const box = (await plot.boundingBox())!;
  return { x: box.x + box.width * x, y: box.y + box.height * y };
}

test.describe("charts under stress", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "toronto", "the same in every zone");
  });

  test("bursts of input send at most two requests, revisits none, and each chart keeps its own window", async ({ page }) => {
    const { net, errors } = await open(page);
    const logger = chart(page, "logger-2577531");
    const weather = chart(page, "weather-temperature");
    const weatherWindow = await label(weather);

    await test.step("a plain wheel scrolls the page and only shows the zoom hint", async () => {
      const before = await label(logger);
      const p = await at(logger, 0.5);
      const scrollY = await page.evaluate(() => window.scrollY);
      await page.mouse.move(p.x, p.y);
      await page.mouse.wheel(0, 120);
      await expect(logger.getByTestId("chart-wheel-hint")).toHaveClass(/opacity-100/);
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(scrollY);
      expect(await label(logger)).toBe(before);
    });

    await test.step("80 Ctrl+wheel events zooming out: at most 2 requests", async () => {
      const n0 = net.requests.length;
      await ctrlWheelBurst(logger, 0.7, 60, 80);
      await settled(page, net);
      expect(net.requests.length - n0).toBeLessThanOrEqual(2);
      await expect(logger.getByTestId("chart-resolution")).toHaveText(/daily|12-h/);
    });

    await test.step("80 Ctrl+wheel events zooming in somewhere new: at most 2 requests", async () => {
      const n0 = net.requests.length;
      await ctrlWheelBurst(logger, 0.3, -60, 80);
      await settled(page, net);
      expect(net.requests.length - n0).toBeLessThanOrEqual(2);
    });

    await test.step("a slider drag of 120 moves: at most 2 requests", async () => {
      const n0 = net.requests.length;
      const handle = logger.getByTestId("chart-slider-window");
      await handle.scrollIntoViewIfNeeded();
      const box = (await handle.boundingBox())!;
      const x0 = box.x + box.width / 2, y = box.y + box.height / 2;
      await page.mouse.move(x0, y);
      await page.mouse.down();
      for (let i = 0; i < 120; i++) {
        await page.mouse.move(x0 + Math.sin(i / 12) * 120 + i, y);
        await page.waitForTimeout(16);
      }
      await page.mouse.up();
      await settled(page, net);
      expect(net.requests.length - n0).toBeLessThanOrEqual(2);
    });

    await test.step("panning back and forth over what was loaded, and Reset: no requests", async () => {
      await settled(page, net);
      const n0 = net.requests.length;
      const plot = logger.getByRole("group", { name: /chart\. Arrow keys/ });
      await plot.focus();
      for (let i = 0; i < 3; i++) { await page.keyboard.press("ArrowRight"); await page.waitForTimeout(300); }
      for (let i = 0; i < 3; i++) { await page.keyboard.press("ArrowLeft"); await page.waitForTimeout(300); }
      await settled(page, net);
      expect(net.requests.length - n0).toBe(0);
      await logger.getByRole("button", { name: /^Reset/ }).click();
      await settled(page, net);
      expect(net.requests.length - n0).toBe(0);
      await expect(logger.getByTestId("chart-window-label")).toHaveText("Oct 31 00:00 – Nov 1 04:00");
    });

    await test.step("the other charts never moved, and nothing went wrong", async () => {
      expect(await label(weather)).toBe(weatherWindow);
      expect(net.peak).toBeLessThanOrEqual(2);
      expect(errors).toEqual([]);
    });
  });

  test("a long soak of random zooming and panning keeps memory bounded", async ({ page }) => {
    const minutes = Number(process.env.STRESS_MINUTES || 0);
    test.skip(!minutes, "set STRESS_MINUTES to run it");
    test.setTimeout((minutes + 2) * 60_000);
    const { net, errors } = await open(page);
    const cdp = await page.context().newCDPSession(page);
    const heap = async () => {
      await cdp.send("HeapProfiler.collectGarbage");
      return ((await cdp.send("Runtime.getHeapUsage")) as { usedSize: number }).usedSize / 1e6;
    };
    const ids = ["logger-2577531", "weather-temperature", "weather-humidity"];
    const end = Date.now() + minutes * 60_000;
    let first = 0, peakHeap = 0, actions = 0;
    while (Date.now() < end) {
      const c = chart(page, ids[actions % ids.length]);
      const p = await at(c, 0.2 + Math.random() * 0.6);
      await page.mouse.move(p.x, p.y);
      const kind = Math.random();
      if (kind < 0.5) {
        await page.keyboard.down("Control");
        for (let i = 0; i < 20; i++) await page.mouse.wheel(0, (Math.random() < 0.5 ? -1 : 1) * 80);
        await page.keyboard.up("Control");
      } else {
        await page.mouse.down();
        await page.mouse.move(p.x + (Math.random() - 0.5) * 300, p.y, { steps: 15 });
        await page.mouse.up();
      }
      actions++;
      if (actions % 25 === 0) {
        const mb = await heap();
        if (!first) first = mb;
        peakHeap = Math.max(peakHeap, mb);
        console.log(`[soak] ${actions} actions, ${net.requests.length} requests, heap ${mb.toFixed(1)} MB`);
      }
    }
    await settled(page, net);
    const last = await heap();
    console.log(`[soak] done: ${actions} actions, ${net.requests.length} requests, peak in flight ${net.peak}, heap ${first.toFixed(1)} -> ${last.toFixed(1)} MB (peak ${peakHeap.toFixed(1)})`);
    expect(net.peak).toBeLessThanOrEqual(2);
    expect(last).toBeLessThan(Math.max(first * 2, first + 60)); // the tile cache is bounded, so the heap levels off
    expect(errors).toEqual([]);
  });
});
