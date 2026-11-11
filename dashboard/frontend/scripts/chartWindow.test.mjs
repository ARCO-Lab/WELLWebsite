// Unit tests for src/utils/chartWindow.ts, with Node's built-in test runner (no extra packages):
//   npm test   (node --experimental-strip-types --test scripts/chartWindow.test.mjs)

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  pickBucket, zoneOffsetMs, wallToUtc, pickedDaysRange, snapDown, snapUp, normalizeWindow, shiftWindow,
  zoomOutWindow, zoomInWindow, detailRange, composePoints, composeBand, bucketLabel, Lru, MIN_RANGE_MS,
  clampToNow, daysCovering, planWindow, presetWindow, dataStart, torontoIso, parseIsoParam, windowFromSearch,
  searchWithWindow,
} from "../src/utils/chartWindow.ts";
import { seriesColor, seriesType, hasBand, compassLabel, weatherPanels } from "../src/utils/chartStyle.ts";

const H = 3600 * 1000;
const D = 24 * H;

test("pickBucket mirrors the backend ladder", () => {
  assert.equal(pickBucket(D), 600); // 144 points
  assert.equal(pickBucket(13 * D), 600); // 1,872 points
  assert.equal(pickBucket(14 * D), 1800); // 2,016 at 10 min: too many
  assert.equal(pickBucket(365 * D), 21600);
  assert.equal(pickBucket(4000 * D), 86400); // capped at daily
});

test("Toronto offsets, including both sides of DST", () => {
  assert.equal(zoneOffsetMs(Date.UTC(2026, 0, 15, 12)), -5 * H); // EST
  assert.equal(zoneOffsetMs(Date.UTC(2026, 6, 15, 12)), -4 * H); // EDT
  assert.equal(wallToUtc(Date.UTC(2026, 6, 15)), Date.UTC(2026, 6, 15, 4)); // local midnight in July
  assert.equal(wallToUtc(Date.UTC(2026, 0, 15)), Date.UTC(2026, 0, 15, 5));
});

test("picked days are Toronto midnight to the next midnight, whatever the browser zone", () => {
  const r = pickedDaysRange(new Date(2026, 3, 3), new Date(2026, 3, 10));
  assert.equal(r.start, Date.UTC(2026, 3, 3, 4));
  assert.equal(r.end, Date.UTC(2026, 3, 11, 4));
});

test("snapping follows the local grid, so daily buckets are local days", () => {
  const t = Date.UTC(2026, 3, 5, 15, 7); // 11:07 Toronto
  assert.equal(snapDown(t, 86400), Date.UTC(2026, 3, 5, 4));
  assert.equal(snapUp(t, 86400), Date.UTC(2026, 3, 6, 4));
  assert.equal(snapDown(t, 600), Date.UTC(2026, 3, 5, 15, 0));
  assert.equal(snapUp(t, 600), Date.UTC(2026, 3, 5, 15, 10));
  assert.equal(snapDown(Date.UTC(2026, 3, 5, 15), 600), Date.UTC(2026, 3, 5, 15)); // already on the grid
});

test("windows: at least an hour, inside the range, null when they cover it", () => {
  const picked = { start: 0, end: 10 * D };
  const tiny = normalizeWindow({ start: 5 * D, end: 5 * D + 60_000 }, picked); // a one-minute drag
  assert.equal(tiny.end - tiny.start, MIN_RANGE_MS);
  assert.equal(normalizeWindow({ start: -D, end: 11 * D }, picked), null);
  assert.deepEqual(normalizeWindow({ start: -D, end: D }, picked), { start: 0, end: 2 * D }); // pushed inside
  assert.deepEqual(shiftWindow({ start: 2 * D, end: 4 * D }, picked, 1), { start: 3 * D, end: 5 * D });
  assert.deepEqual(shiftWindow({ start: 0, end: 2 * D }, picked, -1), { start: 0, end: 2 * D }); // at the edge
  assert.deepEqual(zoomOutWindow({ start: 4 * D, end: 6 * D }, picked), { start: 3 * D, end: 7 * D });
  assert.equal(zoomOutWindow({ start: 2 * D, end: 8 * D }, picked), null); // back to the whole range
  assert.deepEqual(zoomInWindow(picked, picked), { start: 2.5 * D, end: 7.5 * D }); // half, around the centre
  assert.equal(zoomInWindow({ start: 0, end: H }, picked).end - zoomInWindow({ start: 0, end: H }, picked).start, MIN_RANGE_MS);
});

