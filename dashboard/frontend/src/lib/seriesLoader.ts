// The page-wide loader of chart tiles (see seriesTiles.ts): every chart asks it for the tiles it needs, and it
// decides what is actually sent to /api/series. It keeps the number of requests small however fast charts are zoomed
// and panned, and however many charts there are:
// - one cache for the page: a tile of a series loaded once is never asked for again while it is kept (least
//   recently used first out, at most MAX_ENTRIES series-tiles: about 300 tiles of 10 series, ~30 MB);
// - identical tiles are asked for once: a chart that wants a tile already on its way waits for that request;
// - neighbouring missing tiles go in one request (up to MAX_BATCH), and charts that want the same tiles at the same
//   bucket share one request for all their series;
// - at most MAX_IN_FLIGHT requests at a time; the rest wait in a queue, the visible charts' first;
// - wishes are collected for BATCH_MS before anything is sent, so charts that appear together (a card of 8) send
//   one request for their shared tiles instead of the first chart's going out alone;
// - a chart's new wish replaces its old one: queued requests no chart wants any more are dropped before they are
//   sent. A request already sent can't be taken back (the backend runs it anyway), so it finishes and is cached;
// - coarser tiles are worked out from finer ones as they arrive (coarsen), never asked for when the finer ones are
//   here: a chart that loads its whole range at one bucket can zoom out over it with no more requests;
// - a failed request caches nothing, so asking again retries it;
// - a tile that reaches into the last LIVE_WINDOW_MS (still filling in with new readings) is kept only LIVE_TTL_MS
//   as fresh: asked for after that, it is fetched again (the old copy is drawn until the new one arrives).
// No React or browser APIs here (fetching is passed in), so scripts/seriesLoader.test.mjs can test it with Node.

import {
  LADDER, MAX_TILES, coarsen, cutIntoTiles, seriesKey, tileQuery, tileRange, type ApiSeries, type TileSeries,
} from "./seriesTiles.ts";
import { displayUnit } from "../utils/chartStyle.ts";

export const MAX_ENTRIES = 3000;
export const MAX_IN_FLIGHT = 2;
export const MAX_BATCH = MAX_TILES; // tiles per request: the API takes 1 to 8 whole tiles
export const MAX_KEYS = 40; // series per request (the API's MAX_FILTERS)
export const BATCH_MS = 30;
export const LIVE_WINDOW_MS = 3_600_000; // a tile ending later than this before now may still get readings
export const LIVE_TTL_MS = 60_000; // how long such a tile counts as fresh (the API lets browsers reuse it as long)

export interface TileRequest { keys: string[]; bucketS: number; first: number; last: number }
export type FetchTiles = (req: TileRequest) => Promise<ApiSeries[]>;

export interface SeriesMeta { unit: string; agg: "mean" | "sum" | "vector_mean" }

interface Job {
  seq: number;
  keys: Set<string>;
  bucketS: number;
  tiles: number[]; // consecutive
  wanters: Set<string>;
  priority: number; // lower is sooner
  whole: boolean; // a chart's whole range: coarser tiles may be worked out from it where they reach past it (deriveUp)
}

export interface LoaderStats {
  requests: number; // sent to the server
  inFlight: number;
  peakInFlight: number;
  tilesLoaded: number; // series-tiles cached from responses
  tilesDerived: number; // coarser series-tiles worked out from finer cached ones
  hits: number; // series-tiles wanted that were cached already
  deduped: number; // series-tiles wanted that were already on their way
  dropped: number; // queued requests dropped before they were sent
  failed: number;
}

// A series-tile's cache key. The separator can't occur in a series name, so an evicted key splits back into its parts.
const SEP = "\u0000";
const tileKey = (key: string, bucketS: number, index: number) => `${key}${SEP}${bucketS}${SEP}${index}`;

