// Unit tests for src/utils/chartWindow.ts, with Node's built-in test runner (no extra packages):
//   npm test   (node --experimental-strip-types --test scripts/chartWindow.test.mjs)

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  pickBucket, zoneOffsetMs, wallToUtc, pickedDaysRange, snapDown, snapUp, normalizeWindow, shiftWindow,
  zoomOutWindow, zoomInWindow, detailRange, composePoints, bucketLabel, bucketSpanLabel, shortBucket, valueDecimals,
  isPartial, Lru, MIN_RANGE_MS,
} from "../src/utils/chartWindow.ts";

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

const xy = (pts) => pts.map((p) => [p.x, p.y]);

test("composing: overview outside the detail range, detail inside, no gap at the joins", () => {
  const ob = 3600, db = 600;
  const overview = { t: [0, 1, 2, 3, 4, 5].map((h) => h * H), avg: [0, 1, 2, 3, 4, 5] };
  const detailT = [];
  for (let t = 2 * H; t < 4 * H; t += 600_000) detailT.push(t);
  const detail = { values: { t: detailT, avg: detailT.map(() => 9) }, bucketS: db, range: { start: 2 * H, end: 4 * H } };
  const pts = xy(composePoints(overview, ob, detail));
  // hourly buckets are drawn at their middle (half past), raw 10-minute readings at their own time
  assert.deepEqual(pts.slice(0, 2), [[H / 2, 0], [1.5 * H, 1]]);
  assert.deepEqual(pts.filter(([, v]) => v === 9).map(([x]) => x), detailT);
  assert.deepEqual(pts.slice(-2), [[4.5 * H, 4], [5.5 * H, 5]]);
  assert.ok(pts.every(([, v]) => v !== null), "no break where detail meets overview");
});

test("gaps longer than 2.5 buckets become a null, shorter ones don't", () => {
  const s = { t: [0, 600_000, 1_200_000, 1_200_000 + 2 * 600_000, 1_200_000 + 6 * 600_000], avg: [1, 2, 3, 4, 5] };
  const pts = xy(composePoints(s, 600));
  assert.equal(pts.filter(([, v]) => v === null).length, 1); // only the 6-bucket gap (a night without power)
  assert.deepEqual(pts[4], [1_200_000 + 2 * 600_000 + 600_000, null]);
});

test("a series missing from the detail range shows a break, not a line across it", () => {
  const overview = { t: [0, H, 2 * H, 3 * H], avg: [1, 1, 1, 1] };
  const pts = composePoints(overview, 3600, { values: undefined, bucketS: 600, range: { start: H, end: 3 * H } });
  assert.deepEqual(pts.map((p) => p.y), [1, null, 1]);
});

test("typed arrays as cached: NaN is a missing value, drawn as a break", () => {
  const s = { t: Float64Array.from([0, 600_000, 1_200_000]), avg: Float64Array.from([1, NaN, 3]) };
  assert.deepEqual(xy(composePoints(s, 600)), [[0, 1], [600_000, null], [1_200_000, 3]]);
});

test("points carry their bucket, min/max and count", () => {
  const s = { t: [0, 6 * H], avg: [5, 6], min: [4, NaN], max: [7, null], n: [36, 17] };
  const [full, part] = composePoints(s, 21600);
  assert.deepEqual(full.custom,
    { start: 0, bucketS: 21600, lo: 4, hi: 7, n: 36, typical: null, partial: false, isolated: false });
  assert.equal(part.x, 9 * H);
  assert.deepEqual([part.custom.lo, part.custom.hi], [null, null]);
  // two buckets are too few to know what is usual, so neither is called partial
  assert.equal(part.custom.partial, false);
  assert.equal(composePoints({ t: [0], avg: [1] }, 21600)[0].custom.partial, false); // count unknown
  assert.equal(isPartial(1, 600, 6), false); // a raw reading
  assert.equal(isPartial(3, 3600, 6), false); // exactly half
  assert.equal(isPartial(2, 3600, 6), true);
});

