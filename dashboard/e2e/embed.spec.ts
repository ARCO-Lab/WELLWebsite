// The dashboard as the WordPress site embeds it (an iframe of /?embed=1; see dashboard/frontend/src/lib/embed.ts).
//   - The server HTML of /?embed=1 has no header or footer, so they can't flash before the page's scripts run.
//   - Framed by a stand-in for the WordPress Dashboard page, with the theme's real js/dashboard-embed.js, the iframe
//     is sized to the dashboard's content (no scrollbar inside it) through the two pages' messages.
//     As that page scrolls, the Filters panel stays in view (the iframe itself no longer scrolls).
//   - Framed without ?embed=1 (an old link), <html> is marked "in-frame" before first paint and the header is hidden.
// The stand-in page is served by the test itself (page.route) at the WordPress site's origin: nothing is fetched from
// the real site.

import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

// The stand-in page is "public" (its origin is the real site's) and frames the local server: without this, Chrome's
// local network access checks block the iframe.
test.use({ launchOptions: { args: ["--disable-features=LocalNetworkAccessChecks"] } });

// The origin the dashboard sends its height to (NEXT_PUBLIC_WP_HOME, unset in CI builds)
const WP_ORIGIN = "https://well.mcmaster.ca";
const EMBED_JS = fs.readFileSync(
  path.join(__dirname, "..", "..", "home", "wp-content", "themes", "well", "js", "dashboard-embed.js"), "utf-8");

/** Opens a stand-in WordPress page at WP_ORIGIN with the dashboard at `dashboardPath` in its iframe. */
async function openFramed(page: Page, baseURL: string, dashboardPath: string) {
  const dashboard = new URL(dashboardPath, baseURL);
  await page.route(`${WP_ORIGIN}/**`, (route) => route.fulfill({
    contentType: "text/html",
    body: `<!doctype html><html><body style="margin:0">
      <div style="height:300px">WordPress banner</div>
      <div class="well-dashboard-embed">
        <iframe id="well-dashboard-frame" title="WELL data dashboard" src="${dashboard.href}"
          data-dashboard-origin="${dashboard.origin}" style="display:block;width:100%;height:600px;border:0"></iframe>
      </div>
      <div style="height:800px">WordPress footer</div>
      <script>${EMBED_JS}</script>
    </body></html>`,
  }));
  await page.goto(`${WP_ORIGIN}/dashboard/`);
  const frame = page.frameLocator("#well-dashboard-frame");
  await expect(frame.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
  return frame;
}

test("the server HTML of /?embed=1 has no header or footer", async ({ request }) => {
  const embedded = await (await request.get("/?embed=1")).text();
  expect(embedded).toContain(">Dashboard</h1>");
  expect(embedded).not.toMatch(/<header[\s>]/);
  expect(embedded).not.toMatch(/<footer[\s>]/);
  expect(embedded).not.toContain("data-site-chrome");

  // The full page still has both, and the check that hides them in any other frame runs in <head>
  const full = await (await request.get("/")).text();
  expect(full).toMatch(/<header[\s>]/);
  expect(full).toMatch(/<footer[\s>]/);
  const head = full.slice(0, full.indexOf("</head>"));
  expect(head).toContain('classList.add("in-frame")');
});

test("embedded, the iframe is sized to the dashboard's content", async ({ page, baseURL }) => {
  const frame = await openFramed(page, baseURL!, "/?embed=1");
  const iframe = page.locator("#well-dashboard-frame");

  // The iframe takes the height of the dashboard's content, and the dashboard has nothing left to scroll
  await expect.poll(async () => {
    const outer = (await iframe.boundingBox())!.height;
    const inner = await frame.locator("main").evaluate((m) => Math.ceil(m.getBoundingClientRect().height));
    return Math.abs(outer - inner);
  }).toBeLessThanOrEqual(1);
  const overflow = await frame.locator("html").evaluate((h) => h.scrollHeight - h.clientHeight);
  expect(overflow).toBeLessThanOrEqual(0);

  // The page has told it which part is in view (for its dialogs), and there's no header or footer
  await expect(frame.locator("html")).toHaveClass(/embed-sized/);
  await expect(frame.locator("header")).toHaveCount(0);
  await expect(frame.locator("footer")).toHaveCount(0);
});

test("embedded, the Filters panel stays in view as the WordPress page scrolls", async ({ page, baseURL }) => {
  const frame = await openFramed(page, baseURL!, "/?embed=1");
  const iframe = page.locator("#well-dashboard-frame");
  const filters = frame.getByRole("heading", { level: 2, name: "Filters" }).first();

  // A tall block beside the panel, standing in for open graphs, makes the row (and the iframe) much taller
  await filters.evaluate((h) => {
    const row = h.closest(".lg\\:sticky")!.parentElement!.parentElement!;
    const spacer = document.createElement("div");
    spacer.style.height = "2500px";
    row.lastElementChild!.appendChild(spacer);
  });
  await expect.poll(async () => (await iframe.boundingBox())!.height).toBeGreaterThan(3000);

  // Scroll the WordPress page well past the panel's own place: the panel follows, inside the window
  const viewport = page.viewportSize()!;
  for (const by of [1200, 2000]) {
    await page.evaluate((y) => window.scrollTo(0, y), by);
    await expect.poll(async () => {
      const box = (await filters.boundingBox())!;
      return box.y >= 0 && box.y + box.height <= viewport.height;
    }).toBe(true);
  }
});

test("framed without ?embed=1, the header is hidden from the first paint", async ({ page, baseURL }) => {
  const frame = await openFramed(page, baseURL!, "/");
  await expect(frame.locator("html")).toHaveClass(/in-frame/);
  await expect(frame.locator("header")).toBeHidden();
  await expect(frame.locator("footer")).toBeHidden();
});