export class SeriesLoader {
  private cache = new Map<string, TileSeries>(); // insertion order = least recently used first
  private liveSince = new Map<string, number>(); // series-tile -> when it was fetched, for tiles still filling in
  private revisions = new Map<string, number>(); // series -> how many times its tiles were stored (charts redraw on a change)
  private loaded = new Map<string, Set<number>>(); // `${key}#${bucketS}` -> cached tile indexes
  private meta = new Map<string, SeriesMeta>();
  private partial = new Set<string>(); // series-tiles worked out from only part of their finer tiles (deriveUp)
  private pending = new Map<string, Job>(); // series-tile -> the job that will load it
  private queue: Job[] = [];
  private sent = new Set<Job>();
  private listeners = new Map<string, () => void>();
  private errors = new Map<string, Error>();
  private seq = 0;
  readonly stats: LoaderStats = { requests: 0, inFlight: 0, peakInFlight: 0, tilesLoaded: 0, tilesDerived: 0, hits: 0, deduped: 0, dropped: 0, failed: 0 };

  private fetchTiles: FetchTiles;
  private maxEntries: number;
  private maxInFlight: number;
  private batchMs: number;
  private batchTimer: ReturnType<typeof setTimeout> | null = null;

  private now: () => number;

  constructor(fetchTiles: FetchTiles, maxEntries = MAX_ENTRIES, maxInFlight = MAX_IN_FLIGHT, batchMs = 0, now: () => number = Date.now) {
    this.now = now;
    this.fetchTiles = fetchTiles;
    this.maxEntries = maxEntries;
    this.maxInFlight = maxInFlight;
    this.batchMs = batchMs;
  }

  /** `owner` (one chart's one need, e.g. "logger-1:detail") wants these series at this bucket for these tiles. This
   *  replaces what it wanted before. `onChange` is called whenever one of its requests ends (loaded or failed). */
  want(owner: string, keys: string[], bucketS: number, indexes: number[], priority: number, onChange: () => void,
    whole = false, refresh = false): void {
    this.forget(owner);
    this.listeners.set(owner, onChange);
    this.errors.delete(owner);
    const missing = new Map<number, Set<string>>();
    for (const i of indexes) {
      for (const k of keys) {
        const tk = tileKey(k, bucketS, i);
        if (this.usable(tk, refresh)) { this.stats.hits++; continue; }
        const job = this.pending.get(tk);
        if (job) {
          this.stats.deduped++;
          job.wanters.add(owner);
          job.priority = Math.min(job.priority, priority);
          continue;
        }
        let set = missing.get(i);
        if (!set) missing.set(i, (set = new Set()));
        set.add(k);
      }
    }
    // Runs of neighbouring tiles, one request each
    const order = [...missing.keys()].sort((a, b) => a - b);
    let run: number[] = [];
    const flush = () => {
      if (!run.length) return;
      const job: Job = { seq: this.seq++, keys: new Set(), bucketS, tiles: run, wanters: new Set([owner]), priority, whole };
      for (const i of run) for (const k of missing.get(i)!) {
        job.keys.add(k);
        this.pending.set(tileKey(k, bucketS, i), job);
      }
      this.queue.push(job);
      run = [];
    };
    for (const i of order) {
      if (run.length && (i !== run[run.length - 1] + 1 || run.length >= MAX_BATCH)) flush();
      run.push(i);
    }
    flush();
    if (!this.batchMs) this.pump();
    else this.batchTimer ??= setTimeout(() => { this.batchTimer = null; this.pump(); }, this.batchMs);
  }

  /** The owner wants nothing any more (its chart went away). */
  release(owner: string): void {
    this.forget(owner);
    this.listeners.delete(owner);
    this.errors.delete(owner);
    for (const job of this.sent) job.wanters.delete(owner);
  }

  /** A cached tile of one series (marked as just used), or undefined. */
  tile(key: string, bucketS: number, index: number): TileSeries | undefined {
    const tk = tileKey(key, bucketS, index);
    const t = this.cache.get(tk);
    if (t) { // most recently used
      this.cache.delete(tk);
      this.cache.set(tk, t);
    }
    return t;
  }

  /** A number that changes whenever a tile of this series is stored (a refetched tile included). */
  revision(key: string): number {
    return this.revisions.get(key) ?? 0;
  }

