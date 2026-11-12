// Pure helpers for the zoomable sensor charts: the bucket sizes /api/series uses, time-zone-aware snapping to its
// bucket grid, the window maths behind the zoom buttons, joining coarse "overview" data with finer "detail" data,
// breaking lines across outages, and a small LRU cache. No React or browser APIs here, so
// scripts/chartWindow.test.mjs can test it with plain Node.

// Times are epoch milliseconds (UTC); ranges are [start, end), end exclusive.
export type Range = { start: number; end: number };

export const TIME_ZONE = "America/Toronto";

// The bucket sizes /api/series picks from (seconds), smallest first, and the points per series it aims for.
// Keep in step with LADDER and MAX_POINTS in dashboard/backend/app/api/routes/series.py.
export const LADDER = [600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600];
export const MAX_POINTS = 2000;

export const MIN_RANGE_MS = 3600 * 1000; // the narrowest zoom: one hour
export const GAP_FACTOR = 2.5; // points further apart than this many buckets are drawn as a break in the line
export const PAD_FRACTION = 0.5; // detail is loaded for the window plus half its width on each side

/** The bucket /api/series will use for a span: the smallest that keeps it near MAX_POINTS points. */
export function pickBucket(spanMs: number): number {
  for (const bucket of LADDER) {
    if (spanMs / 1000 / bucket <= MAX_POINTS) return bucket;
  }
  return LADDER[LADDER.length - 1];
}

// One formatter, reused: creating Intl formatters is slow.
let partsFormatter: Intl.DateTimeFormat | null = null;

/** How far Toronto's wall clock is ahead of UTC at an instant, in ms (negative: -4 or -5 hours). */
export function zoneOffsetMs(utcMs: number): number {
  partsFormatter ??= new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE, hourCycle: "h23",
    year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric",
  });
  const p: Record<string, number> = {};
  for (const { type, value } of partsFormatter.formatToParts(new Date(utcMs))) p[type] = Number(value);
  const wallAsUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return wallAsUtc - Math.floor(utcMs / 1000) * 1000;
}

/** A Toronto wall-clock time, written as if it were UTC (e.g. Date.UTC(y, m, d)), to the real instant. */
export function wallToUtc(wallMs: number): number {
  const guess = wallMs - zoneOffsetMs(wallMs);
  return wallMs - zoneOffsetMs(guess);
}

/** The picked days as a range: Toronto midnight of the first day to Toronto midnight after the last.
 *  The date pickers hand over Dates whose own calendar day is the day picked. */
export function pickedDaysRange(startDay: Date, endDay: Date): Range {
  return {
    start: wallToUtc(Date.UTC(startDay.getFullYear(), startDay.getMonth(), startDay.getDate())),
    end: wallToUtc(Date.UTC(endDay.getFullYear(), endDay.getMonth(), endDay.getDate() + 1)),
  };
}

// /api/series buckets follow Toronto wall-clock time (daily buckets are local days), so snap in wall-clock time.
export function snapDown(ms: number, bucketS: number): number {
  const b = bucketS * 1000;
  return wallToUtc(Math.floor((ms + zoneOffsetMs(ms)) / b) * b);
}

export function snapUp(ms: number, bucketS: number): number {
  const b = bucketS * 1000;
  return wallToUtc(Math.ceil((ms + zoneOffsetMs(ms)) / b) * b);
}

/** A window the charts can show: at least MIN_RANGE_MS wide and inside the picked range; null when it covers
 *  the whole picked range (the unzoomed view). */
export function normalizeWindow(w: Range, picked: Range): Range | null {
  const total = picked.end - picked.start;
  let width = Math.max(w.end - w.start, MIN_RANGE_MS);
  if (width >= total) return null;
  const center = (w.start + w.end) / 2;
  let start = Math.round(center - width / 2);
  start = Math.min(Math.max(start, picked.start), picked.end - width);
  width = Math.round(width);
  return { start, end: start + width };
}