test("detail range: padded by half the width each side, clamped, snapped to the overview grid", () => {
  const picked = pickedDaysRange(new Date(2026, 3, 1), new Date(2026, 3, 30));
  const w = { start: Date.UTC(2026, 3, 10, 15, 7), end: Date.UTC(2026, 3, 10, 17, 7) }; // 2 h
  const r = detailRange(w, picked, 3600);
  assert.deepEqual(r, { start: Date.UTC(2026, 3, 10, 14), end: Date.UTC(2026, 3, 10, 19) });
  const edge = detailRange({ start: picked.start, end: picked.start + 2 * D }, picked, 21600);
  assert.equal(edge.start, picked.start);
});

test("composing: overview outside the detail range, detail inside, no gap at the joins", () => {
  const ob = 3600, db = 600;
  const overview = { t: [0, 1, 2, 3, 4, 5].map((h) => h * H), avg: [0, 1, 2, 3, 4, 5] };
  const detailT = [];
  for (let t = 2 * H; t < 4 * H; t += 600_000) detailT.push(t);
  const detail = { values: { t: detailT, avg: detailT.map(() => 9) }, bucketS: db, range: { start: 2 * H, end: 4 * H } };
  const pts = composePoints(overview, ob, detail);
  assert.deepEqual(pts.slice(0, 2), [[0, 0], [H, 1]]);
  assert.equal(pts.filter(([, v]) => v === 9).length, 12);
  assert.deepEqual(pts.slice(-2), [[4 * H, 4], [5 * H, 5]]);
  assert.ok(pts.every(([, v]) => v !== null), "no break where detail meets overview");
});

test("gaps longer than 2.5 buckets become a null, shorter ones don't", () => {
  const s = { t: [0, 600_000, 1_200_000, 1_200_000 + 2 * 600_000, 1_200_000 + 6 * 600_000], avg: [1, 2, 3, 4, 5] };
  const pts = composePoints(s, 600);
  assert.equal(pts.filter(([, v]) => v === null).length, 1); // only the 6-bucket gap (a night without power)
  assert.deepEqual(pts[4], [1_200_000 + 2 * 600_000 + 600_000, null]);
});

test("a series missing from the detail range shows a break, not a line across it", () => {
  const overview = { t: [0, H, 2 * H, 3 * H], avg: [1, 1, 1, 1] };
  const pts = composePoints(overview, 3600, { values: undefined, bucketS: 600, range: { start: H, end: 3 * H } });
  assert.deepEqual(pts.map(([, v]) => v), [1, null, 1]);
});

test("typed arrays as cached: NaN is a missing value, drawn as a break", () => {
  const s = { t: Float64Array.from([0, 600_000, 1_200_000]), avg: Float64Array.from([1, NaN, 3]) };
  assert.deepEqual(composePoints(s, 600), [[0, 1], [600_000, null], [1_200_000, 3]]);
});

test("labels", () => {
  assert.equal(bucketLabel(600, false), "10-minute readings");
  assert.equal(bucketLabel(43200, true), "12-hour averages");
  assert.equal(bucketLabel(86400, true), "daily averages");
});

test("LRU keeps the most recently used", () => {
  const c = new Lru(2);
  c.set("a", 1);
  c.set("b", 2);
  c.get("a");
  c.set("c", 3);
  assert.equal(c.get("b"), undefined);
  assert.equal(c.get("a"), 1);
  assert.equal(c.size, 2);
});

test("the min–max band follows the composed line: same times, same breaks", () => {
  const s = { t: [0, H, 2 * H, 6 * H], avg: [1, 2, 3, 4], min: [0, 1, NaN, 3], max: [2, 3, 4, 5] };
  const band = composeBand(s, 3600);
  const line = composePoints(s, 3600);
  assert.deepEqual(band.map(([t]) => t), line.map(([t]) => t));
  assert.deepEqual(band[0], [0, 0, 2]);
  assert.deepEqual(band[2], [2 * H, null, null]); // a missing min breaks the band there
  assert.deepEqual(band[3], [3 * H, null, null]); // the outage break
  assert.deepEqual(composeBand({ t: [0], avg: [1] }, 600), [[0, null, null]]); // no min/max: no band
});

