// One chart's time window and data, independent of every other chart: where it is looking, which bucket that
// needs, which tiles to ask the page's loader for, and the points to draw from whatever tiles are loaded. No React
// or Highcharts here (hooks/useChartWindow.ts and components/graphs/highcharts/MetricChart.tsx wire it up), so
// scripts/seriesLoader.test.mjs can drive it with plain Node.
//
// Moving the window (wheel, drag, slider, keys, buttons) is drawn at once, at most once per frame, from the tiles
// already cached: coarse data where nothing finer is loaded yet, so the chart is never blank. Only once the window
// has stayed put for DEBOUNCE_MS does the chart ask for the tiles its new window needs, so a burst of 80 wheel
// events or a slider drag ends in one request, not 80.

import { MIN_RANGE_MS, type Range } from "../utils/chartWindow.ts";
import type { SeriesLoader, SeriesMeta } from "./seriesLoader.ts";
import {
  LADDER, bucketFor, coarsestIn, composeSeries, segmentsFor, typicalFor, tilesFor, type ComposedPoint, type Segment,
  type TileSeries, type Typical,
} from "./seriesTiles.ts";

export const DEBOUNCE_MS = 250;
export const PAD_FRACTION = 0.5; // tiles for half a window on each side are fetched too, after the window's own
// The bucket every chart's overview (the slider's line, and what shows before finer tiles arrive) is drawn at: the
// whole history in two daily tiles, the same for every chart, so all charts share them.
export const OVERVIEW_BUCKET = LADDER[LADDER.length - 1];

export type WindowReason = "wheel" | "drag" | "pinch" | "slider" | "key" | "button" | "select" | "reset" | "link" | "default";

export interface ChartSnapshot {
  window: Range;
  extent: Range;
  shownBucket: number | null; // the coarsest bucket drawn inside the window (null: nothing drawn yet)
  wantedBucket: number; // the bucket the window needs
  loading: boolean; // something this chart needs is queued or on its way
  error: Error | null;
  hasData: boolean | null; // whether any of the chart's series has a reading at all (null: don't know yet)
  windowEmpty: boolean; // nothing drawn inside the window
}

/** Whether any point with a value lies in [w.start, w.end); points are in time order. */
export function hasPointIn(points: ComposedPoint[], w: Range): boolean {
  let lo = 0, hi = points.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid].x < w.start) lo = mid + 1;
    else hi = mid;
  }
  for (let i = lo; i < points.length && points[i].x < w.end; i++) if (points[i].y !== null) return true;
  return false;
}

export interface ComposedData {
  series: Map<string, ComposedPoint[]>;
  shownBucket: number | null;
}

type Scheduler = (cb: () => void) => void;
const defaultFrame: Scheduler = (cb) => {
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => cb());
  else setTimeout(cb, 16);
};

export function clampWindow(w: Range, extent: Range, keep: "center" | "start" | "end" = "center"): Range {
  const total = extent.end - extent.start;
  const span = Math.min(Math.max(w.end - w.start, MIN_RANGE_MS), total);
  let start = keep === "start" ? w.start : keep === "end" ? w.end - span : (w.start + w.end) / 2 - span / 2;
  start = Math.min(Math.max(start, extent.start), extent.end - span);
  return { start: Math.round(start), end: Math.round(start + span) };
}

export class ChartController {
  private win: Range;
  private ext: Range;
  private defaultWin: Range;
  private keys: string[];
  private width = 600;
  private visible = true;
  private wantB: number;
  private composedSig = "";
  private snap: ChartSnapshot;
  private frameQueued = false;
  private debounce: ReturnType<typeof setTimeout> | null = null;
  private listeners = new Set<() => void>();
  private frameListeners = new Set<(w: Range) => void>();
  private dataListeners = new Set<(d: ComposedData) => void>();
  private windowListeners = new Set<(w: Range, reason: WindowReason) => void>();
  private typicals = new Map<string, { size: number; value: Typical }>();
  private disposed = true; // until activate()
  lastData: ComposedData = { series: new Map(), shownBucket: null };

