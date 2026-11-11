// Fixed tiles of chart data, and how a chart's points are put together from them. No React or browser APIs here,
// so scripts/seriesLoader.test.mjs can test it with plain Node.
//
// Every chart asks /api/series for its own series at a bucket it picks from its window and its width (bucketFor).
// Instead of asking for exactly its window (a new request for every small pan or zoom), it asks for fixed tiles:
// TILE_BUCKETS buckets of one size, starting at multiples of the tile's length on Toronto's wall clock (the clock
// /api/series buckets by). The same window always needs the same tiles, so they can be cached and shared by every
// chart on the page, and a pan only needs the tiles it uncovers. Tiles are counted on the wall clock, so on the
// days the clocks change a tile is an hour longer or shorter in real time, but tiles never gap or overlap.
//
// Times are epoch milliseconds (UTC) unless named "wall": a Toronto wall-clock time written as if it were UTC
// (Date.UTC(y, m, d, h)), which is how bucket and tile edges are counted.

import { LADDER, isPartial, typicalCounts, zoneOffsetMs, type PointInfo, type Range } from "../utils/chartWindow.ts";

export { LADDER };
export const RAW_S = LADDER[0]; // every sensor reports every 10 minutes
export const TILE_BUCKETS = 360;
export const POINTS_PER_PX = 1.5; // about this many buckets per pixel of plot width: detail without waste
export const GAP_FACTOR = 2.5; // neighbours further apart than this many buckets are drawn with a break between

// Toronto's offset changes only on the hour, so it is cached per hour (formatting a date is slow, and charts convert
// thousands of times while they compose).
const offsets = new Map<number, number>();
export function offsetAt(ms: number): number {
  const hour = Math.floor(ms / 3_600_000);
  let off = offsets.get(hour);
  if (off === undefined) {
    if (offsets.size > 100_000) offsets.clear();
    off = zoneOffsetMs(hour * 3_600_000);
    offsets.set(hour, off);
  }
  return off;
}

export const toWall = (ms: number): number => ms + offsetAt(ms);

/** A wall-clock time to the real instant; one that happens twice (the hour repeated in November) as its first
 *  occurrence. (Tile edges are always at 00:00 or 12:00, so they never fall in an hour the clocks skip or repeat.) */
export function fromWall(wall: number): number {
  const guess = wall - offsetAt(wall);
  const utc = wall - offsetAt(guess);
  return toWall(utc - 3_600_000) === wall ? utc - 3_600_000 : utc;
}

/** The bucket for a chart showing `spanMs` on a plot `plotWidthPx` wide: the smallest on the ladder that gives
 *  about POINTS_PER_PX points per pixel or fewer (at least 150 points, at most 3,000). */
export function bucketFor(spanMs: number, plotWidthPx: number): number {
  const target = Math.min(3000, Math.max(150, (plotWidthPx || 600) * POINTS_PER_PX));
  for (const b of LADDER) if (spanMs / 1000 / b <= target) return b;
  return LADDER[LADDER.length - 1];
}

export const tileSpanMs = (bucketS: number): number => TILE_BUCKETS * bucketS * 1000;

/** The tile of `bucketS` buckets an instant falls in. */
export const tileAt = (ms: number, bucketS: number): number => Math.floor(toWall(ms) / tileSpanMs(bucketS));

/** A tile's start and end: wall-clock (exact multiples of the tile length) and real instants. */
export function tileRange(index: number, bucketS: number): { wallStart: number; wallEnd: number; start: number; end: number } {
  const span = tileSpanMs(bucketS);
  const wallStart = index * span, wallEnd = (index + 1) * span;
  return { wallStart, wallEnd, start: fromWall(wallStart), end: fromWall(wallEnd) };
}

/** The tiles a range needs, first to last. */
export function tilesFor(r: Range, bucketS: number): number[] {
  if (!(r.end > r.start)) return [];
  const out: number[] = [];
  for (let i = tileAt(r.start, bucketS), last = tileAt(r.end - 1, bucketS); i <= last; i++) out.push(i);
  return out;
}

