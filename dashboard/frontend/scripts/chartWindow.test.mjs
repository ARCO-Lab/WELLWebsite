// Unit tests for src/utils/chartWindow.ts, with Node's built-in test runner (no extra packages):
//   npm test   (node --experimental-strip-types --test scripts/chartWindow.test.mjs)

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  zoneOffsetMs, wallToUtc, pickedDaysRange, snapUp, bucketSpanLabel, shortBucket, valueDecimals, typicalCounts,
  isPartial, Lru, MIN_RANGE_MS, clampToNow, daysCovering, dataStart, torontoIso, parseIsoParam, windowFromSearch,
  searchWithWindow, hourStart,
} from "../src/utils/chartWindow.ts";
import { composeSeries, cutIntoTiles, fromWall, segmentsFor, tileAt, toWall } from "../src/lib/seriesTiles.ts";
import {
  measurementColor, seriesType, compassLabel, panelsFor, WEATHER_PANELS, QUALITY_PANELS, seriesNote,
} from "../src/utils/chartStyle.ts";

const H = 3600 * 1000;
const D = 24 * H;

// A bucket start on the local (wall-clock) grid
const snapDown = (ms, bucketS) => fromWall(Math.floor(toWall(ms) / (bucketS * 1000)) * bucketS * 1000);

// One series, as the charts compose it (lib/seriesTiles): cut into tiles, drawn at its bucket, partial buckets judged
// by the series' own usual counts (typicalCounts)
function composePoints(s, bucketS) {
  const arr = (a) => (a ? Array.from(a, (v) => (v === null || v === undefined ? NaN : v)) : Array.from(s.t, () => NaN));
  const full = { t: Array.from(s.t), avg: arr(s.avg), min: arr(s.min), max: arr(s.max), n: arr(s.n) };
  const first = tileAt(full.t[0], bucketS), last = tileAt(full.t[full.t.length - 1], bucketS);
  const tiles = cutIntoTiles(full, first, last, bucketS);
  const typical = typicalCounts(s);
  // A tile more on each side: these test series aren't on the wall-clock grid, so a bucket can straddle a tile edge
  const span = [first - 1, ...tiles.keys(), last + 1];
  return composeSeries(segmentsFor([{ bucketS, tiles: span }]), (b, i) => tiles.get(i), () => typical);
}
const xy = (pts) => pts.map((p) => [p.x, p.y]);

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

test("snapping up follows the local grid, so daily buckets are local days", () => {
  const t = Date.UTC(2026, 3, 5, 15, 7); // 11:07 Toronto
  assert.equal(snapUp(t, 86400), Date.UTC(2026, 3, 6, 4));
  assert.equal(snapUp(t, 600), Date.UTC(2026, 3, 5, 15, 10));
  assert.equal(snapUp(Date.UTC(2026, 3, 5, 15), 600), Date.UTC(2026, 3, 5, 15)); // already on the grid
});

