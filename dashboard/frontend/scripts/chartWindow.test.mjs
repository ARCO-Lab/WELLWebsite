// Unit tests for src/utils/chartWindow.ts, with Node's built-in test runner (no extra packages):
//   npm test   (node --experimental-strip-types --test scripts/chartWindow.test.mjs)

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  pickBucket, zoneOffsetMs, wallToUtc, pickedDaysRange, snapDown, snapUp, normalizeWindow, shiftWindow,
  zoomOutWindow, zoomInWindow, detailRange, composePoints, bucketLabel, Lru, MIN_RANGE_MS,
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