const pad = (n: number) => String(n).padStart(2, "0");
/** A wall-clock time as /api/series reads one without an offset: "2026-11-01T00:00:00". */
export function wallIso(wall: number): string {
  const d = new Date(wall);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

/** The start and end to ask /api/series for, for tiles first..last: wall-clock times, so they are exact whatever
 *  the clocks did. The API's end is inclusive and rounded down to a 10-minute mark, so the end is a second before
 *  the next tile: the next tile's first reading isn't included. */
export function tileQuery(first: number, last: number, bucketS: number): { start: string; end: string } {
  return { start: wallIso(tileRange(first, bucketS).wallStart), end: wallIso(tileRange(last, bucketS).wallEnd - 1000) };
}

// ---- One tile of one series, as cached ----

export interface TileSeries {
  t: Float64Array; // bucket starts (epoch ms)
  avg: Float64Array; // NaN: no value
  min: Float64Array;
  max: Float64Array;
  n: Float64Array; // readings in each bucket; NaN when the backend doesn't say
}

export interface ApiSeries {
  group_type: string;
  station_id: string | number;
  measurement_type: string;
  unit: string;
  agg?: "mean" | "sum" | "vector_mean";
  t: number[];
  avg: (number | null)[];
  min: (number | null)[];
  max: (number | null)[];
  n?: number[];
}

/** "Logger|2577531|Water Temperature": one series, as charts and the series= filter name it. */
export const seriesKey = (s: Pick<ApiSeries, "group_type" | "station_id" | "measurement_type">): string =>
  `${s.group_type}|${s.station_id}|${s.measurement_type}`;

const nan = (v: number | null | undefined) => (v === null || v === undefined ? NaN : v);

/** One response series cut into the tiles first..last (each gets its buckets, maybe none). A series sent in two
 *  units (an old alias) is one series to the charts: callers merge by key before cutting. */
export function cutIntoTiles(s: Pick<ApiSeries, "t" | "avg" | "min" | "max" | "n">, first: number, last: number,
  bucketS: number): Map<number, TileSeries> {
  const span = tileSpanMs(bucketS);
  const idx = new Map<number, number[]>();
  for (let i = first; i <= last; i++) idx.set(i, []);
  for (let j = 0; j < s.t.length; j++) idx.get(Math.floor(toWall(s.t[j]) / span))?.push(j);
  const out = new Map<number, TileSeries>();
  for (const [i, js] of idx) {
    out.set(i, {
      t: Float64Array.from(js, (j) => s.t[j]),
      avg: Float64Array.from(js, (j) => nan(s.avg[j])),
      min: Float64Array.from(js, (j) => nan(s.min?.[j])),
      max: Float64Array.from(js, (j) => nan(s.max?.[j])),
      n: Float64Array.from(js, (j) => nan(s.n?.[j])),
    });
  }
  return out;
}

// ---- Composing a chart's points from the tiles that are loaded ----

/** Where each bucket size is drawn: wall-clock spans, each at one size. Coarse tiles cover everything that is
 *  loaded; finer tiles that are loaded replace them where they are (finer wins). */
export interface Segment { wallStart: number; wallEnd: number; bucketS: number }

/** The segments for one chart: `levels` are the sizes it may draw, coarsest first, each with the tiles of it that
 *  are loaded (for all of the chart's series). Adjacent segments of one size are merged. */
export function segmentsFor(levels: { bucketS: number; tiles: number[] }[]): Segment[] {
  let segs: Segment[] = [];
  for (const { bucketS, tiles } of levels) {
    const span = tileSpanMs(bucketS);
    for (const i of [...tiles].sort((a, b) => a - b)) {
      const s = i * span, e = (i + 1) * span;
      const next: Segment[] = [];
      for (const g of segs) { // cut out [s, e)
        if (g.wallEnd <= s || g.wallStart >= e) next.push(g);
        else {
          if (g.wallStart < s) next.push({ ...g, wallEnd: s });
          if (g.wallEnd > e) next.push({ ...g, wallStart: e });
        }
      }
      next.push({ wallStart: s, wallEnd: e, bucketS });
      segs = next.sort((a, b) => a.wallStart - b.wallStart);
    }
  }
  const merged: Segment[] = [];
  for (const g of segs) {
    const last = merged[merged.length - 1];
    if (last && last.bucketS === g.bucketS && last.wallEnd === g.wallStart) last.wallEnd = g.wallEnd;
    else merged.push({ ...g });
  }
  return merged;
}

export interface ComposedPoint { x: number; y: number | null; custom?: PointInfo }

export type Typical = (t: number) => number | null;

/** How many readings a series usually has per bucket of one size, at each time of day (utils/chartWindow
 *  typicalCounts: per series, since the water quality sonde, for one, is silent every night). Learned from every
 *  loaded tile of the series at that size together, not tile by tile, so partial markers don't change as tiles
 *  arrive. */
export function typicalFor(tiles: Iterable<TileSeries>): Typical {
  const t: number[] = [], n: number[] = [];
  for (const tile of tiles) {
    for (let j = 0; j < tile.t.length; j++) {
      t.push(tile.t[j]);
      n.push(tile.n[j]);
    }
  }
  return typicalCounts({ t, avg: n, n });
}

/** One series' points from the segments: in each segment, the buckets of its size that lie wholly inside it (a coarse
 *  bucket cut by a finer tile is left to the finer one). `tile(bucketS, index)` gives a loaded tile of this series
 *  (undefined: not loaded, so no points there). Averaged buckets are drawn at their middle, raw readings at their
 *  time; a null is inserted wherever neighbours are more than GAP_FACTOR buckets apart, so lines break across
 *  outages. `typical` gives the series' usual counts per size, for the partial markers. */
export function composeSeries(
  segments: Segment[],
  tile: (bucketS: number, index: number) => TileSeries | undefined,
  typical: (bucketS: number) => Typical,
): ComposedPoint[] {
  const pts: { t: number; v: number; lo: number; hi: number; n: number; b: number }[] = [];
  for (const seg of segments) {
    const b = seg.bucketS, bm = b * 1000, span = tileSpanMs(b);
    for (let i = Math.floor(seg.wallStart / span); i * span < seg.wallEnd; i++) {
      const tl = tile(b, i);
      if (!tl) continue;
      for (let j = 0; j < tl.t.length; j++) {
        const w = toWall(tl.t[j]);
        if (w < seg.wallStart || w + bm > seg.wallEnd) continue;
        pts.push({ t: tl.t[j], v: tl.avg[j], lo: tl.min[j], hi: tl.max[j], n: tl.n[j], b });
      }
    }
  }
  const out: ComposedPoint[] = [];
  const v = (x: number) => (Number.isNaN(x) ? null : x);
  const typicalBy = new Map<number, Typical>();
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const bm = p.b * 1000;
    if (i > 0) {
      const prev = pts[i - 1];
      if (p.t - prev.t > GAP_FACTOR * Math.max(prev.b * 1000, bm)) out.push({ x: prev.t + prev.b * 1000, y: null });
    }
    if (!typicalBy.has(p.b)) typicalBy.set(p.b, typical(p.b));
    const usual = typicalBy.get(p.b)!(p.t);
    out.push({
      x: p.b > RAW_S ? p.t + bm / 2 : p.t,
      y: v(p.v),
      custom: {
        start: p.t, bucketS: p.b, lo: v(p.lo), hi: v(p.hi), n: v(p.n), typical: usual,
        partial: isPartial(v(p.n), p.b, usual), isolated: false,
      },
    });
  }
  for (let i = 0; i < out.length; i++) {
    const c = out[i].custom;
    if (c && out[i].y !== null) c.isolated = (out[i - 1]?.y ?? null) === null && (out[i + 1]?.y ?? null) === null;
  }
  return out;
}

/** The coarsest bucket drawn inside a window: what the chart's badge claims ("6-h means"), never finer than shown. */
export function coarsestIn(segments: Segment[], window: Range): number | null {
  const ws = toWall(window.start), we = toWall(window.end);
  let b: number | null = null;
  for (const g of segments) if (g.wallEnd > ws && g.wallStart < we) b = Math.max(b ?? 0, g.bucketS);
  return b;
}