  has(key: string, bucketS: number, index: number): boolean {
    return this.cache.has(tileKey(key, bucketS, index));
  }

  /** Cached and not due to be fetched again (see LIVE_TTL_MS). */
  fresh(key: string, bucketS: number, index: number, refresh = false): boolean {
    return this.usable(tileKey(key, bucketS, index), refresh);
  }

  /** The tile indexes of a series cached at a bucket. */
  loadedTiles(key: string, bucketS: number): ReadonlySet<number> {
    return this.loaded.get(`${key}#${bucketS}`) ?? new Set();
  }

  seriesMeta(key: string): SeriesMeta | undefined {
    return this.meta.get(key);
  }

  /** Whether one of the owner's requests is queued or on its way. */
  waiting(owner: string): boolean {
    for (const job of this.queue) if (job.wanters.has(owner)) return true;
    for (const job of this.sent) if (job.wanters.has(owner)) return true;
    return false;
  }

  error(owner: string): Error | null {
    return this.errors.get(owner) ?? null;
  }

  get queued(): number {
    return this.queue.length;
  }

  get cachedEntries(): number {
    return this.cache.size;
  }

  // Take the owner off every queued request; drop those nobody wants now.
  private forget(owner: string): void {
    const keep: Job[] = [];
    for (const job of this.queue) {
      job.wanters.delete(owner);
      if (job.wanters.size > 0) keep.push(job);
      else {
        this.stats.dropped++;
        this.unpend(job);
      }
    }
    this.queue = keep;
  }

  private unpend(job: Job): void {
    for (const i of job.tiles) for (const k of job.keys) {
      const tk = tileKey(k, job.bucketS, i);
      if (this.pending.get(tk) === job) this.pending.delete(tk);
    }
  }

  // Cached and complete: a tile worked out from only part of its finer tiles (deriveUp) is drawn until the real one
  // arrives, but asked for when wanted. A tile still filling in counts as stale only for a refresh (the 10-minute
  // timer, a new range), so moving the window never refetches the latest hour on its own.
  private usable(tk: string, refresh: boolean): boolean {
    return this.cache.has(tk) && !this.partial.has(tk) && !(refresh && this.stale(tk));
  }

  // A tile still filling in, fetched more than LIVE_TTL_MS ago
  private stale(tk: string): boolean {
    const at = this.liveSince.get(tk);
    return at !== undefined && this.now() - at > LIVE_TTL_MS;
  }

  private put(key: string, bucketS: number, index: number, tile: TileSeries): void {
    const tk = tileKey(key, bucketS, index);
    // A replaced tile (the latest hour, fetched again) changes the series' revision, so charts using it redraw; a new
    // tile needs no bump (it changes which tiles a chart draws, which charts notice already)
    if (this.cache.has(tk)) this.revisions.set(key, this.revision(key) + 1);
    if (tileRange(index, bucketS).end > this.now() - LIVE_WINDOW_MS) this.liveSince.set(tk, this.now());
    else this.liveSince.delete(tk);
    this.cache.delete(tk);
    this.cache.set(tk, tile);
    const lk = `${key}#${bucketS}`;
    let set = this.loaded.get(lk);
    if (!set) this.loaded.set(lk, (set = new Set()));
    set.add(index);
    while (this.cache.size > this.maxEntries) {
      const oldest = this.cache.keys().next().value as string;
      this.cache.delete(oldest);
      this.liveSince.delete(oldest);
      this.partial.delete(oldest);
      const [k, b, i] = oldest.split(SEP);
      this.loaded.get(`${k}#${b}`)?.delete(Number(i));
    }
  }