/** ◀ / ▶: move the window by half its width (direction -1 or 1), stopping at the picked range's edges. */
export function shiftWindow(w: Range, picked: Range, direction: -1 | 1): Range | null {
  const step = ((w.end - w.start) / 2) * direction;
  return normalizeWindow({ start: w.start + step, end: w.end + step }, picked);
}

/** Zoom out: double the window around its centre. */
export function zoomOutWindow(w: Range, picked: Range): Range | null {
  const half = w.end - w.start;
  const center = (w.start + w.end) / 2;
  return normalizeWindow({ start: center - half, end: center + half }, picked);
}

/** Zoom in (for keyboards and the button): halve the window around its centre. */
export function zoomInWindow(w: Range, picked: Range): Range | null {
  const quarter = (w.end - w.start) / 4;
  const center = (w.start + w.end) / 2;
  return normalizeWindow({ start: center - quarter, end: center + quarter }, picked);
}

/** The range to load detail for: the window plus padding on each side, inside the picked range, snapped outward to
 *  the grid of `gridS` (the overview's bucket, so detail and overview meet on bucket edges and cache keys repeat). */
export function detailRange(w: Range, picked: Range, gridS: number): Range {
  const pad = (w.end - w.start) * PAD_FRACTION;
  return {
    start: Math.max(picked.start, snapDown(w.start - pad, gridS)),
    end: Math.min(picked.end, snapUp(w.end + pad, gridS)),
  };
}

// Arrays, or typed arrays (as cached: NaN stands for a missing value there). min, max and n (readings per bucket)
// are optional: an older backend sends no n, and Wind Direction has no min/max.
export interface SeriesValues {
  t: ArrayLike<number>;
  avg: ArrayLike<number | null>;
  min?: ArrayLike<number | null>;
  max?: ArrayLike<number | null>;
  n?: ArrayLike<number | null>;
}

// What a plotted point stands for, kept on it for the tooltip and the markers.
export interface PointInfo {
  start: number; // the bucket's start (epoch ms); the point itself is drawn at its middle
  bucketS: number; // the bucket's size
  lo: number | null; // smallest and largest reading in it (null when unknown or meaningless)
  hi: number | null;
  n: number | null; // readings in it (null when the backend doesn't say)
  typical: number | null; // readings this series usually has in a bucket at this time of day (see typicalCounts)
  partial: boolean; // fewer than half the typical readings
  isolated: boolean; // no neighbour on either side, so a line alone wouldn't show it
}

export interface ChartPoint {
  x: number;
  y: number | null;
  custom?: PointInfo;
}

const RAW_S = LADDER[0]; // every sensor reports every 10 minutes

const num = (a: ArrayLike<number | null> | undefined, i: number): number | null => {
  const v = a?.[i];
  return v === undefined || v === null || Number.isNaN(v) ? null : v;
};

// Medians of fewer buckets than this are too noisy to judge a bucket by.
export const MIN_PHASE_SAMPLE = 5;
export const MIN_SERIES_SAMPLE = 8;
const DAY_MS = 86_400_000;

const median = (v: number[]): number | null => {
  if (!v.length) return null;
  v.sort((a, b) => a - b);
  return v[Math.floor(v.length / 2)];
};

/** How many readings a series usually has per bucket, learned from its own counts rather than assumed from a
 *  10-minute cadence: the water quality sonde, for one, is silent every night, so a full day holds about 55
 *  readings, not 144, and the 18:00–24:00 bucket only one or two. The median count of the buckets that start at
 *  the same time of day (UTC, so the two daylight-saving halves of the year are separate times). A time of day
 *  with too few buckets gets null (no judgement): around a clock change, the few days on one side have their own
 *  UTC times, and the series-wide median would call the sonde's normal mornings and evenings partial. Only a short
 *  series, where every time of day is sparse, falls back to the median of all its buckets; null when there are too
 *  few even for that. */
