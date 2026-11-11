// Unit tests for src/lib/seriesTiles.ts, src/lib/seriesLoader.ts and src/lib/chartController.ts, with Node's
// built-in test runner: npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  TILE_BUCKETS, bucketFor, tileAt, tileRange, tilesFor, tileQuery, toWall, fromWall, cutIntoTiles, segmentsFor,
  composeSeries, typicalFor, coarsestIn, tileSpanMs,
} from "../src/lib/seriesTiles.ts";
import { SeriesLoader, MAX_BATCH } from "../src/lib/seriesLoader.ts";
import { ChartController, clampWindow, OVERVIEW_BUCKET } from "../src/lib/chartController.ts";

const H = 3600 * 1000;
const D = 24 * H;
const LADDER = [600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 86400];

test("bucketFor: about 1.5 points per pixel, from the ladder", () => {
  assert.equal(bucketFor(2 * D, 600), 600); // 288 points
  assert.equal(bucketFor(2 * D, 100), 1800); // 150 points at least: 288 at 10 min is too many, 96 at 30 min
  assert.equal(bucketFor(7 * D, 600), 1800); // 1,008 at 10 min > 900; 336 at 30 min
  assert.equal(bucketFor(7 * D, 1200), 600); // 1,008 <= 1,800
  assert.equal(bucketFor(365 * D, 900), 12 * 3600); // 1,460 at 6 h is over 1,350; 730 at 12 h
  assert.equal(bucketFor(550 * D, 600), 86400);
  assert.equal(bucketFor(20 * 365 * D, 600), 86400); // never coarser than a day
  for (const days of [1, 3, 10, 30, 90, 365, 550]) {
    for (const px of [150, 390, 600, 1200]) {
      const b = bucketFor(days * D, px);
      const target = Math.min(3000, Math.max(150, px * 1.5));
      assert.ok(days * D / 1000 / b <= target || b === 86400, `${days} d at ${px} px`);
      const finer = LADDER[LADDER.indexOf(b) - 1];
      if (finer) assert.ok(days * D / 1000 / finer > target, `${days} d at ${px} px: ${finer} would do`);
    }
  }
});

test("wall-clock conversion round-trips, including both DST days", () => {
  for (const iso of ["2025-11-02T05:30:00Z", "2025-11-02T06:30:00Z", "2026-03-08T06:59:00Z", "2026-03-08T07:00:00Z", "2026-07-01T12:00:00Z"]) {
    const t = Date.parse(iso);
    assert.equal(fromWall(toWall(t)), t === Date.parse("2025-11-02T06:30:00Z") ? Date.parse("2025-11-02T05:30:00Z") : t, iso);
  }
  assert.equal(toWall(Date.parse("2026-07-01T04:00:00Z")), Date.UTC(2026, 6, 1)); // EDT midnight
  assert.equal(fromWall(Date.UTC(2026, 0, 15)), Date.parse("2026-01-15T05:00:00Z")); // EST midnight
});

for (const [label, day] of [["fall back, 2025-11-02", Date.UTC(2025, 10, 2)], ["spring forward, 2026-03-08", Date.UTC(2026, 2, 8)]]) {
  test(`tiles across ${label}: no gaps, no overlaps, every bucket in exactly one tile`, () => {
    for (const b of LADDER) {
      const span = tileSpanMs(b);
      const around = { start: fromWall(day) - 3 * span, end: fromWall(day) + 3 * span };
      const tiles = tilesFor(around, b);
      assert.ok(tiles.length >= 6);
      for (let n = 1; n < tiles.length; n++) {
        assert.equal(tiles[n], tiles[n - 1] + 1);
        assert.equal(tileRange(tiles[n - 1], b).end, tileRange(tiles[n], b).start, `b=${b}`);
      }
      // Every bucket start on the wall clock across the DST day lands in one tile, whose wall range holds it
      for (let w = day - 2 * D; w < day + 2 * D; w += b * 1000) {
        const t = fromWall(w);
        const i = tileAt(t, b);
        const r = tileRange(i, b);
        assert.ok(r.wallStart <= toWall(t) && toWall(t) < r.wallEnd, `b=${b} wall=${new Date(w).toISOString()}`);
      }
      // Tile edges are on 00:00 or 12:00, never in an hour the clocks skip or repeat
      for (const i of tiles) assert.ok([0, 12].includes(new Date(tileRange(i, b).wallStart).getUTCHours()), `b=${b}`);
    }
  });
}