  // The coarser tiles that tiles first..last of one series make up, at every bigger bucket on the ladder, wherever all
  // the finer tiles of one are cached (the ones just stored or others): each size divides the next, so a tile of the
  // next size is a whole number of tiles of this one. With `whole` (they cover a chart's whole range), a coarser tile
  // reaching past them is worked out from the part they cover (unless a complete one is cached): its missing part is
  // outside the range, where that chart draws nothing.
  private deriveUp(key: string, bucketS: number, first: number, last: number, whole: boolean): void {
    const agg = this.meta.get(key)?.agg ?? "mean";
    let b = bucketS, lo = first, hi = last;
    for (let n = LADDER.indexOf(b) + 1; n > 0 && n < LADDER.length; n++) {
      const c = LADDER[n], per = c / b;
      const clo = Math.floor(lo / per), chi = Math.floor(hi / per);
      for (let i = clo; i <= chi; i++) {
        const parts: TileSeries[] = [];
        let missing = 0;
        for (let j = i * per; j < (i + 1) * per; j++) {
          const t = this.cache.get(tileKey(key, b, j));
          if (t) parts.push(t);
          else missing++;
        }
        const tk = tileKey(key, c, i);
        if (missing && (!whole || !parts.length || (this.cache.has(tk) && !this.partial.has(tk)))) continue;
        if (missing) this.partial.add(tk);
        else this.partial.delete(tk);
        this.put(key, c, i, coarsen(parts, c, agg));
        this.stats.tilesDerived++;
      }
      b = c; lo = clo; hi = chi;
    }
  }

  private pump(): void {
    while (this.stats.inFlight < this.maxInFlight && this.queue.length) {
      this.queue.sort((a, b) => a.priority - b.priority || a.seq - b.seq);
      const job = this.queue.shift()!;
      this.absorb(job);
      this.send(job);
    }
  }

  // Queued requests for tiles this one covers (or extends to, while it stays one run of at most MAX_BATCH) at the
  // same bucket join it: charts of the same width that want the same tiles share one request.
  private absorb(job: Job): void {
    const keep: Job[] = [];
    for (const other of this.queue) {
      const lo = Math.min(job.tiles[0], other.tiles[0]);
      const hi = Math.max(job.tiles[job.tiles.length - 1], other.tiles[other.tiles.length - 1]);
      const touching = other.tiles[0] <= job.tiles[job.tiles.length - 1] + 1 && other.tiles[other.tiles.length - 1] >= job.tiles[0] - 1;
      const keys = new Set([...job.keys, ...other.keys]);
      if (other.bucketS !== job.bucketS || !touching || hi - lo + 1 > MAX_BATCH || keys.size > MAX_KEYS) {
        keep.push(other);
        continue;
      }
      job.keys = keys;
      job.whole = job.whole && other.whole;
      job.tiles = Array.from({ length: hi - lo + 1 }, (_, n) => lo + n);
      for (const w of other.wanters) job.wanters.add(w);
      for (const [tk, j] of this.pending) if (j === other) this.pending.set(tk, job);
    }
    this.queue = keep;
  }

  private send(job: Job): void {
    const first = job.tiles[0], last = job.tiles[job.tiles.length - 1];
    this.sent.add(job);
    this.stats.requests++;
    this.stats.inFlight++;
    this.stats.peakInFlight = Math.max(this.stats.peakInFlight, this.stats.inFlight);
    this.fetchTiles({ keys: [...job.keys].sort(), bucketS: job.bucketS, first, last })
      .then((series) => {
        // One series per key (an old unit alias can split one in two)
        const byKey = new Map<string, ApiSeries>();
        for (const s of series) {
          const k = seriesKey(s);
          const had = byKey.get(k);
          if (!had) {
            byKey.set(k, s);
            if (!this.meta.has(k)) this.meta.set(k, { unit: displayUnit(s.unit), agg: s.agg ?? "mean" });
          } else {
            const t = [...had.t, ...s.t], avg = [...had.avg, ...s.avg], min = [...had.min, ...s.min];
            const max = [...had.max, ...s.max], n = [...(had.n ?? had.t.map(() => NaN)), ...(s.n ?? s.t.map(() => NaN))];
            const order = t.map((_, j) => j).sort((a, b) => t[a] - t[b]);
            byKey.set(k, {
              ...had, t: order.map((j) => t[j]), avg: order.map((j) => avg[j]), min: order.map((j) => min[j]),
              max: order.map((j) => max[j]), n: order.map((j) => n[j]),
            });
          }
        }
        const empty = { t: [], avg: [], min: [], max: [], n: [] };
        for (const k of job.keys) {
          for (const [i, tile] of cutIntoTiles(byKey.get(k) ?? empty, first, last, job.bucketS)) {
            this.partial.delete(tileKey(k, job.bucketS, i));
            this.put(k, job.bucketS, i, tile);
            this.stats.tilesLoaded++;
          }
          this.deriveUp(k, job.bucketS, first, last, job.whole);
        }
      })
      .catch((err: unknown) => {
        this.stats.failed++;
        const error = err instanceof Error ? err : new Error(String(err));
        // Only refreshing tiles already cached (the latest hour): the charts still draw the old copy, so no error
        // box; the tiles stay stale, and the next wish for them tries again
        const refreshOnly = job.tiles.every((i) => [...job.keys].every((k) => this.cache.has(tileKey(k, job.bucketS, i))));
        if (refreshOnly) console.warn("[charts] refreshing the latest hour failed; trying again later:", error.message);
        else for (const w of job.wanters) this.errors.set(w, error);
      })
      .finally(() => {
        this.unpend(job);
        this.sent.delete(job);
        this.stats.inFlight--;
        for (const w of job.wanters) this.listeners.get(w)?.();
        this.pump();
      });
  }
}