test("picked days stop at the next whole hour after now", () => {
  const picked = pickedDaysRange(new Date(2026, 10, 10), new Date(2026, 10, 11)); // Nov 10-11, Toronto
  const now = Date.UTC(2026, 10, 11, 17, 12); // 12:12 EST on Nov 11
  assert.deepEqual(clampToNow(picked, now), { start: picked.start, end: Date.UTC(2026, 10, 11, 18) });
  assert.deepEqual(clampToNow(picked, Date.UTC(2026, 10, 20)), picked); // past days: unchanged
  const today = pickedDaysRange(new Date(2026, 10, 11), new Date(2026, 10, 11));
  assert.equal(clampToNow(today, today.start).end - today.start, MIN_RANGE_MS); // just after midnight: an hour
});

test("a window reaching outside the picked days: the days that cover it, and the window within them", () => {
  const w = { start: Date.UTC(2026, 9, 3, 18), end: Date.UTC(2026, 9, 5, 2) }; // Oct 3 14:00 - Oct 4 22:00 EDT
  const { startDay, endDay } = daysCovering(w);
  assert.deepEqual([startDay.getFullYear(), startDay.getMonth(), startDay.getDate()], [2026, 9, 3]);
  assert.deepEqual([endDay.getFullYear(), endDay.getMonth(), endDay.getDate()], [2026, 9, 4]);
  const plan = planWindow(w, Date.UTC(2026, 10, 1));
  assert.deepEqual(plan.viewWindow, w);
  const whole = pickedDaysRange(new Date(2026, 9, 3), new Date(2026, 9, 4));
  assert.equal(planWindow(whole, Date.UTC(2026, 10, 1)).viewWindow, null); // whole days: not zoomed
  // ends at midnight: that day isn't picked
  assert.equal(daysCovering({ start: whole.start, end: whole.end }).endDay.getDate(), 4);
});

test("range buttons: the last N days up to what is shown, All from the first day with data", () => {
  const now = Date.UTC(2026, 10, 11, 17, 12);
  const nextHour = Date.UTC(2026, 10, 11, 18);
  assert.deepEqual(presetWindow(1, { start: 0, end: nextHour }, now), { start: nextHour - D, end: nextHour });
  const shown = { start: Date.UTC(2026, 9, 1), end: Date.UTC(2026, 9, 10) };
  assert.deepEqual(presetWindow(7, shown, now), { start: shown.end - 7 * D, end: shown.end });
  assert.deepEqual(presetWindow("all", shown, now), { start: dataStart(), end: nextHour });
  assert.equal(dataStart(), Date.UTC(2025, 4, 8, 4)); // 2025-05-08 00:00 EDT
  assert.equal(presetWindow(30, { start: 0, end: dataStart() + D }, now).start, dataStart()); // never before data
});