test("tileQuery asks for wall-clock bounds ending a second before the next tile", () => {
  const b = 600;
  const i = tileAt(Date.parse("2026-10-02T12:00:00Z"), b);
  const q = tileQuery(i, i + 1, b);
  const r0 = tileRange(i, b), r1 = tileRange(i + 1, b);
  assert.equal(q.start, new Date(r0.wallStart).toISOString().slice(0, 19));
  assert.equal(q.end, new Date(r1.wallEnd - 1000).toISOString().slice(0, 19));
  assert.equal((r1.wallEnd - r0.wallStart) / 1000 / b, 2 * TILE_BUCKETS);
});

// A fake series: one point per bucket from `from` to `to` (instants), value = hours since epoch
function fakeSeries(from, to, b, extra = {}) {
  const t = [], avg = [], min = [], max = [], n = [];
  for (let w = toWall(from); w < toWall(to); w += b * 1000) {
    const x = fromWall(w);
    t.push(x); avg.push(x / H); min.push(x / H - 1); max.push(x / H + 1); n.push(extra.n ? extra.n(x) : b / 600);
  }
  return { group_type: "Logger", station_id: "1", measurement_type: "Level", unit: "m", agg: "mean", t, avg, min, max, n };
}

test("cutIntoTiles puts each bucket in its tile; empty tiles stay empty", () => {
  const b = 3600, i = tileAt(Date.parse("2026-10-01T12:00:00Z"), b);
  const s = fakeSeries(tileRange(i, b).start, tileRange(i + 1, b).start + 5 * H, b);
  const cut = cutIntoTiles(s, i, i + 2, b);
  assert.equal(cut.get(i).t.length, TILE_BUCKETS);
  assert.equal(cut.get(i + 1).t.length, 5);
  assert.equal(cut.get(i + 2).t.length, 0);
});

test("segmentsFor: finer loaded tiles replace coarser ones, adjacent pieces merge", () => {
  const segs = segmentsFor([
    { bucketS: 86400, tiles: [100, 101] },
    { bucketS: 3600, tiles: [2401, 2402, 2404] }, // 15-day tiles inside the first 360-day one
  ]);
  const day = tileSpanMs(86400), hour = tileSpanMs(3600);
  assert.deepEqual(segs.map((g) => g.bucketS), [86400, 3600, 86400, 3600, 86400]);
  assert.equal(segs[0].wallStart, 100 * day);
  assert.equal(segs[1].wallStart, 2401 * hour);
  assert.equal(segs[1].wallEnd, 2403 * hour); // 2401 and 2402 merged
  assert.equal(segs[4].wallEnd, 102 * day);
  for (let n = 1; n < segs.length; n++) assert.equal(segs[n - 1].wallEnd, segs[n].wallStart); // no gaps
});

test("composeSeries: coarse outside, fine inside, bucket middles, breaks across gaps", () => {
  const day = 86400, hour = 3600;
  const iD = tileAt(Date.parse("2026-09-01T12:00:00Z"), day);
  const iH = tileAt(Date.parse("2026-10-01T12:00:00Z"), hour);
  const coarse = cutIntoTiles(fakeSeries(tileRange(iD, day).start, tileRange(iD, day).end, day), iD, iD, day);
  const fineSeries = fakeSeries(tileRange(iH, hour).start, tileRange(iH, hour).end, hour);
  // a 10-hour outage in the hourly data
  const cutAt = 100;
  for (const f of ["avg", "min", "max", "n"]) fineSeries[f].splice(cutAt, 10);
  fineSeries.t.splice(cutAt, 10);
  const fine = cutIntoTiles(fineSeries, iH, iH, hour);
  const segs = segmentsFor([{ bucketS: day, tiles: [iD] }, { bucketS: hour, tiles: [iH] }]);
  const tile = (b, i) => (b === day ? coarse.get(i) : fine.get(i));
  const pts = composeSeries(segs, tile, () => () => null);
  const real = pts.filter((p) => p.y !== null);
  // Hourly points only inside the hourly tile, daily ones only outside it, and none overlapping
  const { wallStart, wallEnd } = tileRange(iH, hour);
  for (const p of real) {
    const w = toWall(p.custom.start);
    if (p.custom.bucketS === hour) assert.ok(w >= wallStart && w < wallEnd);
    else assert.ok(w + D <= wallStart || w >= wallEnd);
    assert.equal(p.x, p.custom.start + p.custom.bucketS * 500); // drawn at the bucket's middle
  }
  for (let n = 1; n < real.length; n++) assert.ok(real[n].x > real[n - 1].x); // in order
  assert.equal(real.filter((p) => p.custom.bucketS === hour).length, TILE_BUCKETS - 10);
  assert.ok(pts.some((p) => p.y === null)); // the outage is a break
  assert.equal(coarsestIn(segs, { start: tileRange(iH, hour).start + H, end: tileRange(iH, hour).start + 5 * H }), hour);
  assert.equal(coarsestIn(segs, { start: tileRange(iD, day).start, end: tileRange(iD, day).start + D }), day);
});