// ---- The page's loader, fetching from /api/series ----

export async function errorFrom(res: Response, what = "chart data"): Promise<Error> {
  // A 404 most likely means the data service is an older version, without this route or its options
  let message = res.status === 404
    ? `Couldn't load ${what} (HTTP 404): the data service may be out of date.`
    : res.status >= 500
      ? `Couldn't load ${what} just now (HTTP ${res.status}). Please try again in a moment.`
      : `Couldn't load ${what} (HTTP ${res.status}).`;
  try {
    const body = await res.json();
    // The backend's own message for a request it refused (4xx) or gave up on (504) says what to change
    if (body?.error && ((res.status >= 400 && res.status < 500 && res.status !== 404) || res.status === 504)) {
      message = String(body.error);
    }
  } catch {
    // keep the generic message
  }
  return new Error(message);
}

export const UNREACHABLE = "Couldn't reach the data service. Please check your connection and try again.";

// Waits before trying a request again: a dropped connection, or a server error that may pass (502, 503: the backend
// restarting or its database busy; 504: a query that ran out of time while the database was loaded)
export const RETRY_DELAYS_MS = [1000, 3000];
const PASSING = new Set([502, 503, 504]);

/** One tile request. Tried up to RETRY_DELAYS_MS.length more times, within the same request slot (so retries never add
 *  to the requests in flight), before the error is reported: one request can serve several charts, so a blip would
 *  otherwise put an error on all of them. A refusal (4xx) is the server's answer and is reported at once. */
export async function fetchFromApi(req: TileRequest, wait: (ms: number) => Promise<void> = (ms) => new Promise((r) => setTimeout(r, ms))): Promise<ApiSeries[]> {
  const { start, end } = tileQuery(req.first, req.last, req.bucketS);
  const params = new URLSearchParams({ start, end, bucket: String(req.bucketS) });
  for (const k of req.keys) params.append("series", k);
  for (let attempt = 0; ; attempt++) {
    let res: Response;
    try {
      res = await fetch(`/api/series?${params.toString()}`);
    } catch {
      if (attempt >= RETRY_DELAYS_MS.length) throw new Error(UNREACHABLE);
      await wait(RETRY_DELAYS_MS[attempt]);
      continue;
    }
    if (res.ok) return ((await res.json()) as { series: ApiSeries[] }).series;
    if (!PASSING.has(res.status) || attempt >= RETRY_DELAYS_MS.length) throw await errorFrom(res);
    await wait(RETRY_DELAYS_MS[attempt]);
  }
}

let pageLoader: SeriesLoader | null = null;
/** The one loader every chart on the page shares. */
export function seriesLoader(): SeriesLoader {
  pageLoader ??= new SeriesLoader(fetchFromApi, MAX_ENTRIES, MAX_IN_FLIGHT, BATCH_MS);
  return pageLoader;
}
