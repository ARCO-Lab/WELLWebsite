// A read-only check of the charts' arithmetic against a running dashboard (two GET requests):
//   node --experimental-strip-types scripts/liveSeriesCheck.mjs [https://welldash.mcmaster.ca] [days ago]
// It asks /api/series for one 15-day tile at hourly buckets, and for the same 15 days at 10-minute buckets (six
// tiles), then works the hourly buckets out from the 10-minute ones the way the charts do (coarsen, in
// src/lib/seriesTiles.ts) and compares them with the server's own. The server rounds values to 4 decimals, so means
// may differ by up to 0.0001 and hourly rain totals (six rounded 10-minute totals) by up to 0.0004; minimums,
// maximums and counts must match exactly; wind direction (a mean of directions) must be within two degrees.

import { coarsen, cutIntoTiles, seriesKey, tileAt, tileQuery } from "../src/lib/seriesTiles.ts";

const base = (process.argv[2] ?? "https://welldash.mcmaster.ca").replace(/\/$/, "");
const daysAgo = Number(process.argv[3] ?? 20);
const SERIES = [
  "Weather|22051538|Air Temperature",
  "Weather|22051538|Rain",
  "Weather|22051538|Wind Direction",
  "Logger|2577531|Water Temperature",
];
const HOUR = 3600, TEN = 600, PER = HOUR / TEN; // six 10-minute tiles in one hourly tile

const tile = tileAt(Date.now() - daysAgo * 86400_000, HOUR);
async function get(bucketS, first, last) {
  const { start, end } = tileQuery(first, last, bucketS);
  const q = new URLSearchParams({ start, end, bucket: String(bucketS) });
  for (const s of SERIES) q.append("series", s);
  const res = await fetch(`${base}/api/series?${q}`, { headers: { "User-Agent": "series-check" } });
  if (!res.ok) throw new Error(`${res.status} for bucket=${bucketS}: ${(await res.text()).slice(0, 200)}`);
  const body = await res.json();
  return body.series ?? body;
}

const hourly = await get(HOUR, tile, tile);
const fine = await get(TEN, tile * PER, tile * PER + PER - 1);
let failures = 0;
for (const key of SERIES) {
  const want = hourly.find((s) => seriesKey(s) === key);
  const got10 = fine.find((s) => seriesKey(s) === key);
  if (!want || !got10) { console.log(`${key}: no readings in this tile`); continue; }
  const parts = [...cutIntoTiles(got10, tile * PER, tile * PER + PER - 1, TEN).entries()].sort((a, b) => a[0] - b[0]).map(([, t]) => t);
  const got = coarsen(parts, HOUR, want.agg ?? "mean");
  const wantTile = cutIntoTiles(want, tile, tile, HOUR).get(tile);
  const direction = want.agg === "vector_mean";
  let worst = 0, bad = 0;
  if (got.t.length !== wantTile.t.length) { bad++; if (process.env.SHOW) console.log("   buckets", got.t.length, wantTile.t.length); }
  for (let j = 0; j < Math.min(got.t.length, wantTile.t.length); j++) {
    if (got.t[j] !== wantTile.t[j]) { bad++; if (process.env.SHOW) console.log("   t", new Date(got.t[j]).toISOString(), new Date(wantTile.t[j]).toISOString()); continue; }
    for (const f of ["avg", "min", "max", "n"]) {
      const a = got[f][j], b = wantTile[f][j];
      if (Number.isNaN(a) && Number.isNaN(b)) continue;
      let d = Math.abs(a - b);
      if (direction && f === "avg") d = Math.abs(((a - b + 540) % 360) - 180);
      if (f === "avg") worst = Math.max(worst, d);
      const tolerance = f !== "avg" ? 1e-9 : direction ? 2 : want.agg === "sum" ? 4e-4 : 1e-4;
      if (d > tolerance) { bad++; if (process.env.SHOW) console.log("  ", f, new Date(wantTile.t[j]).toISOString(), "browser", a, "server", b); }
    }
  }
  failures += bad;
  console.log(`${key} (${want.agg ?? "mean"}): ${wantTile.t.length} hourly buckets, ${bad} differing values, largest mean difference ${worst.toPrecision(3)}`);
}
console.log(failures ? `FAILED: ${failures} values differ` : "OK: the hourly buckets worked out in the browser match the server's");
process.exit(failures ? 1 : 0);