  readonly id: string;
  private loader: SeriesLoader;
  private frame: Scheduler;
  private debounceMs: number;

  constructor(
    id: string,
    keys: string[],
    defaultWindow: Range,
    extent: Range,
    loader: SeriesLoader,
    frame: Scheduler = defaultFrame,
    debounceMs = DEBOUNCE_MS,
  ) {
    this.id = id;
    this.loader = loader;
    this.frame = frame;
    this.debounceMs = debounceMs;
    this.keys = [...keys];
    this.ext = extent;
    this.defaultWin = clampWindow(defaultWindow, extent);
    this.win = this.defaultWin;
    this.wantB = bucketFor(this.win.end - this.win.start, this.width);
    this.snap = this.makeSnapshot();
  }

  // ---- reading ----

  get window(): Range { return this.win; }
  get extent(): Range { return this.ext; }
  get defaultWindow(): Range { return this.defaultWin; }
  get seriesKeys(): readonly string[] { return this.keys; }
  meta(key: string): SeriesMeta | undefined { return this.loader.seriesMeta(key); }
  snapshot = (): ChartSnapshot => this.snap;

  subscribe = (cb: () => void): (() => void) => {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  };
  /** Called once per frame in which the window moved, with the window to draw. */
  onFrame(cb: (w: Range) => void): () => void {
    this.frameListeners.add(cb);
    return () => this.frameListeners.delete(cb);
  }
  /** Called with new points whenever what is drawn changes (tiles arrived, or a finer bucket is wanted). */
  onData(cb: (d: ComposedData) => void): () => void {
    this.dataListeners.add(cb);
    return () => this.dataListeners.delete(cb);
  }
  /** Called on every window change, with its reason (for linking charts). */
  onWindow(cb: (w: Range, reason: WindowReason) => void): () => void {
    this.windowListeners.add(cb);
    return () => this.windowListeners.delete(cb);
  }

  // ---- changing ----

  /** Show this window (kept inside the data's extent and at least MIN_RANGE_MS wide). */
  setWindow(w: Range, reason: WindowReason, keep: "center" | "start" | "end" = "center"): void {
    const next = clampWindow(w, this.ext, keep);
    if (next.start === this.win.start && next.end === this.win.end) return;
    this.win = next;
    for (const cb of this.windowListeners) cb(next, reason);
    this.scheduleFrame();
    this.requestSoon(true);
  }

  // Ask once things have been still for debounceMs. `restart`: a new change, so wait again from now.
  private requestSoon(restart: boolean): void {
    if (this.debounce && !restart) return;
    if (this.debounce) clearTimeout(this.debounce);
    this.debounce = setTimeout(() => { this.debounce = null; this.request(); }, this.debounceMs);
  }

  reset(): void { this.setWindow(this.defaultWin, "reset"); }

  /** Zoom by `factor` (under 1: in) keeping the instant `at` where it is on screen. */
  zoom(factor: number, at = (this.win.start + this.win.end) / 2, reason: WindowReason = "button"): void {
    const span = this.win.end - this.win.start;
    const total = this.ext.end - this.ext.start;
    const next = Math.min(Math.max(span * factor, MIN_RANGE_MS), total);
    const f = next / span;
    this.setWindow({ start: at - (at - this.win.start) * f, end: at + (this.win.end - at) * f }, reason);
  }

  /** Move by a share of the window's width (negative: earlier). */
  pan(share: number, reason: WindowReason = "button"): void {
    const d = (this.win.end - this.win.start) * share;
    this.setWindow({ start: this.win.start + d, end: this.win.end + d }, reason);
  }

  /** New default window (other days picked, or a link): the chart goes there. */
  setDefault(w: Range): void {
    this.defaultWin = clampWindow(w, this.ext);
    this.setWindow(this.defaultWin, "default");
    this.request();
  }

