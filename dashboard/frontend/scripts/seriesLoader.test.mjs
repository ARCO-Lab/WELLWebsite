// Unit tests for src/lib/seriesTiles.ts, src/lib/seriesLoader.ts and src/lib/chartController.ts, with Node's
// built-in test runner: npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  TILE_BUCKETS, bucketFor, tileAt, tileRange, tilesFor, tileQuery, toWall, fromWall, cutIntoTiles, segmentsFor,
  composeSeries, typicalFor, coarsestIn, tileSpanMs, fitWindow, coarsen, baseBucket, MAX_TILES, bucketInstant,
} from "../src/lib/seriesTiles.ts";
import { SeriesLoader, MAX_BATCH, fetchFromApi, RETRY_DELAYS_MS } from "../src/lib/seriesLoader.ts";
import { ChartController, clampWindow, overviewBucket, fillTiles } from "../src/lib/chartController.ts";

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
  assert.equal(overviewBucket(extent, 600, 1.5), 86400); // 18 months at 600 px: daily
  assert.equal(overviewBucket(twoDays, 600, 1.5), 600); // two days: 10-minute readings
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

test("controller: a lingering gesture longer than the max wait fetches only the window it is on; a sweep doesn't", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const c = new ChartController("logger-1", [A], twoDays, extent, loader, syncFrame, 30);
  c.activate();
  await sleep(60);
  await srv.settle();
  const n0 = srv.calls.length;
  c.setWindow({ start: Date.parse("2026-03-01T05:00:00Z"), end: Date.parse("2026-03-03T05:00:00Z") }, "slider");
  c.beginGesture(); // before the debounce fires: nothing sent yet
  for (let i = 0; i < 9; i++) { // 1.8 s of small moves: lingering
    c.pan(0.01, "slider");
    await sleep(200);
  }
  const during = srv.calls.slice(n0);
  assert.equal(during.length, 1); // one max-wait fetch: the window's tiles, filled up to one request (no history)
  assert.equal(during[0].bucketS, 600);
  assert.ok(during[0].last - during[0].first + 1 <= 8);
  const shown = tilesFor(c.window, 600);
  assert.ok(during[0].first <= shown[0] && during[0].last >= shown[shown.length - 1]);
  c.endGesture();
  await sleep(60);
  await srv.settle();
  // A sweep: a window's width or more every 100 ms for 1.8 s sends nothing until it ends
  const n1 = srv.calls.length;
  c.beginGesture();
  for (let i = 0; i < 18; i++) {
    c.pan(-1.5, "slider");
    await sleep(100);
  }
  assert.equal(srv.calls.length, n1);
  c.endGesture();
  await sleep(60);
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

test("loader: a tile still filling in is fetched again after a minute; older tiles never are", async () => {
  const srv = fakeServer();
  let clock = Date.parse("2026-11-11T17:00:00Z");
  const loader = new SeriesLoader(srv.fetchTiles, 3000, 2, 0, () => clock);
  const live = tileAt(clock - 3600e3, 600); // ends after now - 1 h: still getting readings
  const old = live - 3;
  let changes = 0;
  loader.want("c", [A], 600, [old, live], 0, () => changes++);
  await srv.settle();
  const n0 = srv.calls.length;
  const rev0 = loader.revision(A);
  clock += 30_000;
  loader.want("c", [A], 600, [old, live], 0, () => changes++);
  assert.equal(srv.calls.length, n0); // fresh for a minute
  clock += 40_000;
  loader.want("c", [A], 600, [old, live], 0, () => changes++);
  assert.equal(srv.calls.length, n0 + 1); // the live tile only
  assert.deepEqual([srv.calls.at(-1).first, srv.calls.at(-1).last], [live, live]);
  assert.ok(loader.has(A, 600, live)); // the old copy is still drawn meanwhile
  await srv.settle();
  assert.ok(loader.revision(A) > rev0); // charts recompose with the new readings
  clock += 10 * 60_000;
  loader.want("c", [A], 600, [old], 0, () => {});
  assert.equal(srv.calls.length, n0 + 1); // a past tile stays cached
});

test("loader: a failed refresh of a cached live tile shows no error and tries again; a new tile's failure does", async () => {
  let failing = false;
  const srv = fakeServer({ fail: () => failing });
  let clock = Date.parse("2026-11-11T17:00:00Z");
  const loader = new SeriesLoader(srv.fetchTiles, 3000, 2, 0, () => clock);
  const live = tileAt(clock - 3600e3, 600);
  loader.want("c", [A], 600, [live], 0, () => {});
  await srv.settle();
  const rev = loader.revision(A);
  failing = true;
  clock += 61_000;
  const warn = console.warn;
  console.warn = () => {};
  try {
    loader.want("c", [A], 600, [live], 0, () => {});
    await srv.settle();
  } finally {
    console.warn = warn;
  }
  assert.equal(loader.error("c"), null); // the old copy is still drawn
  assert.ok(loader.has(A, 600, live));
  assert.equal(loader.revision(A), rev); // nothing replaced
  const n = srv.calls.length;
  loader.want("c", [A], 600, [live], 0, () => {});
  assert.equal(srv.calls.length, n + 1); // tried again
  await srv.settle();
  loader.want("d", [B], 600, [live], 0, () => {}); // never loaded: its failure is an error
  await srv.settle();
  assert.match(loader.error("d").message, /500/);
});

// ---- fitting the window to where the data is ----

test("fitWindow: from the first bucket with data to the end of the last, inside the picked range", () => {
  const range = { start: Date.parse("2026-11-10T05:00:00Z"), end: Date.parse("2026-11-12T05:00:00Z") }; // Nov 10-11 EST
  // Data only on Nov 11 from 9:00 to 17:00 (10-minute readings: last bucket starts 16:50)
  const w = fitWindow(range, Date.parse("2026-11-11T14:00:00Z"), Date.parse("2026-11-11T21:50:00Z"), 600, H);
  assert.deepEqual(w, { start: Date.parse("2026-11-11T14:00:00Z"), end: Date.parse("2026-11-11T22:00:00Z") });
  // Data that starts inside the range and runs past its end: cut at the range
  const late = fitWindow(range, Date.parse("2026-11-11T20:00:00Z"), Date.parse("2026-11-12T08:00:00Z"), 600, H);
  assert.deepEqual(late, { start: Date.parse("2026-11-11T20:00:00Z"), end: range.end });
  // Data that started before the range and stops inside it
  const early = fitWindow(range, Date.parse("2026-11-09T00:00:00Z"), Date.parse("2026-11-10T09:00:00Z"), 3600, H);
  assert.deepEqual(early, { start: range.start, end: Date.parse("2026-11-10T10:00:00Z") });
});

test("fitWindow: no data is the whole range; one reading is an hour around it, inside the range", () => {
  const range = { start: Date.parse("2026-11-10T05:00:00Z"), end: Date.parse("2026-11-12T05:00:00Z") };
  assert.deepEqual(fitWindow(range, null, null, 600, H), range);
  const one = Date.parse("2026-11-11T12:00:00Z");
  const w = fitWindow(range, one, one, 600, H);
  assert.equal(w.end - w.start, H);
  assert.ok(w.start <= one && one + 600e3 <= w.end);
  // At the very start of the range: the hour starts there, not before it
  const atStart = fitWindow(range, range.start, range.start, 600, H);
  assert.deepEqual(atStart, { start: range.start, end: range.start + H });
  // At the very end
  const lastSlot = range.end - 600e3;
  assert.deepEqual(fitWindow(range, lastSlot, lastSlot, 600, H), { start: range.end - H, end: range.end });
  // A range shorter than the minimum: the whole range
  const short = { start: range.start, end: range.start + 30 * 60e3 };
  assert.deepEqual(fitWindow(short, short.start, short.start, 600, H), short);
});

test("fitWindow: daily buckets on the days the clocks change end at the next local midnight", () => {
  // Nov 1 2026 is 25 hours long in Toronto: a daily bucket starting at its midnight ends 25 h later
  const range = { start: Date.parse("2026-10-25T04:00:00Z"), end: Date.parse("2026-11-08T05:00:00Z") };
  const nov1 = Date.parse("2026-11-01T04:00:00Z");
  assert.deepEqual(fitWindow(range, nov1, nov1, 86400, H), { start: nov1, end: nov1 + 25 * H });
  // Mar 8 2026 is 23 hours long
  const spring = { start: Date.parse("2026-03-01T05:00:00Z"), end: Date.parse("2026-03-15T04:00:00Z") };
  const mar8 = Date.parse("2026-03-08T05:00:00Z");
  assert.deepEqual(fitWindow(spring, mar8, mar8, 86400, H), { start: mar8, end: mar8 + 23 * H });
});

test("controller: opens on where the data is, keeps the navigator's extent, and stops fitting once the user moves", async () => {
  // Readings only from 9:00 to 17:00 on the second day of a two-day range
  const from = Date.parse("2026-10-21T13:00:00Z"), to = Date.parse("2026-10-21T21:00:00Z");
  const fetchTiles = (req) => Promise.resolve(req.keys.map((k) => {
    const [g, st, m] = k.split("|");
    const s = fakeSeries(Math.max(from, tileRange(req.first, req.bucketS).start), Math.min(to, tileRange(req.last, req.bucketS).end), req.bucketS);
    return { ...s, group_type: g, station_id: st, measurement_type: m };
  }));
  const loader = new SeriesLoader(fetchTiles);
  const range = { start: Date.parse("2026-10-20T04:00:00Z"), end: Date.parse("2026-10-22T04:00:00Z") };
  const c = new ChartController("weather", [A], range, range, loader, syncFrame, 10);
  c.setAutoFit(true);
  c.activate();
  await sleep(80);
  assert.equal(c.window.start, from);
  assert.equal(c.window.end, to);
  assert.deepEqual(c.extent, range); // the navigator still covers both days
  assert.equal(c.ovB(), 600); // two days at 10-minute readings from the start
  assert.equal(c.overview(A).filter((p) => p.y !== null).length, (to - from) / 600e3);
  // Reset returns to the fitted window; after the user moves, new data doesn't move it
  c.pan(-0.5, "key");
  await sleep(40);
  const moved = c.window;
  c.setExtent({ start: range.start, end: range.end + H });
  await sleep(60);
  assert.equal(c.window.start, moved.start);
  c.reset();
  await sleep(20);
  assert.equal(c.window.start, from);
  c.dispose();
});

test("controller: a range with no readings keeps the whole range and says so", async () => {
  const loader = new SeriesLoader((req) => Promise.resolve(req.keys.map((k) => {
    const [g, st, m] = k.split("|");
    return { group_type: g, station_id: st, measurement_type: m, unit: "m", agg: "mean", t: [], avg: [], min: [], max: [], n: [] };
  })));
  const range = { start: Date.parse("2026-10-20T04:00:00Z"), end: Date.parse("2026-10-22T04:00:00Z") };
  const c = new ChartController("q", [A], range, range, loader, syncFrame, 10);
  c.setAutoFit(true);
  c.activate();
  await sleep(80);
  assert.deepEqual(c.window, range);
  assert.equal(c.snapshot().hasData, false);
  c.dispose();
});

test("controller: the hour moving on updates Reset's window but never moves a window the user moved", async () => {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles);
  const range = { start: Date.parse("2026-11-10T05:00:00Z"), end: Date.parse("2026-11-11T17:00:00Z") };
  const c = new ChartController("w", [A], range, range, loader, syncFrame, 10);
  c.activate();
  await sleep(30);
  await srv.settle();
  // Untouched: the next hour's default is followed
  const later = { start: range.start, end: range.end + H };
  c.setExtent(later);
  c.updateDefault(later);
  await sleep(30);
  assert.deepEqual(c.window, later);
  // Moved by the user: the next hour changes only where Reset goes
  c.zoom(0.25, undefined, "wheel");
  await sleep(30);
  const moved = c.window;
  const evenLater = { start: range.start, end: range.end + 2 * H };
  c.setExtent(evenLater);
  c.updateDefault(evenLater);
  await sleep(30);
  assert.deepEqual(c.window, moved);
  c.reset();
  await sleep(20);
  assert.deepEqual(c.window, evenLater);
  // Other days picked: every chart goes there
  const other = { start: Date.parse("2026-10-01T04:00:00Z"), end: Date.parse("2026-10-03T04:00:00Z") };
  c.setExtent(other);
  c.setDefault(other);
  await sleep(30);
  assert.deepEqual(c.window, other);
  await srv.settle();
  c.dispose();
});

