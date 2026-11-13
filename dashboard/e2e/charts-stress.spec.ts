// The charts under stress: however fast a chart is zoomed and panned, the page sends few requests, never more than
// two at a time, and the charts stay independent of each other. /api/series is slowed down here (each answer held
// for SLOW_MS, like a busy production server), so requests that pile up would show.
//
// Runs with the rest of the e2e suite (playwright.config.ts), in one browser zone only: what it checks doesn't depend
// on the zone. Performance budgets (at the end) check a slow phone too, with Chrome's CPU throttling. A longer soak
// (random zooming and panning, with the JS heap checked) runs when STRESS_MINUTES is set:
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
  for (const group of ["Water Loggers", "Weather Station", "Water Quality"]) {
    await page.getByRole("checkbox", { name: group, exact: true }).click();
  }
  await expect(chart(page, "logger").getByTestId("chart-resolution")).toBeVisible();
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

/** The navigator's window under a chart (Highcharts Stock): dragging it moves the chart's window. */
const navigatorWindow = (c: Locator) => c.locator(".highcharts-navigator-mask-inside");

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

  test("a chart is drawn a few times while it loads, not once per series", async ({ page }) => {
    // Count Chart.redraw per chart from the moment Highcharts loads (its bundle puts itself on window._Highcharts)
    await page.addInitScript(() => {
      type HC = { Chart: { prototype: { redraw: (...a: unknown[]) => unknown; container?: HTMLElement } } };
      const counts: Record<string, number> = {};
      (window as unknown as { __redraws: Record<string, number> }).__redraws = counts;
      let H: HC | undefined;
      Object.defineProperty(window, "_Highcharts", {
        configurable: true,
        get: () => H,
        set(v: HC) {
          H = v;
          const original = v.Chart.prototype.redraw;
          v.Chart.prototype.redraw = function (this: { container?: HTMLElement }, ...a: unknown[]) {
            const id = this.container?.closest<HTMLElement>('[data-testid^="chart-"]')?.dataset.testid ?? "other";
            counts[id] = (counts[id] ?? 0) + 1;
            return original.apply(this, a);
          };
        },
      });
    });
    const { net } = await open(page);
    await settled(page, net);
    const counts = await page.evaluate(() => (window as unknown as { __redraws: Record<string, number> }).__redraws);
    console.log(`[perf] redraws while loading: ${JSON.stringify(counts)}`);
    // The weather chart has 11 series: with per-point accessibility descriptions it was redrawn once per series
    expect(counts["chart-weather"] ?? 0).toBeGreaterThan(0);
    expect(counts["chart-weather"]).toBeLessThanOrEqual(5);
  });

  test("toggling sub-filters keeps exactly one navigator series per chart", async ({ page }) => {
    await open(page);
    for (let i = 0; i < 4; i++) {
      await page.getByRole("checkbox", { name: "Dew Point", exact: true }).click();
      await page.waitForTimeout(400);
    }
    await expect(chart(page, "weather").getByTestId("chart-resolution")).toBeVisible();
    const navigators = await page.evaluate(() => {
      type HChart = { container: HTMLElement; navigator?: { series?: unknown[] } };
      const H = (window as unknown as { _Highcharts?: { charts: (HChart | undefined)[] } })._Highcharts;
      return (H?.charts ?? []).filter((c): c is HChart => !!c && !!c.container.closest('[data-testid^="chart-"]'))
        .map((c) => c.navigator?.series?.length ?? 0);
    });
    expect(navigators.length).toBe(3); // one chart per card
    expect(navigators).toEqual([1, 1, 1]);
  });

  test("clicking a legend item hides its series and leaves the window where it was", async ({ page }) => {
    await open(page);
    const weather = chart(page, "weather");
    const before = await label(weather);
    const item = weather.locator(".highcharts-legend-item", { hasText: "Dew Point" });
    await item.scrollIntoViewIfNeeded();
    await item.click();
    await page.waitForTimeout(600);
    await expect(item).toHaveClass(/highcharts-legend-item-hidden/);
    expect(await label(weather)).toBe(before);
  });

  test("switching tabs and back is quick and asks for nothing again", async ({ page }) => {
    const { net } = await open(page);
    const tab = (name: string) => page.getByRole("tab", { name, exact: true });
    await tab("Ancaster Watershed").click();
    await expect(tab("Ancaster Watershed")).toHaveAttribute("aria-selected", "true");
    await page.waitForTimeout(500);
    const n0 = net.requests.length;
    // From the click to the next painted frame, with the charts already drawn (kept mounted, not rebuilt)
    const ms = await page.evaluate(async () => {
      const t = [...document.querySelectorAll('[role="tab"]')].find((el) => el.textContent?.trim() === "West Campus") as HTMLElement;
      const t0 = performance.now();
      t.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, button: 0 }));
      t.click();
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return performance.now() - t0;
    });
    await expect(chart(page, "logger").getByTestId("chart-resolution")).toBeVisible();
    console.log(`[perf] tab back to West Campus: ${ms.toFixed(0)} ms to the next frame`);
    expect(ms).toBeLessThan(500);
    await settled(page, net);
    expect(net.requests.length - n0).toBe(0);
  });

  test("bursts of input send at most two requests, revisits none, and each chart keeps its own window", async ({ page }) => {
    const { net, errors } = await open(page);
    const logger = chart(page, "logger");
    const weather = chart(page, "weather");
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

    await test.step("80 Ctrl+wheel events zooming out to the whole picked range: at most 2 requests", async () => {
      const n0 = net.requests.length;
      await ctrlWheelBurst(logger, 0.7, 60, 80);
      await settled(page, net);
      expect(net.requests.length - n0).toBeLessThanOrEqual(2);
      // As far out as the picked range (the navigator's extent), which is two days: still 10-minute readings
      await expect(logger.getByTestId("chart-window-label")).toHaveText("Oct 31 00:00 – Nov 1 04:00");
      await expect(logger.getByTestId("chart-resolution")).toHaveText("10-min readings");
    });

    await test.step("80 Ctrl+wheel events zooming in somewhere new: at most 2 requests", async () => {
      const n0 = net.requests.length;
      await ctrlWheelBurst(logger, 0.3, -60, 80);
      await settled(page, net);
      expect(net.requests.length - n0).toBeLessThanOrEqual(2);
    });

    await test.step("a slider drag of 120 moves: at most 2 requests", async () => {
      const n0 = net.requests.length;
      const handle = navigatorWindow(logger);
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
      await expect(logger.getByTestId("chart-window-label")).toHaveText("Nov 1 01:00 – Nov 1 02:50"); // fitted to its readings
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
    const ids = ["logger", "weather", "quality"];
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

// ---- Performance budgets: smooth enough on a slow phone, not only on a fast desktop ----
// CPU throttling (Chrome DevTools' "4x slowdown") stands in for a low-end phone. The measures:
// - long tasks: main-thread work over 50 ms (PerformanceObserver "longtask"), which delays input and frames;
// - frame times: gaps between animation frames while a gesture runs.

async function cpu(page: Page, rate: number) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate });
  return cdp;
}

/** Start recording long tasks and frame gaps in the page; the returned function stops and reports them. */
async function record(page: Page) {
  await page.evaluate(() => {
    const w = window as unknown as { __perf: { long: number[]; frames: number[]; on: boolean } };
    w.__perf = { long: [], frames: [], on: true };
    new PerformanceObserver((list) => {
      if (w.__perf.on) for (const e of list.getEntries()) w.__perf.long.push(e.duration);
    }).observe({ type: "longtask", buffered: false });
    let last = performance.now();
    const tick = (t: number) => {
      if (!w.__perf.on) return;
      w.__perf.frames.push(t - last);
      last = t;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  return async () => page.evaluate(() => {
    const w = window as unknown as { __perf: { long: number[]; frames: number[]; on: boolean } };
    w.__perf.on = false;
    const frames = [...w.__perf.frames].sort((a, b) => a - b);
    return {
      longTotal: w.__perf.long.reduce((a, b) => a + b, 0),
      longCount: w.__perf.long.length,
      p95: frames[Math.floor(frames.length * 0.95)] ?? 0,
      frames: frames.length,
    };
  });
}

test.describe("chart performance budgets", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "toronto", "the same in every zone");
  });

  test("80 Ctrl+wheel events at full speed: under 500 ms of long tasks", async ({ page }) => {
    await open(page);
    const logger = chart(page, "logger");
    await at(logger, 0.5);
    const stop = await record(page);
    await ctrlWheelBurst(logger, 0.6, 60, 80);
    await page.waitForTimeout(500);
    const m = await stop();
    console.log(`[perf] wheel burst, 1x: long tasks ${m.longCount} totalling ${m.longTotal.toFixed(0)} ms, frame p95 ${m.p95.toFixed(0)} ms`);
    expect(m.longTotal).toBeLessThan(500);
  });

  test("a slider drag at 4x CPU sends at most 2 requests", async ({ page }) => {
    const { net } = await open(page);
    const logger = chart(page, "logger");
    // Zoom in first, so the drag crosses many tiles
    await ctrlWheelBurst(logger, 0.5, -60, 30);
    await settled(page, net);
    await cpu(page, 4);
    const n0 = net.requests.length;
    const handle = navigatorWindow(logger);
    await handle.scrollIntoViewIfNeeded();
    const box = (await handle.boundingBox())!;
    const x0 = box.x + box.width / 2, y = box.y + box.height / 2;
    const stop = await record(page);
    await page.mouse.move(x0, y);
    await page.mouse.down();
    for (let i = 0; i < 120; i++) {
      await page.mouse.move(x0 - i * 2, y);
      await page.waitForTimeout(16);
    }
    await page.mouse.up();
    const m = await stop();
    await settled(page, net);
    console.log(`[perf] slider drag, 4x: ${net.requests.length - n0} requests, frame p95 ${m.p95.toFixed(0)} ms, long tasks ${m.longCount}`);
    expect(net.requests.length - n0).toBeLessThanOrEqual(2);
  });

  test.describe("on a phone", () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });

    test("a vertical swipe that starts on the navigator scrolls the page and leaves the chart alone", async ({ page }) => {
      const { net } = await open(page);
      const logger = chart(page, "logger");
      const track = logger.locator(".highcharts-navigator-outline");
      await track.scrollIntoViewIfNeeded();
      await page.evaluate(() => window.scrollBy(0, -200)); // room to scroll down
      const box = (await track.boundingBox())!;
      const before = await label(logger);
      const n0 = net.requests.length;
      const scrollY = await page.evaluate(() => window.scrollY);
      const cdp = await page.context().newCDPSession(page);
      const at = (y: number) => [{ x: box.x + box.width * 0.3, y, id: 1 }]; // on the track, away from the thumb
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(box.y + box.height / 2) });
      for (let i = 1; i <= 12; i++) {
        await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at(box.y + box.height / 2 - i * 15) });
        await page.waitForTimeout(16);
      }
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      await page.waitForTimeout(600);
      expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(scrollY + 50);
      expect(await label(logger)).toBe(before); // not paged, not dragged
      await settled(page, net);
      expect(net.requests.length - n0).toBe(0);
    });

    test("one finger moving sideways pans the chart; a tap on the navigator's track centres the window there", async ({ page }) => {
      const { net } = await open(page);
      const logger = chart(page, "logger");
      await logger.getByRole("button", { name: /Zoom in/ }).click(); // room to pan
      await settled(page, net);
      const cdp = await page.context().newCDPSession(page);
      const swipe = async (x: number, y: number, dx: number) => {
        await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y, id: 1 }] });
        for (let i = 1; i <= 12; i++) {
          await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x + (dx * i) / 12, y, id: 1 }] });
          await page.waitForTimeout(16);
        }
        await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      };
      const before = await label(logger);
      const p = await at(logger, 0.6);
      await swipe(p.x, p.y, -120); // finger to the left: later readings
      await expect.poll(() => label(logger)).not.toBe(before);
      await settled(page, net);
      const panned = (await label(logger))!;
      // A tap on the track left of the window (the left shade) centres the window there: on Oct 31
      const shade = logger.locator(".highcharts-navigator-mask-outside").first();
      const box = (await shade.boundingBox())!;
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: box.x + box.width * 0.2, y: box.y + box.height / 2, id: 1 }] });
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      await expect.poll(() => label(logger)).toMatch(/^Oct 31 /);
      expect(panned).toMatch(/^Nov 1 /);
    });

    test("in the larger view the plot keeps most of the width (one y-axis on a phone)", async ({ page }) => {
      await open(page);
      await page.getByRole("button", { name: /Open the .*graphs in a larger view/ }).first().click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.locator(".highcharts-container").first()).toBeVisible();
      await page.waitForTimeout(500);
      const shares = await page.evaluate(() => {
        type HChart = { container: HTMLElement; plotWidth: number; chartWidth: number };
        const H = (window as unknown as { _Highcharts?: { charts: (HChart | undefined)[] } })._Highcharts;
        return (H?.charts ?? []).filter((c): c is HChart => !!c && !!c.container.closest("[role=dialog]")).map((c) => c.plotWidth / c.chartWidth);
      });
      expect(shares.length).toBeGreaterThan(0);
      for (const s of shares) expect(s).toBeGreaterThanOrEqual(0.6);
    });

    test("a two-finger pinch at 4x CPU keeps long tasks under a second", async ({ page }) => {
      await open(page);
      const logger = chart(page, "logger");
      const p = await at(logger, 0.5, 0.35);
      const cdp = await cpu(page, 4);
      const touch = (type: string, spread: number) => cdp.send("Input.dispatchTouchEvent", {
        type,
        touchPoints: type === "touchEnd" ? [] : [{ x: p.x - spread, y: p.y, id: 1 }, { x: p.x + spread, y: p.y, id: 2 }],
      });
      const stop = await record(page);
      await touch("touchStart", 30);
      for (let i = 0; i < 40; i++) { await touch("touchMove", 30 + i * 3); await page.waitForTimeout(16); } // pinch out: zoom in
      for (let i = 0; i < 40; i++) { await touch("touchMove", 150 - i * 3); await page.waitForTimeout(16); } // and back
      await touch("touchEnd", 0);
      const m = await stop();
      console.log(`[perf] pinch, 4x: frame p95 ${m.p95.toFixed(0)} ms over ${m.frames} frames, long tasks ${m.longCount} totalling ${m.longTotal.toFixed(0)} ms`);
      expect(m.longTotal).toBeLessThan(1000);
    });
  });
});