test("partial buckets: judged by the series' usual count at that time of day, over all its loaded tiles", () => {
  const b = 3600;
  const i = tileAt(Date.parse("2026-07-01T12:00:00Z"), b);
  // A sonde-like series: 6 readings an hour by day, 2 at night (01-05 UTC), and one daytime hour with only 1
  const bad = tileRange(i, b).start + 3 * D + 14 * H;
  const n = (x) => (x === bad ? 1 : new Date(x).getUTCHours() >= 1 && new Date(x).getUTCHours() < 5 ? 2 : 6);
  const s = fakeSeries(tileRange(i, b).start, tileRange(i + 1, b).end, b, { n });
  const tiles = cutIntoTiles(s, i, i + 1, b);
  const typical = typicalFor(tiles.values());
  const night = Date.UTC(2026, 6, 2, 3), day = Date.UTC(2026, 6, 2, 15);
  assert.equal(typical(night), 2);
  assert.equal(typical(day), 6);
  const segs = segmentsFor([{ bucketS: b, tiles: [i, i + 1] }]);
  const pts = composeSeries(segs, (bb, k) => tiles.get(k), () => typical).filter((p) => p.y !== null);
  const partial = pts.filter((p) => p.custom.partial);
  assert.deepEqual(partial.map((p) => p.custom.start), [bad]); // night buckets with 2 readings are normal for it
  assert.equal(partial[0].custom.typical, 6);
  // From one tile alone the same bucket is judged the same way (both tiles are long enough to learn from)
  assert.equal(typicalFor([tiles.get(i)])(bad), 6);
});

// ---- the loader ----

function fakeServer({ fail = () => false } = {}) {
  const calls = [];
  const resolvers = [];
  const fetchTiles = (req) => new Promise((resolve, reject) => {
    calls.push(req);
    resolvers.push(() => {
      if (fail(req)) return reject(new Error("HTTP 500"));
      const b = req.bucketS;
      const from = tileRange(req.first, b).start, to = tileRange(req.last, b).end;
      resolve(req.keys.map((k) => {
        const [g, st, m] = k.split("|");
        return { ...fakeSeries(from, to, b), group_type: g, station_id: st, measurement_type: m };
      }));
    });
  });
  const settle = async () => {
    while (resolvers.length) {
      resolvers.shift()();
      await new Promise((r) => setTimeout(r, 0));
    }
  };
  return { calls, fetchTiles, settle, inFlight: () => resolvers.length };
}

const A = "Logger|1|Level", B = "Logger|1|Temp", C = "Weather|2|Rain";

test("loader: identical tiles are asked for once, and neighbours go in one request", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  let changes = 0;
  loader.want("chart1", [A, B], 600, [10, 11, 12], 0, () => changes++);
  loader.want("chart2", [A, B], 600, [11, 12], 0, () => changes++);
  assert.equal(srv.calls.length, 1);
  assert.deepEqual(srv.calls[0], { keys: [A, B], bucketS: 600, first: 10, last: 12 });
  assert.equal(loader.stats.deduped, 4);
  await srv.settle();
  assert.equal(changes, 2);
  loader.want("chart3", [A], 600, [10, 11, 12], 0, () => {});
  assert.equal(srv.calls.length, 1); // all cached
  assert.equal(loader.stats.hits, 3);
  assert.equal(loader.tile(A, 600, 11).t.length, TILE_BUCKETS);
});

test("loader: at most 2 requests in flight; a queued request nobody wants is dropped; one in flight finishes and is cached", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  for (let n = 0; n < 6; n++) loader.want(`c${n}`, [A], 1800, [n * 20], 0, () => {});
  assert.equal(srv.calls.length, 2);
  assert.equal(loader.stats.peakInFlight, 2);
  // c0 and c1 are on their way; c2..c5 queued. c3 changes its mind, c4 goes away.
  loader.want("c3", [A], 1800, [], 0, () => {});
  loader.release("c4");
  loader.want("c0", [A], 1800, [], 0, () => {}); // no longer wants its tile, but the request was sent
  assert.equal(loader.stats.dropped, 2);
  await srv.settle();
  assert.equal(srv.calls.length, 4); // c0, c1, c2, c5
  assert.deepEqual(srv.calls.map((c) => c.first), [0, 20, 40, 100]);
  assert.ok(loader.has(A, 1800, 0)); // c0's tile was cached anyway
  assert.equal(loader.stats.peakInFlight, 2);
});