test("fetchFromApi: a passing server error or dropped connection is retried in the same slot; a refusal is not", async () => {
  const saved = globalThis.fetch;
  const waits = [];
  const wait = (ms) => { waits.push(ms); return Promise.resolve(); };
  const reply = (status, body) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  const req = { keys: [A], bucketS: 600, first: 10, last: 10 };
  try {
    let calls = 0;
    globalThis.fetch = async () => (++calls < 3 ? reply(503, { error: "busy" }) : reply(200, { series: [] }));
    assert.deepEqual(await fetchFromApi(req, wait), []);
    assert.equal(calls, 3);
    assert.deepEqual(waits, RETRY_DELAYS_MS);
    calls = 0; waits.length = 0;
    globalThis.fetch = async () => { calls++; return reply(400, { error: "bucket must be one of 600, ..." }); };
    await assert.rejects(fetchFromApi(req, wait), /bucket must be/);
    assert.equal(calls, 1); // a refusal isn't retried
    calls = 0;
    globalThis.fetch = async () => { calls++; return reply(504, { error: "The database took too long" }); };
    await assert.rejects(fetchFromApi(req, wait), /took too long/);
    assert.equal(calls, 1 + RETRY_DELAYS_MS.length);
    calls = 0;
    globalThis.fetch = async () => { calls++; if (calls === 1) throw new TypeError("network"); return reply(200, { series: [] }); };
    assert.deepEqual(await fetchFromApi(req, wait), []);
    assert.equal(calls, 2);
  } finally {
    globalThis.fetch = saved;
  }
});