export function typicalCounts(s: SeriesValues | undefined): (t: number) => number | null {
  const byPhase = new Map<number, number[]>();
  const all: number[] = [];
  for (let i = 0; s?.n && i < s.t.length; i++) {
    const n = num(s.n, i);
    if (n === null || n <= 0) continue;
    const phase = ((s.t[i] % DAY_MS) + DAY_MS) % DAY_MS;
    let list = byPhase.get(phase);
    if (!list) byPhase.set(phase, (list = []));
    list.push(n);
    all.push(n);
  }
  const overall = all.length >= MIN_SERIES_SAMPLE ? median(all) : null;
  const phases = new Map<number, number | null>();
  const anyDense = [...byPhase.values()].some((list) => list.length >= MIN_PHASE_SAMPLE);
  const sparse = anyDense ? null : overall;
  for (const [phase, list] of byPhase) phases.set(phase, list.length >= MIN_PHASE_SAMPLE ? median(list) : sparse);
  return (t) => phases.get(((t % DAY_MS) + DAY_MS) % DAY_MS) ?? sparse;
}

/** Whether a bucket holding `n` readings has fewer than half of what is `typical` for it (an outage starts or ends
 *  in it). Raw readings, and buckets whose count or typical count is unknown, are never partial. */
export function isPartial(n: number | null, bucketS: number, typical: number | null): boolean {
  return n !== null && typical !== null && bucketS > RAW_S && n < typical / 2;
}

/** Points for one series: overview points outside the detail range and detail points inside it, so a pan or
 *  zoom never shows a gap while detail loads. An averaged bucket is drawn at its middle (it stands for the whole
 *  span, not its first moment); raw readings at their own time. A null is inserted wherever two neighbours are
 *  more than GAP_FACTOR buckets apart (using the coarser of their two buckets), so lines break across outages
 *  instead of drawing straight through them. */
export function composePoints(
  overview: SeriesValues | undefined,
  overviewBucketS: number,
  detail?: { values: SeriesValues | undefined; bucketS: number; range: Range },
): ChartPoint[] {
  type Raw = { t: number; v: number | null; bS: number; lo: number | null; hi: number | null; n: number | null;
    typical: number | null };
  const pts: Raw[] = [];
  const ob = overviewBucketS * 1000;
  const push = (s: SeriesValues | undefined, bS: number, keep: (t: number) => boolean) => {
    if (!s) return;
    const typical = typicalCounts(s); // from all of this response's buckets, not only the ones kept
    for (let i = 0; i < s.t.length; i++) if (keep(s.t[i])) {
      pts.push({ t: s.t[i], v: num(s.avg, i), bS, lo: num(s.min, i), hi: num(s.max, i), n: num(s.n, i),
        typical: typical(s.t[i]) });
    }
  };
  if (!detail) {
    push(overview, overviewBucketS, () => true);
  } else {
    const { start, end } = detail.range;
    push(overview, overviewBucketS, (t) => t + ob <= start);
    push(detail.values, detail.bucketS, (t) => t >= start && t < end);
    push(overview, overviewBucketS, (t) => t >= end);
  }

  const out: ChartPoint[] = [];
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const b = p.bS * 1000;
    if (i > 0) {
      const prev = pts[i - 1];
      if (p.t - prev.t > GAP_FACTOR * Math.max(prev.bS * 1000, b)) out.push({ x: prev.t + prev.bS * 1000, y: null });
    }
    out.push({
      x: p.bS > RAW_S ? p.t + b / 2 : p.t,
      y: p.v,
      custom: { start: p.t, bucketS: p.bS, lo: p.lo, hi: p.hi, n: p.n, typical: p.typical,
        partial: isPartial(p.n, p.bS, p.typical), isolated: false },
    });
  }
  for (let i = 0; i < out.length; i++) {
    const c = out[i].custom;
    if (c && out[i].y !== null) c.isolated = (out[i - 1]?.y ?? null) === null && (out[i + 1]?.y ?? null) === null;
  }
  return out;
}