test("loader: runs longer than MAX_BATCH are split; gaps split runs", () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles, 3000, 10);
  const want = [...Array(MAX_BATCH + 2).keys(), 50];
  loader.want("c", [A], 600, want, 0, () => {});
  assert.deepEqual(srv.calls.map((c) => [c.first, c.last]), [[0, MAX_BATCH - 1], [MAX_BATCH, MAX_BATCH + 1], [50, 50]]);
});

test("loader: charts wanting the same tiles share one request for all their series; visible first", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  loader.want("busy1", [C], 600, [1], 0, () => {});
  loader.want("busy2", [C], 600, [3], 0, () => {}); // two in flight now
  loader.want("offscreen", [A], 600, [7, 8], 2, () => {});
  loader.want("logger", [A, B], 600, [7, 8], 0, () => {});
  loader.want("weather", [C], 600, [7, 8], 0, () => {});
  await srv.settle();
  assert.equal(srv.calls.length, 3);
  assert.deepEqual(srv.calls[2], { keys: [A, B, C], bucketS: 600, first: 7, last: 8 });
});

test("loader: a failed request caches nothing and reports the error; asking again retries", async () => {
  let failing = true;
  const srv = fakeServer({ fail: () => failing });
  const loader = new SeriesLoader(srv.fetchTiles);
  let changed = 0;
  loader.want("c", [A], 600, [5], 0, () => changed++);
  await srv.settle();
  assert.equal(changed, 1);
  assert.equal(loader.has(A, 600, 5), false);
  assert.match(loader.error("c").message, /500/);
  failing = false;
  loader.want("c", [A], 600, [5], 0, () => changed++);
  assert.equal(loader.error("c"), null);
  await srv.settle();
  assert.equal(srv.calls.length, 2);
  assert.ok(loader.has(A, 600, 5));
});

test("loader: least recently used tiles go first when the cache is full", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles, 3, 2);
  loader.want("c", [A], 600, [1, 2, 3], 0, () => {});
  await srv.settle();
  loader.tile(A, 600, 1); // used: now the newest
  loader.want("c", [A], 600, [9], 0, () => {});
  await srv.settle();
  assert.equal(loader.cachedEntries, 3);
  assert.ok(loader.has(A, 600, 1) && loader.has(A, 600, 3) && loader.has(A, 600, 9));
  assert.equal(loader.has(A, 600, 2), false);
  assert.deepEqual([...loader.loadedTiles(A, 600)].sort((a, b) => a - b), [1, 3, 9]);
});

// ---- the chart controller ----

const now = Date.parse("2026-11-11T17:00:00Z");
const extent = { start: Date.parse("2025-05-08T04:00:00Z"), end: now };
const twoDays = { start: now - 2 * D, end: now };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const syncFrame = (cb) => setTimeout(cb, 0);

test("controller: a burst of 80 zoom steps ends in one request for the window", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const c = new ChartController("logger-1", [A, B], twoDays, extent, loader, syncFrame, 30);
  c.setPlotWidth(600);
  c.activate();
  await srv.settle();
  const before = srv.calls.length;
  c.setWindow({ start: Date.parse("2026-01-01T05:00:00Z"), end: Date.parse("2026-12-01T05:00:00Z") }, "slider");
  await sleep(60);
  await srv.settle();
  const zoomStart = srv.calls.length;
  const at = Date.parse("2026-10-02T12:00:00Z");
  for (let n = 0; n < 80; n++) {
    c.zoom(0.93, at, "wheel");
    await sleep(2);
  }
  await sleep(60);
  assert.ok(srv.calls.length - zoomStart <= 2, `${srv.calls.length - zoomStart} requests`);
  await srv.settle();
  const span = c.window.end - c.window.start;
  assert.ok(span < 3 * D, `zoomed to ${span / H} h`);
  assert.equal(c.snapshot().wantedBucket, 600);
  assert.equal(c.snapshot().shownBucket, 600);
  assert.ok(before >= 1);
  // Reset and coming back need nothing new
  const n0 = srv.calls.length;
  c.reset();
  await sleep(60);
  c.setWindow({ start: at - 12 * H, end: at + 12 * H }, "key");
  await sleep(60);
  assert.equal(srv.calls.length, n0);
  c.dispose();
});