// ---- one request for the whole range, coarser buckets worked out from it ----

// Raw readings every 10 minutes (with an outage), aggregated straight into buckets of `b` the way /api/series does
function rawReadings(from, to, value) {
  const out = [];
  for (let t = from; t < to; t += 600_000) {
    if (t >= from + 30 * H && t < from + 33 * H) continue; // three hours without readings
    out.push([t, value(t)]);
  }
  return out;
}
const rad = (v) => (v * Math.PI) / 180;
function aggregate(readings, b, agg) {
  const size = b * 1000, groups = new Map();
  for (const [t, v] of readings) {
    const g = Math.floor(toWall(t) / size);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(v);
  }
  const s = { t: [], avg: [], min: [], max: [], n: [] };
  for (const [g, vs] of [...groups].sort((x, y) => x[0] - y[0])) {
    const total = vs.reduce((a, v) => a + v, 0);
    const sin = vs.reduce((a, v) => a + Math.sin(rad(v)), 0), cos = vs.reduce((a, v) => a + Math.cos(rad(v)), 0);
    s.t.push(bucketInstant(g * size)); // as the server labels it: the repeated hour by its second occurrence
    s.avg.push(agg === "sum" ? total : agg === "vector_mean" ? ((Math.atan2(sin, cos) * 180) / Math.PI + 360) % 360 : total / vs.length);
    s.min.push(Math.min(...vs));
    s.max.push(Math.max(...vs));
    s.n.push(vs.length);
  }
  return s;
}

