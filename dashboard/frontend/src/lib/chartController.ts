// One chart's time window and data, independent of every other chart: where it is looking, which bucket that
// needs, which tiles to ask the page's loader for, and the points to draw from whatever tiles are loaded. No React
// or Highcharts here (hooks/useChartWindow.ts and components/graphs/highcharts/MetricChart.tsx wire it up), so
// scripts/seriesLoader.test.mjs can drive it with plain Node.
//
// Moving the window (wheel, drag, slider, keys, buttons) is drawn from the tiles already cached: coarse data where
// nothing finer is loaded yet, so the chart is never blank. Cheap things (the slider's window, the dates above the
// chart) follow every frame; the chart itself is redrawn at a pace set by what its last redraw cost (a redraw takes
// 10-30 ms on a desktop but 100-500 ms on a slow phone, so redrawing every frame there would freeze the page).
//
// What it asks for: first, the whole extent (the picked range) at the finest bucket whose tiles over it fit in one
// request (baseBucket: two weeks or so at 10-minute readings, all of the history at 6 hours). Every coarser bucket is
// worked out from that in the browser (coarsen, in seriesTiles.ts), so zooming out, the navigator line and the opening
// view need nothing more. Only a window that needs finer buckets than the base asks again: its tiles, filled up to
// one request mostly ahead of the way it is moving (fillTiles), so the next steps find them cached.
//
// Requests wait until the window has settled. A gesture (a drag, a pinch, a burst of wheel events; see
// beginGesture) holds them until it ends, however slow its frames are; one that lingers (still going after
// MAX_WAIT_MS, but moving less than a window's width in that time) fetches the window it is on. Single steps (keys,
// buttons) wait DEBOUNCE_MS. So a burst of 80 wheel events or a slider drag ends in one request, not 80. During a
// gesture the chart also keeps the points it has (only moving the axis) unless the window's own tiles arrive: putting
// thousands of points back into the chart on every frame was what made a drag crawl on a slow phone.

import { MIN_RANGE_MS, type Range } from "../utils/chartWindow.ts";
import type { SeriesLoader, SeriesMeta } from "./seriesLoader.ts";
import {
  LADDER, MAX_TILES, baseBucket, bucketFor, coarsestIn, composeSeries, fitWindow, segmentsFor, typicalFor, tilesFor, type ComposedPoint, type Segment,
  POINTS_PER_PX, type TileSeries, type Typical,
} from "./seriesTiles.ts";

export const DEBOUNCE_MS = 250;
export const MAX_WAIT_MS = 1500; // a gesture this long fetches the tiles of the window it is on, without waiting for its end
export const GESTURE_IDLE_MS = 3000; // a gesture with no movement for this long is taken as ended (a lost pointerup)
export const PACE = 1.5; // the next chart redraw starts this many times the last one's cost after it ended
export const AHEAD_SHARE = 2 / 3; // of the tiles a request has room for besides the window's, those ahead of a pan
// The overview (the navigator's line, and what shows before finer tiles arrive) covers the chart's extent, the picked
// range, at the bucket that range needs at the chart's width: a two-day range is at 10-minute readings from the start.
// It is never finer than the chart's base bucket (baseBucket), the one its whole range is loaded at first.
export const overviewBucket = (extent: Range, plotWidthPx: number, pointsPerPx: number): number =>
  Math.max(bucketFor(extent.end - extent.start, plotWidthPx, pointsPerPx), baseBucket(extent));

/** The tiles to ask for to show a window: none when it is cached already; otherwise its tiles, and as many more as
 *  one request has room for (MAX_TILES), most of them ahead of where the window is moving (`dir` > 0: later) or
 *  evenly after a zoom (`dir` 0), so the next pan or zoom finds them cached. The extra tiles stop at the extent
 *  (`lo`..`hi`) and at tiles already cached, so they stay one run. */