test("controller: two charts keep their own windows", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const one = new ChartController("logger-1", [A], twoDays, extent, loader, syncFrame, 10);
  const four = new ChartController("logger-4", [B], twoDays, extent, loader, syncFrame, 10);
  one.activate();
  four.activate();
  one.setWindow({ start: Date.parse("2026-10-01T04:00:00Z"), end: Date.parse("2026-10-04T04:00:00Z") }, "select");
  four.setWindow({ start: Date.parse("2026-06-01T04:00:00Z"), end: Date.parse("2026-06-22T04:00:00Z") }, "slider");
  await sleep(30);
  await srv.settle();
  assert.equal(one.window.start, Date.parse("2026-10-01T04:00:00Z"));
  assert.equal(four.window.start, Date.parse("2026-06-01T04:00:00Z"));
  assert.ok(one.lastData.series.get(A).some((p) => p.custom?.bucketS === 600));
  assert.ok(four.lastData.series.get(B).every((p) => !p.custom || p.custom.bucketS >= 1800));
});

test("clampWindow keeps a window inside the extent and at least an hour wide", () => {
  const w = clampWindow({ start: extent.start - 10 * D, end: extent.start - 9 * D }, extent);
  assert.equal(w.start, extent.start);
  assert.equal(w.end - w.start, D);
  const tiny = clampWindow({ start: now - 60_000, end: now }, extent);
  assert.equal(tiny.end - tiny.start, H);
  assert.equal(tiny.end, now);
  assert.equal(OVERVIEW_BUCKET, 86400);
});

test("controller: a slow gesture sends nothing until it ends, however long its frames take", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const c = new ChartController("logger-1", [A, B], twoDays, extent, loader, syncFrame, 30);
  c.activate();
  await sleep(60);
  await srv.settle();
  const n0 = srv.calls.length;
  c.beginGesture();
  // A drag on a slow phone: moves 100 ms apart (longer than the debounce), across a year, for about a second
  for (let i = 0; i < 10; i++) {
    c.pan(-3, "slider");
    await sleep(100);
  }
  assert.equal(srv.calls.length, n0); // held
  c.endGesture();
  await sleep(60);
  assert.ok(srv.calls.length - n0 >= 1 && srv.calls.length - n0 <= 2, `${srv.calls.length - n0} requests`);
  await srv.settle();
  c.dispose();
});

test("controller: a gesture longer than the max wait fetches only the window it is on", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const c = new ChartController("logger-1", [A], twoDays, extent, loader, syncFrame, 30);
  c.activate();
  await sleep(60);
  await srv.settle();
  const n0 = srv.calls.length;
  c.beginGesture();
  c.setWindow({ start: Date.parse("2026-03-01T05:00:00Z"), end: Date.parse("2026-03-03T05:00:00Z") }, "slider");
  for (let i = 0; i < 9; i++) { // 1.8 s of small moves
    c.pan(0.01, "slider");
    await sleep(200);
  }
  const during = srv.calls.slice(n0);
  assert.equal(during.length, 1); // one max-wait fetch, for the window's tiles only (no history, no padding)
  assert.equal(during[0].bucketS, 600);
  assert.ok(during[0].last - during[0].first <= 1);
  c.endGesture();
  await srv.settle();
  c.dispose();
});

test("controller: a gesture whose end was lost ends by itself", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const c = new ChartController("logger-1", [A], twoDays, extent, loader, syncFrame, 30);
  c.activate();
  c.beginGesture();
  c.pan(-1, "drag");
  assert.equal(c.inGesture, true);
  await sleep(3200 + 1600); // idle past GESTURE_IDLE_MS, checked at the next max-wait
  assert.equal(c.inGesture, false);
  c.dispose();
});

test("loader: wishes made together within the batch window go in one request", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles, 3000, 2, 20);
  loader.want("logger-1", [A], 600, [7], 0, () => {});
  loader.want("logger-2", [B], 600, [7], 0, () => {});
  loader.want("rain", [C], 600, [7], 0, () => {});
  assert.equal(srv.calls.length, 0);
  await sleep(40);
  assert.equal(srv.calls.length, 1);
  assert.deepEqual(srv.calls[0].keys, [A, B, C]);
  await srv.settle();
});

test("bucketFor: about one point per pixel on phones", () => {
  assert.equal(bucketFor(3 * D, 300), 600); // 432 points at 1.5 per px (450)
  assert.equal(bucketFor(3 * D, 300, 1), 1800); // over 300 at 1 per px: 30-min buckets (144)
});