test("coarsen: buckets worked out from finer tiles equal the API's own, across the fall-back day", () => {
  // Readings over 2026-11-01 (25 hours long), varying so that the weights matter
  const from = fromWall(Date.UTC(2026, 9, 25)), to = fromWall(Date.UTC(2026, 10, 8));
  const value = (t) => 5 + Math.sin(t / 7e6) * 3 + ((t / 600_000) % 7);
  for (const agg of ["mean", "sum"]) {
    const readings = rawReadings(from, to, value);
    for (const [fine, coarse] of [[600, 1800], [600, 10800], [1800, 3600], [3600, 86400]]) {
      const per = coarse / fine;
      const i = tileAt(from, coarse);
      const fineTiles = cutIntoTiles(aggregate(readings, fine, agg), i * per, (i + 1) * per - 1, fine);
      const parts = [...fineTiles.keys()].sort((a, b) => a - b).map((j) => fineTiles.get(j));
      const got = coarsen(parts, coarse, agg);
      const want = cutIntoTiles(aggregate(readings, coarse, agg), i, i, coarse).get(i);
      assert.equal(got.t.length, want.t.length, `${agg} ${fine}->${coarse}`);
      for (let j = 0; j < want.t.length; j++) {
        assert.equal(got.t[j], want.t[j]);
        for (const f of ["avg", "min", "max", "n"]) {
          assert.ok(Math.abs(got[f][j] - want[f][j]) < 1e-9, `${agg} ${fine}->${coarse} ${f}[${j}]`);
        }
      }
    }
  }
  // Wind direction: north stays north (350 and 10 degrees give 0, not 180), close to the mean over every reading
  const dirs = rawReadings(from, from + 4 * D, (t) => ((t / 600_000) % 2 ? 350 : 10) + ((t / 3.6e6) % 3));
  const i = tileAt(from, 1800);
  const fineTiles = cutIntoTiles(aggregate(dirs, 600, "vector_mean"), i * 3, i * 3 + 2, 600);
  const got = coarsen([...fineTiles.values()], 1800, "vector_mean");
  const want = cutIntoTiles(aggregate(dirs, 1800, "vector_mean"), i, i, 1800).get(i);
  assert.ok(want.t.length > 0);
  for (let j = 0; j < want.t.length; j++) {
    const d = Math.abs(((got.avg[j] - want.avg[j] + 540) % 360) - 180);
    assert.ok(d < 1, `direction ${got.avg[j]} vs ${want.avg[j]}`);
  }
});