  setExtent(extent: Range): void {
    if (extent.start === this.ext.start && extent.end === this.ext.end) return;
    this.ext = extent;
    this.defaultWin = clampWindow(this.defaultWin, extent);
    this.win = clampWindow(this.win, extent);
    this.scheduleFrame();
    this.request();
  }

  setKeys(keys: string[]): void {
    if (keys.join("\n") === this.keys.join("\n")) return;
    this.keys = [...keys];
    this.composedSig = "";
    this.request();
  }

  /** The plot's width (it changes a little whenever the axis labels do): asks again only if that changes the bucket,
   *  and only once things are still, so a redraw in the middle of a zoom never sends a request. */
  setPlotWidth(px: number): void {
    if (!(px > 0) || px === this.width) return;
    this.width = px;
    if (bucketFor(this.win.end - this.win.start, px) !== this.wantB) this.requestSoon(false);
  }

  /** Charts off screen ask for their tiles after the ones on screen. */
  setVisible(visible: boolean): void {
    if (visible === this.visible) return;
    this.visible = visible;
    this.requestSoon(false);
  }

  /** Ask again for whatever is missing (after an error). */
  retry(): void { this.request(); }

  /** The chart went away: its queued requests are dropped (the ones sent finish and are cached). Listeners stay;
   *  each removes itself. activate() brings it back (React mounts effects twice in development). */
  dispose(): void {
    this.disposed = true;
    if (this.debounce) clearTimeout(this.debounce);
    this.debounce = null;
    for (const part of ["overview", "window", "around"]) this.loader.release(this.owner(part));
  }

  activate(): void {
    if (!this.disposed) return;
    this.disposed = false;
    this.request();
  }

  /** One series at the overview bucket only (the whole history, daily), for the slider's line. */
  overview(key: string): ComposedPoint[] {
    const tiles = [...this.loader.loadedTiles(key, OVERVIEW_BUCKET)];
    return composeSeries(segmentsFor([{ bucketS: OVERVIEW_BUCKET, tiles }]), (b, i) => this.loader.tile(key, b, i), () => () => null);
  }

  // ---- loading and composing ----

  private owner(part: string): string { return `${this.id}:${part}`; }

  /** Ask the loader for the overview tiles, the window's tiles and (after those) the tiles around it. */
  request(): void {
    if (this.disposed) return;
    const w = this.win, span = w.end - w.start;
    this.wantB = bucketFor(span, this.width);
    const changed = () => this.dataChanged();
    const keys = this.keys;
    const near = this.visible ? 0 : 2;
    this.loader.want(this.owner("overview"), keys, OVERVIEW_BUCKET, tilesFor(this.ext, OVERVIEW_BUCKET), near + 1, changed);
    const fine = this.wantB < OVERVIEW_BUCKET;
    const inWindow = fine ? tilesFor(w, this.wantB) : [];
    this.loader.want(this.owner("window"), keys, this.wantB, inWindow, near, changed);
    const around = fine
      ? tilesFor({ start: Math.max(this.ext.start, w.start - span * PAD_FRACTION), end: Math.min(this.ext.end, w.end + span * PAD_FRACTION) }, this.wantB)
          .filter((i) => !inWindow.includes(i))
      : [];
    this.loader.want(this.owner("around"), keys, this.wantB, around, near + 2, changed);
    this.dataChanged();
  }

  private dataChanged(): void {
    this.compose();
    this.updateSnapshot();
  }

  // The tiles of a bucket loaded for every one of this chart's series
  private loadedForAll(bucketS: number): number[] {
    if (!this.keys.length) return [];
    let common: number[] | null = null;
    for (const k of this.keys) {
      const set = this.loader.loadedTiles(k, bucketS);
      common = common === null ? [...set] : common.filter((i) => set.has(i));
    }
    return common ?? [];
  }