export function fillTiles(windowTiles: number[], lo: number, hi: number, have: (i: number) => boolean, dir: number,
  max = MAX_TILES): number[] {
  if (!windowTiles.length || windowTiles.every(have)) return [];
  let first = windowTiles[0], last = windowTiles[windowTiles.length - 1];
  let room = max - (last - first + 1);
  if (room <= 0) return windowTiles;
  const ahead = dir === 0 ? Math.ceil(room / 2) : Math.round(room * AHEAD_SHARE);
  const grow = (later: boolean, n: number) => {
    let added = 0;
    while (added < n) {
      const i = later ? last + 1 : first - 1;
      if (i < lo || i > hi || have(i)) break;
      if (later) last = i; else first = i;
      added++;
    }
    return added;
  };
  const forward = dir >= 0;
  room -= grow(forward, ahead);
  room -= grow(!forward, room);
  grow(forward, room); // what the other side couldn't use
  return Array.from({ length: last - first + 1 }, (_, n) => first + n);
}

export type WindowReason = "wheel" | "drag" | "pinch" | "slider" | "key" | "button" | "select" | "reset" | "link" | "default" | "fit";
// Window changes that aren't the user's: they don't stop the fit to the data, and aren't announced
const AUTOMATIC: ReadonlySet<WindowReason> = new Set(["default", "fit"]);