test("links: Toronto ISO times out, and only sensible ones back in", () => {
  assert.equal(torontoIso(Date.UTC(2026, 10, 10, 19, 20, 30)), "2026-11-10T14:20-05:00");
  assert.equal(torontoIso(Date.UTC(2026, 6, 1, 16)), "2026-07-01T12:00-04:00");
  for (const ms of [Date.UTC(2026, 10, 10, 19, 20), Date.UTC(2026, 2, 8, 7, 30), Date.UTC(2026, 10, 1, 5, 30)]) {
    assert.equal(parseIsoParam(torontoIso(ms)), ms); // round trip, including both DST changes
  }
  assert.equal(parseIsoParam("2026-11-10T19:20Z"), Date.UTC(2026, 10, 10, 19, 20));
  assert.equal(parseIsoParam("2026-11-10T14:20"), Date.UTC(2026, 10, 10, 19, 20)); // no offset: Toronto
  assert.equal(parseIsoParam("2026-11-10"), Date.UTC(2026, 10, 10, 5)); // a day: its Toronto midnight
  assert.equal(parseIsoParam("2026-11-10T20:50 05:30"), Date.UTC(2026, 10, 10, 15, 20)); // a typed plus, read as a space
  for (const bad of ["", "yesterday", "2026-02-31", "2026-11-10T25:00", "1e12", "2026-11-10T14:20-05:00x", "Nov 10 2026"]) {
    assert.ok(Number.isNaN(parseIsoParam(bad)), bad);
  }
  const now = Date.UTC(2026, 10, 11, 17, 12);
  const q = "?from=2026-11-10T14:20-05:00&to=2026-11-10T18:00-05:00";
  assert.deepEqual(windowFromSearch(q, now), { start: Date.UTC(2026, 10, 10, 19, 20), end: Date.UTC(2026, 10, 10, 23) });
  assert.equal(windowFromSearch("?from=2026-11-10", now), null);
  assert.equal(windowFromSearch("?from=garbage&to=2026-11-10", now), null);
  assert.equal(windowFromSearch("?from=2026-11-10T18:00&to=2026-11-10T14:00", now), null); // backwards
  assert.equal(windowFromSearch("?from=2030-01-01&to=2030-02-01", now), null); // all in the future
  assert.equal(windowFromSearch("?from=2026-11-10T14:00&to=2026-11-10T14:20", now), null); // under an hour
  assert.equal(windowFromSearch("?from=2020-01-01&to=2025-06-01", now).start, dataStart()); // clamped to the data
  assert.equal(searchWithWindow("?tab=x", { start: Date.UTC(2026, 10, 10, 19, 20), end: Date.UTC(2026, 10, 10, 23) }),
    "?tab=x&from=2026-11-10T14%3A20-05%3A00&to=2026-11-10T18%3A00-05%3A00");
  assert.equal(searchWithWindow("?from=a&to=b", null), "");
  const back = searchWithWindow("", { start: Date.UTC(2026, 6, 1, 4), end: Date.UTC(2026, 6, 2, 4) });
  assert.deepEqual(windowFromSearch(back, now), { start: Date.UTC(2026, 6, 1, 4), end: Date.UTC(2026, 6, 2, 4) });
});

test("chart style: a fixed colour per measurement, and how each kind of series is drawn", () => {
  assert.equal(seriesColor("Water Surface Elevation"), seriesColor("Water Surface Elevation"));
  assert.notEqual(seriesColor("Water Surface Elevation"), seriesColor("Water Temperature"));
  assert.equal(seriesColor("Something new"), seriesColor("Something new")); // unknown: stable too
  assert.equal(seriesType("sum"), "column");
  assert.equal(seriesType("vector_mean"), "scatter");
  assert.equal(seriesType("mean"), "line");
  assert.equal(hasBand("mean", true), true);
  assert.equal(hasBand("mean", false), false); // raw readings: no band
  assert.equal(hasBand("sum", true), false);
  assert.equal(hasBand("vector_mean", true), false);
  assert.equal(compassLabel(225), "225° (SW)");
  assert.equal(compassLabel(-10), "350° (N)");
});

test("weather: one small chart per unit, in a fixed order", () => {
  const panels = weatherPanels(["Wind Speed", "Rain", "Air Temperature", "Gust Speed", "Soil Temperature", "Mystery",
    "All Weather"], new Set(["Mystery", "Rain"]));
  assert.deepEqual(panels.map((p) => p.title), ["Temperature (°C)", "Rain (mm)", "Wind speed (m/s)", "Mystery"]);
  assert.deepEqual(panels.map((p) => p.id), ["temperature", "rain", "wind-speed", "extra-mystery"]); // stable test ids
  const extras = weatherPanels(["Humidity", "Wind-Gust", "Wind Gust"], new Set(["Humidity", "Wind-Gust", "Wind Gust"]));
  assert.deepEqual(extras.map((p) => p.id), ["extra-humidity", "extra-wind-gust", "extra-wind-gust-2"]); // no collisions
  assert.deepEqual(panels[0].measurements, ["Air Temperature", "Soil Temperature"]);
  assert.deepEqual(panels[2].measurements, ["Wind Speed", "Gust Speed"]);
  assert.deepEqual(weatherPanels([]), []);
});