  // The series' usual counts at a bucket size, from all its loaded tiles; worked out again when tiles arrive
  private typical(key: string, bucketS: number): Typical {
    const tiles = this.loader.loadedTiles(key, bucketS);
    const id = `${key}#${bucketS}`;
    const had = this.typicals.get(id);
    if (had && had.size === tiles.size) return had.value;
    const list: TileSeries[] = [];
    for (const i of tiles) {
      const t = this.loader.tile(key, bucketS, i);
      if (t) list.push(t);
    }
    const value = typicalFor(list);
    this.typicals.set(id, { size: tiles.size, value });
    return value;
  }

  /** The segments to draw: the overview everywhere, then each finer bucket down to the wanted one where its tiles
   *  are loaded near the window (finer wins). */
  segments(): Segment[] {
    const w = this.win, span = w.end - w.start;
    const near = { start: w.start - 2 * span, end: w.end + 2 * span };
    const nearTiles = (b: number) => new Set(tilesFor(near, b));
    const levels: { bucketS: number; tiles: number[] }[] = [];
    // Down to what the window needs now, not what was last asked for: finer tiles already cached are drawn while
    // the window is still moving, before it settles and asks.
    const finest = bucketFor(span, this.width);
    for (let n = LADDER.length - 1; n >= 0; n--) {
      const b = LADDER[n];
      if (b < finest) break;
      const loaded = this.loadedForAll(b);
      const tiles = b === OVERVIEW_BUCKET ? loaded : loaded.filter((i) => nearTiles(b).has(i));
      if (tiles.length) levels.push({ bucketS: b, tiles });
    }
    return segmentsFor(levels);
  }

  private compose(): void {
    const segs = this.segments();
    const sig = `${this.keys.join(",")}|${segs.map((g) => `${g.wallStart}-${g.wallEnd}@${g.bucketS}`).join(",")}`;
    if (sig === this.composedSig) return;
    this.composedSig = sig;
    const series = new Map<string, ComposedPoint[]>();
    for (const k of this.keys) {
      series.set(k, composeSeries(segs, (b, i) => this.loader.tile(k, b, i), (b) => this.typical(k, b)));
    }
    this.lastData = { series, shownBucket: coarsestIn(segs, this.win) };
    for (const cb of this.dataListeners) cb(this.lastData);
  }

  private makeSnapshot(): ChartSnapshot {
    const owners = ["overview", "window", "around"].map((p) => this.owner(p));
    const error = owners.map((o) => this.loader.error(o)).find(Boolean) ?? null;
    let hasData: boolean | null = null;
    if (this.lastData.series.size) {
      const any = [...this.lastData.series.values()].some((pts) => pts.some((p) => p.y !== null));
      hasData = any ? true : this.loadedForAll(OVERVIEW_BUCKET).length >= tilesFor(this.ext, OVERVIEW_BUCKET).length ? false : null;
    }
    return {
      window: this.win,
      extent: this.ext,
      shownBucket: coarsestIn(this.segments(), this.win),
      wantedBucket: this.wantB,
      // The window's own tiles; the overview (the whole history, for the slider) loads in the background
      loading: this.loader.waiting(owners[1]) || (this.lastData.shownBucket === null && this.loader.waiting(owners[0])),
      error,
      hasData,
      windowEmpty: ![...this.lastData.series.values()].some((pts) => hasPointIn(pts, this.win)),
    };
  }

  private updateSnapshot(): void {
    const next = this.makeSnapshot();
    const s = this.snap;
    if (s.window === next.window && s.extent === next.extent && s.shownBucket === next.shownBucket
      && s.wantedBucket === next.wantedBucket && s.loading === next.loading && s.error === next.error
      && s.hasData === next.hasData && s.windowEmpty === next.windowEmpty) return;
    this.snap = next;
    for (const cb of this.listeners) cb();
  }

  private scheduleFrame(): void {
    if (this.frameQueued) return;
    this.frameQueued = true;
    this.frame(() => {
      this.frameQueued = false;
      if (this.disposed) return;
      for (const cb of this.frameListeners) cb(this.win);
      this.compose(); // finer tiles already cached for where the window went
      this.updateSnapshot();
    });
  }
}