export interface ChartSnapshot {
  window: Range;
  extent: Range;
  shownBucket: number | null; // the coarsest bucket drawn inside the window (null: nothing drawn yet)
  wantedBucket: number; // the bucket the window needs
  loading: boolean; // something this chart needs is queued or on its way
  error: Error | null;
  hasData: boolean | null; // whether any of the chart's series has a reading at all (null: don't know yet)
  windowEmpty: boolean; // nothing drawn inside the window
  settled: Range; // the window as of the last time it came to rest (for screen readers: announced once, not per frame)
  settledByUser: boolean; // it came to rest after the user moved it (not new picked days, a link or the first load)
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

const now = (): number => (typeof performance !== "undefined" ? performance.now() : Date.now());

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
  private maxWait: ReturnType<typeof setTimeout> | null = null;
  private gestureActive = false;
  private lastMove = 0;
  private density = POINTS_PER_PX;
  private settledWin: Range;
  private settledByUser = false;
  private lastReason: WindowReason = "default";
  private autoFit = false; // open on where the series have readings (fitWindow), until the user moves the window
  private userMoved = false;
  private fitted: Range | null = null;
  private paceQueued = false;
  private needCompose = true; // tiles arrived, or a gesture ended: compose at the next paced redraw
  private lastTick: Range | null = null; // the window at the last max-wait check
  private lastCost = 0;
  private lastEnd = 0;
  private listeners = new Set<() => void>();
  private frameListeners = new Set<(w: Range) => void>();
  private redrawListeners = new Set<(w: Range, gesture: boolean) => void>();
  private gestureListeners = new Set<(active: boolean) => void>();
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
    this.settledWin = this.win;
    this.wantB = bucketFor(this.win.end - this.win.start, this.width, this.density);
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
  /** Called once per frame in which the window moved, with the window: for cheap updates (the slider's window). */
  onFrame(cb: (w: Range) => void): () => void {
    this.frameListeners.add(cb);
    return () => this.frameListeners.delete(cb);
  }
  /** Called when the chart should redraw, at a pace its own cost allows, with the window to show and whether a gesture
   *  is under way (a chart may draw a cheaper preview then, and redraw fully when it ends: the gesture's end schedules
   *  one more call). Data listeners run just before, in the same turn, so one redraw covers both. */
  onRedraw(cb: (w: Range, gesture: boolean) => void): () => void {
    this.redrawListeners.add(cb);
    return () => this.redrawListeners.delete(cb);
  }
  /** Called when a gesture starts (true) and ends (false). */
  onGesture(cb: (active: boolean) => void): () => void {
    this.gestureListeners.add(cb);
    return () => this.gestureListeners.delete(cb);
  }
  /** Called with new points whenever what is drawn changes (tiles arrived, or a finer bucket is wanted); with
   *  setData(..., false) style updates in mind: the redraw comes from onRedraw right after. */
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
    this.lastReason = reason;
    if (!AUTOMATIC.has(reason)) this.userMoved = true;
    this.lastMove = now();
    for (const cb of this.windowListeners) cb(next, reason);
    this.scheduleFrame();
    if (!this.gestureActive) this.requestSoon(true);
  }

  /** A continuous gesture starts (pointer or touch down, the first of a burst of wheel events): no requests until
   *  endGesture, apart from the window's own tiles every MAX_WAIT_MS if it goes on that long. */
  beginGesture(): void {
    if (this.gestureActive) return;
    this.gestureActive = true;
    this.lastMove = now();
    this.lastTick = this.win;
    if (this.debounce) clearTimeout(this.debounce);
    this.debounce = null;
    this.armMaxWait();
    for (const cb of this.gestureListeners) cb(true);
  }

  endGesture(): void {
    if (!this.gestureActive) return;
    this.gestureActive = false;
    if (this.maxWait) clearTimeout(this.maxWait);
    this.maxWait = null;
    this.requestSoon(true);
    this.needCompose = true;
    for (const cb of this.gestureListeners) cb(false);
    this.schedulePaced();
  }

  get inGesture(): boolean { return this.gestureActive; }

  private armMaxWait(): void {
    if (this.maxWait) clearTimeout(this.maxWait);
    this.maxWait = setTimeout(() => {
      this.maxWait = null;
      if (!this.gestureActive) return;
      if (now() - this.lastMove >= GESTURE_IDLE_MS) { // nothing has moved for a while: its end was lost
        this.endGesture();
        return;
      }
      // Lingering (panned under a window's width since the last check): fetch where it is. Sweeping: tiles fetched now
      // would be out of view before they arrived. A zoom still going (the span changed) waits for its end too.
      const was = this.lastTick ?? this.win, span = this.win.end - this.win.start;
      const zooming = Math.abs((was.end - was.start) - span) > span * 0.01;
      if (!zooming && Math.abs((this.win.start + this.win.end) / 2 - (was.start + was.end) / 2) < span) this.request(true);
      this.lastTick = this.win;
      this.armMaxWait();
    }, MAX_WAIT_MS);
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

  /** New default window (other days picked, or a link): the chart goes there (and fits to the data again). */
  setDefault(w: Range): void {
    this.defaultWin = clampWindow(w, this.ext);
    this.userMoved = false;
    this.fitted = null;
    this.setWindow(this.defaultWin, "default");
    this.request();
  }

  /** The default window moved on its own (the hour moved on, so today's picked range ends later): Reset goes there,
   *  but a window the user moved stays where it is (only an untouched one follows, or fits to the data again). */
  updateDefault(w: Range): void {
    this.defaultWin = clampWindow(w, this.ext);
    if (this.userMoved) return;
    if (this.autoFit) {
      this.fitted = null;
      this.fitToData();
    } else {
      this.setWindow(this.defaultWin, "default");
    }
  }

  /** Fetch again what is still filling in (the last hour's tiles, once they are older than the loader's freshness),
   *  as a page left open does every few minutes; nothing while a gesture is under way. */
  refreshLive(): void {
    if (this.gestureActive || this.disposed) return;
    this.request(false, true);
  }

  /** Open on where the series have readings within the extent (once its overview has loaded), until the user moves
   *  the window: a range whose edges have no data never opens on an empty window. Off for a shared link's window. */
  setAutoFit(on: boolean): void {
    if (on === this.autoFit) return;
    this.autoFit = on;
    this.fitted = null;
    this.fitToData();
  }

  // The first and last bucket with a reading, across the series, in the extent's overview, once all of it is loaded
  private dataBounds(): { first: number | null; last: number | null } | null {
    const ovB = this.ovB();
    const need = tilesFor(this.ext, ovB);
    if (!need.length || this.loadedForAll(ovB).filter((i) => need.includes(i)).length < need.length) return null;
    let first: number | null = null, last: number | null = null;
    for (const k of this.keys) {
      for (const i of need) {
        const t = this.loader.tile(k, ovB, i);
        if (!t) continue;
        for (let j = 0; j < t.t.length; j++) {
          if (Number.isNaN(t.avg[j]) || t.t[j] + ovB * 1000 <= this.ext.start || t.t[j] >= this.ext.end) continue;
          if (first === null || t.t[j] < first) first = t.t[j];
          if (last === null || t.t[j] > last) last = t.t[j];
        }
      }
    }
    return { first, last };
  }

  private fitToData(): void {
    if (!this.autoFit || this.userMoved || this.disposed) return;
    const b = this.dataBounds();
    if (!b) return;
    const fit = fitWindow(this.ext, b.first, b.last, this.ovB(), MIN_RANGE_MS);
    if (this.fitted && fit.start === this.fitted.start && fit.end === this.fitted.end) return;
    this.fitted = fit;
    this.defaultWin = clampWindow(fit, this.ext); // Reset comes back here
    this.setWindow(this.defaultWin, "fit");
  }

  setExtent(extent: Range): void {
    if (extent.start === this.ext.start && extent.end === this.ext.end) return;
    this.ext = extent;
    this.fitted = null;
    this.defaultWin = clampWindow(this.defaultWin, extent);
    this.win = clampWindow(this.win, extent);
    this.scheduleFrame();
    this.request(false, true);
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
    if (!this.gestureActive && bucketFor(this.win.end - this.win.start, px, this.density) !== this.wantB) this.requestSoon(false);
  }

  /** Points per pixel of plot width to aim for (about 1 on phones, where every point costs more to draw). */
  setDensity(pointsPerPx: number): void {
    if (!(pointsPerPx > 0) || pointsPerPx === this.density) return;
    this.density = pointsPerPx;
    this.requestSoon(false);
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
    if (this.maxWait) clearTimeout(this.maxWait);
    this.maxWait = null;
    this.gestureActive = false;
    for (const part of ["overview", "window"]) this.loader.release(this.owner(part));
  }

  activate(): void {
    if (!this.disposed) return;
    this.disposed = false;
    this.request();
  }

  /** One series at the overview bucket only, within the extent, for the navigator's line. */
  overview(key: string): ComposedPoint[] {
    const ovB = this.ovB();
    const tiles = [...this.loader.loadedTiles(key, ovB)];
    const pts = composeSeries(segmentsFor([{ bucketS: ovB, tiles }]), (b, i) => this.loader.tile(key, b, i), () => () => null);
    return pts.filter((p) => p.x >= this.ext.start && p.x <= this.ext.end);
  }

  /** The overview's bucket (see overviewBucket). */
  ovB(): number { return overviewBucket(this.ext, this.width, this.density); }

  // ---- loading and composing ----

  private owner(part: string): string { return `${this.id}:${part}`; }

  /** Ask the loader for the chart's whole range at its base bucket (one request, once: every coarser bucket is worked
   *  out from it) and, when the window needs finer buckets than that, its tiles filled up to one request along the
   *  way it moved (fillTiles); with `windowOnly` (the middle of a long gesture), only the latter. */
  request(windowOnly = false, refresh = false): void {
    if (this.disposed) return;
    const w = this.win, span = w.end - w.start;
    this.wantB = bucketFor(span, this.width, this.density);
    const keys = this.keys;
    const near = this.visible ? 0 : 2;
    const base = baseBucket(this.ext);
    if (!windowOnly) this.loader.want(this.owner("overview"), keys, base, tilesFor(this.ext, base), near, () => this.dataChanged(false), true, refresh);
    // Finer than the base: the window's tiles, and more along the way it moved since it last settled
    let tiles: number[] = [];
    if (this.wantB < base) {
      const prev = this.settledWin, b = this.wantB;
      const zoomed = Math.abs((prev.end - prev.start) - span) > span * 0.01;
      const dir = zoomed ? 0 : Math.sign((w.start + w.end) - (prev.start + prev.end));
      const all = tilesFor(this.ext, b);
      tiles = fillTiles(tilesFor(w, b), all[0], all[all.length - 1], (i) => keys.every((k) => this.loader.fresh(k, b, i, refresh)), dir);
    }
    this.loader.want(this.owner("window"), keys, this.wantB, tiles, near, () => this.dataChanged(true), false, refresh);
    if (windowOnly) {
      this.updateSnapshot();
      return;
    }
    this.settledWin = w;
    this.settledByUser = !AUTOMATIC.has(this.lastReason);
    this.dataChanged(true);
  }

  // Tiles arrived. The window's own are drawn at the next paced redraw; others (the history, the tiles around) are
  // left for the end of a gesture, so arriving data doesn't add redraws to a slow drag.
  private dataChanged(forWindow: boolean): void {
    this.fitToData();
    if (forWindow || !this.gestureActive) {
      this.needCompose = true;
      this.schedulePaced();
    }
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
    const finest = bucketFor(span, this.width, this.density);
    const ovB = this.ovB();
    for (let n = LADDER.length - 1; n >= 0; n--) {
      const b = LADDER[n];
      if (b < finest) break;
      const loaded = this.loadedForAll(b);
      const tiles = b === ovB ? loaded : loaded.filter((i) => nearTiles(b).has(i));
      if (tiles.length) levels.push({ bucketS: b, tiles });
    }
    return segmentsFor(levels);
  }

  private compose(): void {
    const segs = this.segments();
    // The tiles in use, and each series' revision: a tile fetched again (the latest hour, filling in) draws anew
    const sig = `${this.ext.start}-${this.ext.end}|${this.keys.map((k) => `${k}#${this.loader.revision(k)}`).join(",")}|${segs.map((g) => `${g.wallStart}-${g.wallEnd}@${g.bucketS}`).join(",")}`;
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
    const owners = ["overview", "window"].map((p) => this.owner(p));
    const error = owners.map((o) => this.loader.error(o)).find(Boolean) ?? null;
    let hasData: boolean | null = null;
    if (this.lastData.series.size) {
      const any = [...this.lastData.series.values()].some((pts) => pts.some((p) => p.y !== null));
      hasData = any ? true : this.loadedForAll(this.ovB()).length >= tilesFor(this.ext, this.ovB()).length ? false : null;
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
      settled: this.settledWin,
      settledByUser: this.settledByUser,
    };
  }

  // React listeners (the toolbar) hear of a new window only outside gestures; during one, onFrame listeners follow it
  private updateSnapshot(): void {
    const next = this.makeSnapshot();
    const s = this.snap;
    if ((s.window === next.window || this.gestureActive) && s.extent === next.extent && s.shownBucket === next.shownBucket
      && s.wantedBucket === next.wantedBucket && s.loading === next.loading && s.error === next.error
      && s.hasData === next.hasData && s.windowEmpty === next.windowEmpty && s.settled === next.settled) return;
    this.snap = next;
    for (const cb of this.listeners) cb();
  }

  // Every frame the window moved in: the cheap listeners, and a paced redraw
  private scheduleFrame(): void {
    if (this.frameQueued) return;
    this.frameQueued = true;
    this.frame(() => {
      this.frameQueued = false;
      if (this.disposed) return;
      for (const cb of this.frameListeners) cb(this.win);
      this.updateSnapshot();
      this.schedulePaced();
    });
  }

  // The chart's redraw: not before PACE times the last one's cost has passed since it ended, so a slow device spends
  // most of its time handling input rather than redrawing (the chart catches up a few times a second instead of
  // freezing).
  private schedulePaced(): void {
    if (this.paceQueued || this.disposed) return;
    this.paceQueued = true;
    const go = () => this.frame(() => this.runPaced());
    const wait = this.lastEnd + this.lastCost * PACE - now();
    if (wait > 4) setTimeout(go, wait);
    else go();
  }

  private runPaced(): void {
    this.paceQueued = false;
    if (this.disposed) return;
    const t = now();
    // Outside a gesture: finer tiles already cached for where the window went, and tiles that arrived. During one:
    // only when the window's own tiles arrived (the axis moves over the points the chart already has).
    if (!this.gestureActive || this.needCompose) {
      this.needCompose = false;
      this.compose();
    }
    for (const cb of this.redrawListeners) cb(this.win, this.gestureActive);
    this.updateSnapshot();
    this.lastEnd = now();
    this.lastCost = this.lastEnd - t;
  }
}