test("gaps longer than 2.5 buckets become a null, shorter ones don't", () => {
  const s = { t: [0, 600_000, 1_200_000, 1_200_000 + 2 * 600_000, 1_200_000 + 6 * 600_000], avg: [1, 2, 3, 4, 5] };
  const pts = xy(composePoints(s, 600));
  assert.equal(pts.filter(([, v]) => v === null).length, 1); // only the 6-bucket gap (a night without power)
  assert.deepEqual(pts[4], [1_200_000 + 2 * 600_000 + 600_000, null]);
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

test("across a clock change, the few days on one side aren't judged by the other side's counts", () => {
  // Oct 28 - Dec 5 2026 at 30-minute buckets: 4 EDT days, then EST from Nov 1. The EDT days' buckets start at
  // other UTC times, too few to have a usual count of their own; their 08:00 bucket (08:20 only, 1 reading) and
  // 18:00 bucket (18:00-18:10, 2) must not be called partial against the 3 a mid-day bucket holds.
  const counts = new Map();
  for (let d = 0; d < 39; d++) {
    for (let m = 8 * 60 + 20; m <= 18 * 60 + 10; m += 10) {
      const b = snapDown(wallToUtc(Date.UTC(2026, 9, 28 + d) + m * 60_000), 1800);
      counts.set(b, (counts.get(b) ?? 0) + 1);
    }
  }
  const sorted = [...counts].sort((x, y) => x[0] - y[0]);
  const s = { t: sorted.map(([b]) => b), avg: sorted.map(() => 1), n: sorted.map(([, c]) => c) };
  const pts = composePoints(s, 1800).filter((p) => p.y !== null);
  assert.equal(pts.filter((p) => p.custom.partial).length, 0);
  const edtMorning = pts.find((p) => p.custom.start === wallToUtc(Date.UTC(2026, 9, 28, 8)));
  assert.deepEqual([edtMorning.custom.n, edtMorning.custom.typical], [1, null]); // too few to judge, so no flag
  const estMorning = pts.find((p) => p.custom.start === wallToUtc(Date.UTC(2026, 10, 10, 8)));
  assert.deepEqual([estMorning.custom.n, estMorning.custom.typical], [1, 1]);
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

// ---- extent, picked days and links ----

test("picked days stop at the next whole hour after now", () => {
  const picked = pickedDaysRange(new Date(2026, 10, 10), new Date(2026, 10, 11)); // Nov 10-11, Toronto
  const now = Date.UTC(2026, 10, 11, 17, 12); // 12:12 EST on Nov 11
  assert.deepEqual(clampToNow(picked, now), { start: picked.start, end: Date.UTC(2026, 10, 11, 18) });
  assert.deepEqual(clampToNow(picked, Date.UTC(2026, 10, 20)), picked); // past days: unchanged
  const today = pickedDaysRange(new Date(2026, 10, 11), new Date(2026, 10, 11));
  assert.equal(clampToNow(today, today.start).end - today.start, MIN_RANGE_MS); // just after midnight: an hour
  assert.equal(hourStart(now), Date.UTC(2026, 10, 11, 17));
  assert.equal(dataStart(), Date.UTC(2025, 4, 8, 4)); // 2025-05-08 00:00 EDT
});

test("the days a window covers", () => {
  const w = { start: Date.UTC(2026, 9, 3, 18), end: Date.UTC(2026, 9, 5, 2) }; // Oct 3 14:00 - Oct 4 22:00 EDT
  const { startDay, endDay } = daysCovering(w);
  assert.deepEqual([startDay.getFullYear(), startDay.getMonth(), startDay.getDate()], [2026, 9, 3]);
  assert.deepEqual([endDay.getFullYear(), endDay.getMonth(), endDay.getDate()], [2026, 9, 4]);
  const whole = pickedDaysRange(new Date(2026, 9, 3), new Date(2026, 9, 4));
  assert.equal(daysCovering(whole).endDay.getDate(), 4); // ends at midnight: that day isn't included
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
  // Other parameters keep their commas, written the way utils/selectionLink writes them
  assert.equal(searchWithWindow("?groups=gauges,weather&from=a&to=b", null), "?groups=gauges,weather");
  assert.equal(searchWithWindow("?groups=gauges%2Cweather", null), "?groups=gauges,weather");
  const back = searchWithWindow("", { start: Date.UTC(2026, 6, 1, 4), end: Date.UTC(2026, 6, 2, 4) });
  assert.deepEqual(windowFromSearch(back, now), { start: Date.UTC(2026, 6, 1, 4), end: Date.UTC(2026, 6, 2, 4) });
});

test("chart style: a fixed colour per measurement, how each kind is drawn, and the charts per card", () => {
  assert.notEqual(measurementColor("Air Temperature"), measurementColor("Dew Point"));
  assert.notEqual(measurementColor("Air Temperature"), measurementColor("Soil Temperature"));
  assert.equal(measurementColor("Something new"), measurementColor("Something new")); // unknown: stable too
  assert.equal(seriesType("sum"), "area"); // stepped
  assert.equal(seriesType("vector_mean"), "scatter");
  assert.equal(seriesType("mean"), "line");
  assert.equal(compassLabel(225), "225° (SW)");
  assert.equal(compassLabel(-10), "350° (N)");
  const weather = panelsFor(WEATHER_PANELS, ["Wind Speed", "Rain", "Air Temperature", "Gust Speed", "Soil Temperature", "All Weather"]);
  assert.deepEqual(weather.map((p) => p.id), ["temperature", "rain", "wind-speed"]); // stable test ids, fixed order
  assert.deepEqual(weather[0].measurements, ["Air Temperature", "Soil Temperature"]);
  assert.deepEqual(weather[2].measurements, ["Wind Speed", "Gust Speed"]);
  const extras = panelsFor(WEATHER_PANELS, ["Humidity", "Wind-Gust", "Wind Gust"], new Set(["Humidity", "Wind-Gust", "Wind Gust"]));
  assert.deepEqual(extras.map((p) => p.id), ["extra-humidity", "extra-wind-gust", "extra-wind-gust-2"]); // no collisions
  const quality = panelsFor(QUALITY_PANELS, ["ODO", "TSS", "Conductivity"]);
  assert.deepEqual(quality.map((p) => p.id), ["conductivity", "oxygen"]);
  assert.equal(seriesNote("Quality", "TSS").hidden, true);
  assert.match(seriesNote("Quality", "ODO").note, /Jun 2026/);
  assert.equal(seriesNote("Weather", "Rain"), undefined);
});

// ---- one chart per card: its series and axes ----
import { cardSeries } from "../src/utils/cardSeries.ts";

test("cardSeries: every selected measurement in one chart, one y-axis per unit, in a fixed order", () => {
  const { series, axes } = cardSeries("Weather", [{ id: "22051538", name: "Weather station" }],
    ["Wind Speed", "Rainfall", "Rain", "Air Temperature", "Gust Speed", "Soil Temperature", "All Weather"]);
  assert.deepEqual(series.map((s) => s.measurement), ["Air Temperature", "Soil Temperature", "Rain", "Wind Speed", "Gust Speed"]);
  assert.deepEqual(axes.map((a) => a.unit), ["°C", "mm", "m/s"]);
  assert.deepEqual(series.map((s) => s.axis), [0, 0, 1, 2, 2]);
  assert.equal(series[0].key, "Weather|22051538|Air Temperature");
  assert.equal(series[0].name, "Air Temperature (°C)"); // what the e2e tooltip check looks for
  assert.equal(series.find((s) => s.measurement === "Rain").agg, "sum");
});

test("cardSeries: loggers share one chart, a colour per logger, temperature dashed, two axes", () => {
  const { series, axes } = cardSeries("Logger", [{ id: "2577531", name: "Logger 1" }, { id: "2577534", name: "Logger 4" }],
    ["Water Temperature", "Water Surface Elevation", "All Loggers"]);
  assert.deepEqual(series.map((s) => s.name), [
    "Logger 1 · Water Surface Elevation (m asl)", "Logger 1 · Water Temperature (°C)",
    "Logger 4 · Water Surface Elevation (m asl)", "Logger 4 · Water Temperature (°C)",
  ]);
  assert.equal(series[0].color, series[1].color);
  assert.notEqual(series[0].color, series[2].color);
  assert.deepEqual(series.map((s) => s.dash ?? ""), ["", "ShortDash", "", "ShortDash"]);
  assert.deepEqual(axes, [{ unit: "m asl", measurements: ["Water Surface Elevation"] }, { unit: "°C", measurements: ["Water Temperature"] }]);
});

test("cardSeries: faulty sensors are noted, TSS starts hidden; nothing selected is nothing drawn", () => {
  const { series } = cardSeries("Quality", [{ id: "4501", name: "Water quality" }], ["TSS", "ODO", "Conductivity"]);
  assert.deepEqual(series.map((s) => s.measurement), ["Conductivity", "ODO", "TSS"]);
  assert.equal(series[2].hidden, true);
  assert.match(series[1].note, /Jun 2026/);
  assert.deepEqual(cardSeries("Logger", [{ id: "1", name: "Logger 1" }], []).series, []);
});

test("guarded: a callback's exception is reported, not thrown; otherwise it runs as usual", async () => {
  const { guarded } = await import("../src/lib/guarded.ts");
  const seen = [];
  const ok = guarded((a, b) => seen.push(a + b), (e) => seen.push(`reported ${e.message}`));
  ok(1, 2);
  const bad = guarded(() => { throw new Error("boom"); }, (e) => seen.push(`reported ${e.message}`));
  assert.doesNotThrow(() => bad());
  assert.deepEqual(seen, [3, "reported boom"]);
});