test("bucketInstant: the repeated hour is labelled by its second occurrence, as /api/series does", () => {
  const w = Date.UTC(2026, 10, 1, 1); // 01:00 on the fall-back day
  assert.equal(bucketInstant(w), Date.parse("2026-11-01T06:00:00Z")); // 01:00 EST
  assert.equal(bucketInstant(w + 30 * 60_000), Date.parse("2026-11-01T06:30:00Z"));
  assert.equal(bucketInstant(Date.UTC(2026, 10, 1, 0)), Date.parse("2026-11-01T04:00:00Z")); // 00:00 EDT: only once
  assert.equal(bucketInstant(Date.UTC(2026, 10, 1, 2)), Date.parse("2026-11-01T07:00:00Z"));
});

test("baseBucket: the finest bucket whose whole tiles over the range fit in one request of 8", () => {
  const end = Date.parse("2026-11-12T17:00:00Z");
  const all = { start: Date.parse("2025-05-08T04:00:00Z"), end };
  assert.equal(baseBucket(all), 21600); // all the history: 6 hours, 7 tiles
  assert.equal(tilesFor(all, 21600).length, 7);
  assert.equal(baseBucket({ start: end - 2 * D, end }), 600); // two days: the raw readings
  assert.equal(baseBucket({ start: end - 14 * D, end }), 600);
  assert.equal(baseBucket({ start: end - 90 * D, end }), 3600);
  for (const days of [1, 7, 14, 20, 27, 90, 365, 560]) {
    const r = { start: end - days * D, end }, b = baseBucket(r);
    assert.ok(tilesFor(r, b).length <= MAX_TILES, `${days} d`);
    const finer = LADDER[LADDER.indexOf(b) - 1];
    if (finer) assert.ok(tilesFor(r, finer).length > MAX_TILES, `${days} d: ${finer} would fit`);
  }
});

test("fillTiles: nothing when the window is cached; otherwise one run of up to 8, mostly ahead of a pan", () => {
  const none = () => false;
  assert.deepEqual(fillTiles([10, 11], 0, 100, () => true, 1), []);
  assert.deepEqual(fillTiles([10, 11], 0, 100, none, 1), [8, 9, 10, 11, 12, 13, 14, 15]); // 4 ahead, 2 behind
  assert.deepEqual(fillTiles([10, 11], 0, 100, none, -1), [6, 7, 8, 9, 10, 11, 12, 13]);
  assert.deepEqual(fillTiles([10, 11], 0, 100, none, 0), [7, 8, 9, 10, 11, 12, 13, 14]); // after a zoom: even
  assert.deepEqual(fillTiles([1, 2], 0, 100, none, -1), [0, 1, 2, 3, 4, 5, 6, 7]); // the extent's start: the rest after
  assert.deepEqual(fillTiles([10, 11], 0, 100, (i) => i === 13 || i === 8, 1), [9, 10, 11, 12]); // stops at cached tiles
  assert.deepEqual(fillTiles([10, 11, 12], 10, 12, none, 1), [10, 11, 12]); // the whole extent
});