/** "10-min", "6-h", "daily": a bucket size, short, for tooltips. */
export function shortBucket(bucketS: number): string {
  if (bucketS === 86400) return "daily";
  return bucketS >= 3600 ? `${bucketS / 3600}-h` : `${Math.round(bucketS / 60)}-min`;
}

const two = (v: number) => String(v).padStart(2, "0");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** The time a point covers, in Toronto time: "Oct 1, 2026 18:00–24:00" for a 6-hour bucket, "Oct 1, 2026" for a
 *  day, "Oct 1, 2026 18:10" for a raw reading. Buckets follow the local wall clock, so the end is start + size
 *  on that clock (a bucket ending at midnight ends at 24:00, not 00:00 the next day). */
export function bucketSpanLabel(startMs: number, bucketS: number): string {
  const wall = new Date(startMs + zoneOffsetMs(startMs));
  const day = `${MONTHS[wall.getUTCMonth()]} ${wall.getUTCDate()}, ${wall.getUTCFullYear()}`;
  if (bucketS >= 86400) return day;
  const hm = (m: number) => `${two(Math.floor(m / 60))}:${two(m % 60)}`;
  const from = wall.getUTCHours() * 60 + wall.getUTCMinutes();
  if (bucketS <= RAW_S) return `${day} ${hm(from)}`;
  return `${day} ${hm(from)}–${hm(from + bucketS / 60)}`;
}

// Decimals a value is shown with, by unit: water levels in m asl to the millimetre, the rest to what the
// sensors actually resolve.
const DECIMALS: Record<string, number> = {
  "m": 3, "m asl": 3, "m³/m³": 3, "g/L": 3, "PPT": 2, "ppt": 2, "mg/L": 2,
  "°C": 1, "%": 1, "mbar": 1, "mm": 1, "m/s": 1, "NTU": 1, "uS/cm": 0, "µS/cm": 0, "W/m²": 0, "°": 0,
};
export function valueDecimals(unit: string): number {
  return DECIMALS[unit] ?? 2;
}

/** "10-minute readings", "1-hour averages", "daily averages"… for a bucket size. */
export function bucketLabel(bucketS: number, aggregated: boolean): string {
  let size: string;
  if (bucketS >= 86400 && bucketS % 86400 === 0) size = bucketS === 86400 ? "daily" : `${bucketS / 86400}-day`;
  else if (bucketS >= 3600) size = `${bucketS / 3600}-hour`;
  else size = `${Math.round(bucketS / 60)}-minute`;
  return `${size} ${aggregated ? "averages" : "readings"}`;
}

/** The badge on a chart showing averaged data, e.g. "12-hour averages" (plus a note when rain is shown: it is a
 *  total per bucket); null at full resolution. */
export function resolutionBadge(bucketS: number | null, aggregated: boolean, hasTotals: boolean): string | null {
  if (!bucketS || !aggregated) return null;
  return `${bucketLabel(bucketS, true)}${hasTotals ? " (rain: totals)" : ""}`;
}

/** A least-recently-used cache: get() refreshes an entry, set() drops the oldest beyond `max`. */
export class Lru<V> {
  max: number;
  map = new Map<string, V>();

  constructor(max: number) {
    this.max = max;
  }

  get(key: string): V | undefined {
    const value = this.map.get(key);
    if (value !== undefined) {
      this.map.delete(key);
      this.map.set(key, value);
    }
    return value;
  }

  set(key: string, value: V): void {
    this.map.delete(key);
    this.map.set(key, value);
    while (this.map.size > this.max) this.map.delete(this.map.keys().next().value as string);
  }

  get size(): number {
    return this.map.size;
  }
}

// ---- The data's extent, the picked days and shareable links ----

// The first day with sensor data (as in components/filters/Calendar.tsx): charts can't go back further.
export const DATA_START_DAY = { year: 2025, month: 4, day: 8 }; // 2025-05-08, month counted from 0
export const dataStart = (): number =>
  wallToUtc(Date.UTC(DATA_START_DAY.year, DATA_START_DAY.month, DATA_START_DAY.day));