// A sonde that reports 08:20-18:10 Toronto time and is silent every night, as the water quality one is.
function dayOnly(days, bucketS, outageDay = -1) {
  const t = [], avg = [], n = [];
  const start = wallToUtc(Date.UTC(2026, 5, 1));
  const counts = new Map();
  for (let d = 0; d < days; d++) {
    if (d === outageDay) continue;
    for (let m = 8 * 60 + 20; m <= 18 * 60 + 10; m += 10) {
      if (outageDay >= 0 && d === outageDay + 1 && m < 16 * 60) continue; // the day after an outage starts at 16:00
      const reading = start + d * D + m * 60_000;
      const b = snapDown(reading, bucketS);
      counts.set(b, (counts.get(b) ?? 0) + 1);
    }
  }
  for (const [b, c] of [...counts].sort((x, y) => x[0] - y[0])) { t.push(b); avg.push(1); n.push(c); }
  return { t, avg, n };
}

test("a day-only cadence is normal, not partial, at every bucket size", () => {
  for (const bucketS of [3600, 21600, 43200, 86400]) {
    const pts = composePoints(dayOnly(30, bucketS), bucketS).filter((p) => p.y !== null);
    assert.equal(pts.filter((p) => p.custom.partial).length, 0, `${bucketS}-s buckets`);
  }
  // e.g. a full day holds 60 readings, not 144, and the evening bucket's one reading is what that bucket usually holds
  const daily = composePoints(dayOnly(30, 86400), 86400).filter((p) => p.y !== null);
  assert.equal(daily[5].custom.typical, 60);
  const evening = composePoints(dayOnly(30, 21600), 21600).find((p) => p.custom?.n === 2);
  assert.equal(evening.custom.typical, 2);
});

test("a real outage is partial against the series' own usual count", () => {
  const daily = composePoints(dayOnly(30, 86400, 10), 86400).filter((p) => p.y !== null);
  const after = daily.filter((p) => p.custom.partial);
  assert.equal(after.length, 1); // only the day it came back at 16:00 (14 readings of the usual 60)
  assert.equal(after[0].custom.n, 14);
  const sixHour = composePoints(dayOnly(30, 21600, 10), 21600).filter((p) => p.custom?.partial);
  assert.equal(sixHour.length, 1); // that day's 12:00-18:00 bucket, from 16:00: 12 readings of the usual 36
  assert.equal(sixHour[0].custom.n, 12);
});

test("a point with no neighbour on either side is isolated, so it can get a marker", () => {
  const s = { t: [0, 600_000, 10 * 600_000, 20 * 600_000, 21 * 600_000], avg: [1, 2, 3, 4, 5] };
  const pts = composePoints(s, 600).filter((p) => p.y !== null);
  assert.deepEqual(pts.map((p) => p.custom.isolated), [false, false, true, false, false]);
  assert.equal(composePoints({ t: [0], avg: [1] }, 600)[0].custom.isolated, true); // a lone reading
});

test("bucket spans in Toronto wall-clock time", () => {
  const sixPm = wallToUtc(Date.UTC(2026, 9, 1, 18)); // Oct 1, 18:00 EDT
  assert.equal(bucketSpanLabel(sixPm, 21600), "Oct 1, 2026 18:00–24:00");
  assert.equal(bucketSpanLabel(sixPm, 1800), "Oct 1, 2026 18:00–18:30");
  assert.equal(bucketSpanLabel(sixPm + 600_000, 600), "Oct 1, 2026 18:10");
  assert.equal(bucketSpanLabel(wallToUtc(Date.UTC(2026, 0, 5)), 86400), "Jan 5, 2026");
  assert.equal(shortBucket(21600), "6-h");
  assert.equal(shortBucket(600), "10-min");
  assert.equal(shortBucket(86400), "daily");
  assert.equal(valueDecimals("m asl"), 3);
  assert.equal(valueDecimals("°C"), 1);
  assert.equal(valueDecimals("something new"), 2);
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