// A session on one card of three series: each step is [what, action]; returns the requests each step made
async function session(range, steps) {
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles, 3000, 2, 0);
  const c = new ChartController("card", [A, B, C], range, range, loader, syncFrame, 30);
  c.setPlotWidth(600);
  c.activate();
  await sleep(60);
  await srv.settle();
  const first = srv.calls.slice();
  const per = [];
  for (const [what, act] of steps) {
    const n0 = srv.calls.length;
    act(c);
    await sleep(60);
    await srv.settle();
    await sleep(20);
    await srv.settle();
    per.push([what, srv.calls.slice(n0)]);
  }
  c.dispose();
  return { first, per, loader };
}

test("session over all the history: one first request, then at most one per interaction", async () => {
  const range = { start: Date.parse("2025-05-08T04:00:00Z"), end: Date.parse("2026-11-12T17:00:00Z") };
  const zoomIn = (c) => c.zoom(0.5, undefined, "button"), zoomOut = (c) => c.zoom(2, undefined, "button");
  const steps = [
    ...Array.from({ length: 6 }, () => ["zoom in", zoomIn]),
    ...Array.from({ length: 6 }, () => ["pan later", (c) => c.pan(0.5, "button")]),
    ...Array.from({ length: 6 }, () => ["pan earlier", (c) => c.pan(-0.5, "button")]),
    ...Array.from({ length: 3 }, () => ["zoom out", zoomOut]),
    ...Array.from({ length: 3 }, () => ["zoom in", zoomIn]),
    ["reset", (c) => c.reset()],
  ];
  const { first, per, loader } = await session(range, steps);
  assert.equal(first.length, 1);
  assert.equal(first[0].bucketS, 21600);
  assert.equal(first[0].last - first[0].first + 1, 7);
  for (const [what, calls] of per) {
    assert.ok(calls.length <= 1, `${what}: ${calls.length} requests`);
    for (const r of calls) assert.ok(r.last - r.first + 1 <= MAX_TILES);
  }
  const total = 1 + per.reduce((a, [, calls]) => a + calls.length, 0);
  console.log(`[session] all history: ${total} requests for ${steps.length} interactions`);
  assert.ok(total <= 12, `${total} requests for ${steps.length} interactions`);
  assert.ok(loader.stats.peakInFlight <= 2);
  assert.ok(loader.stats.tilesDerived > 0); // the 12-hour and daily tiles came from the 6-hour ones
  for (const [what, calls] of per.filter(([w]) => w === "zoom out" || w === "reset")) assert.equal(calls.length, 0, what);
});

test("session over two weeks: the first request has the raw readings, and nothing is asked for again", async () => {
  const end = Date.parse("2026-11-12T17:00:00Z");
  const range = { start: end - 14 * D, end };
  const steps = [
    ...Array.from({ length: 5 }, () => ["zoom in", (c) => c.zoom(0.5, undefined, "button")]),
    ...Array.from({ length: 4 }, () => ["pan", (c) => c.pan(-0.5, "button")]),
    ["zoom out", (c) => c.zoom(4, undefined, "button")],
  ];
  const { first, per } = await session(range, steps);
  assert.equal(first.length, 1);
  assert.equal(first[0].bucketS, 600);
  for (const [what, calls] of per) assert.equal(calls.length, 0, what);
});

test("a narrow chart over two days draws at once: coarser tiles reaching past the range come from its one request", async () => {
  // At 220 px on a phone two days want 30-minute buckets, whose 7.5-day tile reaches past the one 10-minute tile asked for
  const end = Date.parse("2026-11-12T17:00:00Z");
  const range = { start: end - 2 * D, end };
  const srv = fakeServer();
  const loader = new SeriesLoader(srv.fetchTiles, 3000, 2, 0);
  const c = new ChartController("phone", [A, B], range, range, loader, syncFrame, 30);
  c.setPlotWidth(220);
  c.setDensity(1);
  c.activate();
  await sleep(60);
  await srv.settle();
  await sleep(20);
  assert.equal(srv.calls.length, 1);
  assert.equal(c.ovB(), 1800);
  assert.notEqual(c.snapshot().shownBucket, null);
  assert.ok(c.overview(A).some((p) => p.y !== null));
  assert.ok([...c.lastData.series.get(A)].some((p) => p.y !== null && p.x >= range.start && p.x <= range.end));
  c.dispose();
});