/** The start of the hour an instant falls in. Read from effects and handlers, never while rendering. */
export const hourStart = (now: number): number => Math.floor(now / 3_600_000) * 3_600_000;

/** The picked days, ending no later than the next whole hour after now: today's remaining hours have no data
 *  yet, and showing them left the right half of a chart empty. */
export function clampToNow(r: Range, now: number): Range {
  const end = Math.min(r.end, Math.max(r.start + MIN_RANGE_MS, snapUp(now, 3600)));
  return { start: r.start, end };
}

/** The calendar days a range covers, in Toronto, as the date pickers hold them (Dates whose own calendar day is
 *  the day). */
export function daysCovering(w: Range): { startDay: Date; endDay: Date } {
  const day = (ms: number) => {
    const wall = new Date(ms + zoneOffsetMs(ms));
    return new Date(wall.getUTCFullYear(), wall.getUTCMonth(), wall.getUTCDate());
  };
  return { startDay: day(w.start), endDay: day(Math.max(w.start, w.end - 1)) };
}

/** An instant as ISO 8601 in Toronto time, to the minute: "2026-11-10T14:20-05:00". */
export function torontoIso(ms: number): string {
  const off = zoneOffsetMs(ms);
  const wall = new Date(Math.floor((ms + off) / 60000) * 60000);
  const sign = off < 0 ? "-" : "+";
  const abs = Math.abs(off) / 60000;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${wall.toISOString().slice(0, 16)}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

// A date, optionally a time, optionally an offset; nothing else (Date.parse accepts far too much, and reads a
// date-only string as UTC).
const ISO = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,3})?)?(Z|[+-]\d{2}:?\d{2})?)?$/;

/** One ?from= / ?to= value to an instant; a value without an offset is Toronto wall-clock time. NaN if invalid. */
export function parseIsoParam(value: string): number {
  // A "+" typed into a link arrives as a space ("…T14:20 05:30"); read it back as the "+" it was.
  const m = ISO.exec(value.trim().replace(/ (\d{2}:?\d{2})$/, "+$1"));
  if (!m) return NaN;
  const [, y, mo, d, h = "0", mi = "0", s = "0", zone] = m;
  const wall = Date.UTC(+y, +mo - 1, +d, +h, +mi, +s);
  const check = new Date(wall); // reject 2026-02-31 and 25:00, which Date.UTC would roll over
  if (check.getUTCMonth() !== +mo - 1 || check.getUTCDate() !== +d || +h > 23 || +mi > 59 || +s > 59) return NaN;
  if (!zone) return wallToUtc(wall);
  if (zone === "Z") return wall;
  const digits = zone.replace(":", "");
  const offsetMin = (zone[0] === "-" ? -1 : 1) * (+digits.slice(1, 3) * 60 + +digits.slice(3, 5));
  return wall - offsetMin * 60000;
}

/** The window a link asks for (?from=&to=), or null when it is missing or makes no sense: unparseable, end not
 *  after start, or nothing left (at least an hour) after clamping it to the days with data. */
export function windowFromSearch(search: string, now: number): Range | null {
  const q = new URLSearchParams(search);
  const from = q.get("from"), to = q.get("to");
  if (!from || !to) return null;
  let start = parseIsoParam(from), end = parseIsoParam(to);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  start = Math.max(start, dataStart());
  end = Math.min(end, snapUp(now, 3600));
  return end - start >= MIN_RANGE_MS ? { start, end } : null;
}

/** A link's query string with ?from=&to= set to the window (null: removed), other parameters kept. */
export function searchWithWindow(search: string, w: Range | null): string {
  const q = new URLSearchParams(search);
  if (w) {
    q.set("from", torontoIso(w.start));
    q.set("to", torontoIso(w.end));
  } else {
    q.delete("from");
    q.delete("to");
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}
