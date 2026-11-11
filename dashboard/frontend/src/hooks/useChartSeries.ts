// This file defines useChartSeries, which loads the sensor charts' data from /api/series, and the context that
// shares it (and the one zoom window all charts follow) with every chart on the page and in the modal.
//
// - Overview: the picked days, for the active groups, in one request; /api/series aggregates it to ~2,000
//   points per series.
// - Detail: while zoomed, once the window has settled for 300 ms, one more request for the window plus half its
//   width on each side, snapped to the overview's bucket grid. Charts draw overview points outside that range
//   and detail points inside it, so data is never blank: coarse first, then sharper in place.
// - One AbortController for all of them: a new request cancels the previous one, and a response that is no longer
//   wanted is ignored. The last 12 responses are cached, so zooming out, Reset and revisits need no request.
// - The picked days end at the next whole hour after now (clampToNow), so today's empty future isn't drawn.
// - showWindow: a window that may reach outside the picked days (the range buttons, a shared link) moves the
//   picked days to cover it, then zooms to it.

import { createContext, startTransition, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  Lru, clampToNow, detailRange, normalizeWindow, pickBucket, pickedDaysRange, planWindow, type Range,
} from "@/utils/chartWindow";

export interface GroupSelection {
  gauges: boolean;
  weather: boolean;
  quality: boolean;
}

export interface ApiSeries {
  group_type: string;
  station_id: string | number;
  measurement_type: string;
  unit: string;
  agg?: "mean" | "sum" | "vector_mean"; // what `avg` holds; rain is a total per bucket
  t: number[]; // bucket starts, epoch ms UTC
  avg: (number | null)[];
  min: (number | null)[];
  max: (number | null)[];
}

export interface SeriesResponse {
  bucket_seconds: number;
  aggregated: boolean;
  series: ApiSeries[];
}

// One series as kept in memory: only what the charts draw. Typed arrays (NaN for a missing value) instead of the
// response's four arrays of boxed numbers: t and avg as Float64 (16 bytes a point), and min/max as Float32 (8 more,
// precise enough to draw) only for averaged series, the only ones drawn with a min–max band.
export interface ChartSeries {
  group_type: string;
  station_id: string | number;
  measurement_type: string;
  unit: string;
  agg: "mean" | "sum" | "vector_mean";
  t: Float64Array;
  avg: Float64Array;
  min?: Float32Array;
  max?: Float32Array;
}

// One loaded response, with what it was loaded for and its series indexed by seriesKey.
export interface LoadedSeries {
  groups: string;
  range: Range;
  bucketS: number;
  aggregated: boolean;
  byKey: Map<string, ChartSeries>;
  series: ChartSeries[];
}

const nan = (v: number | null) => (v === null ? NaN : v);
const slim = (s: ApiSeries): ChartSeries => {
  const agg = s.agg ?? "mean";
  const out: ChartSeries = {
    group_type: s.group_type, station_id: s.station_id, measurement_type: s.measurement_type, unit: s.unit, agg,
    t: Float64Array.from(s.t),
    avg: Float64Array.from(s.avg, nan),
  };
  if (agg === "mean" && s.min && s.max) {
    out.min = Float32Array.from(s.min, nan);
    out.max = Float32Array.from(s.max, nan);
  }
  return out;
};

export const seriesKey = (s: Pick<ApiSeries, "group_type" | "station_id" | "measurement_type" | "unit">) =>
  `${s.group_type}|${s.station_id}|${s.measurement_type}|${s.unit}`;

// Responses kept. One with every group is ~29 series of up to ~2,000 points: about 1.4 MB as typed arrays, so
// at most ~17 MB.
const CACHE_ENTRIES = 12;
const DEBOUNCE_MS = 300;
const GROUP_KEYS = ["weather", "quality", "gauges"] as const;

export const UNREACHABLE = "Couldn't reach the data service. Please check your connection and try again.";

/** The error to show for a failed request. The backend's own message is shown for a request it refused (4xx: e.g.
 *  a range it can't serve) or gave up on (504: too long to compute), since it says what to change; a server failure (5xx) shows a plain message instead of
 *  whatever the server said, which is logged to the console (and so reaches Sentry's breadcrumbs). */
export async function errorFrom(res: Response, what = "chart data"): Promise<Error> {
  // A 404 here most likely means the data service is an older version, without this route
  let message = res.status === 404
    ? `Couldn't load ${what} (HTTP 404): the data service may be out of date.`
    : res.status >= 500
      ? `Couldn't load ${what} just now (HTTP ${res.status}). Please try again in a moment.`
      : `Couldn't load ${what} (HTTP ${res.status}).`;
  let detail: unknown = null;
  try {
    const body = await res.json();
    detail = body?.error ?? null;
    // 504 is the backend's own "that range took too long; pick a shorter one", which the user can act on too
    const actionable = (res.status >= 400 && res.status < 500 && res.status !== 404) || res.status === 504;
    if (detail && actionable) message = String(detail);
  } catch {
    // keep the generic message
  }
  if (res.status >= 500) console.error(`[charts] ${what}: HTTP ${res.status}`, detail);
  return new Error(message);
}

export interface ChartView {
  range: Range | null; // the picked days of the data shown
  viewWindow: Range | null; // null: the whole range
  zoomTo: (w: Range | null) => void; // normalised: at least an hour, inside the range
  overview: LoadedSeries | null;
  detail: LoadedSeries | null; // only while zoomed, and only when finer than the overview
  shownBucketS: number | null; // the resolution inside the window right now
  shownAggregated: boolean;
  loading: boolean; // the overview
  error: Error | null;
  detailLoading: boolean;
  detailError: Error | null;
  retryDetail: () => void;
  // Show a window that may reach outside the picked days (the range buttons, a shared link): the picked days move
  // to cover it. null: back to the picked days.
  showWindow: (w: Range) => void;
  // The wind rose's counts (fetched only while it is shown; see useWindRose)
  wind: WindState;
}

export interface WindRoseResponse {
  sectors: string[];
  speed_classes: { name: string; from: number; to: number | null }[];
  roses: Record<string, { total: number; counts: number[][]; percent: number[][] }>;
}

export interface WindState {
  data: WindRoseResponse | null;
  loading: boolean;
  error: Error | null;
}

export const ChartViewContext = createContext<ChartView | null>(null);

export function useChartView(): ChartView {
  const view = useContext(ChartViewContext);
  if (!view) throw new Error("useChartView needs a ChartViewContext provider");
  return view;
}

export default function useChartSeries(
  activeGroups: GroupSelection,
  startDate: Date | null,
  endDate: Date | null,
  viewWindow: Range | null,
  setViewWindow: (w: Range | null) => void,
  setDays: (startDay: Date, endDay: Date, viewWindow: Range | null) => void,
): Omit<ChartView, "wind"> {
  // The hour now: the picked days end at the next whole hour (clampToNow), so a page left open moves that end on
  // as the hours pass (the newest hour then loads on the next overview, e.g. after Reset).
  const [hour, setHour] = useState(() => Math.floor(Date.now() / 3_600_000));
  useEffect(() => {
    const id = window.setInterval(() => setHour(Math.floor(Date.now() / 3_600_000)), 60_000);
    return () => window.clearInterval(id);
  }, []);
  const rangeRef = useRef<Range | null>(null);
  const range = useMemo(() => {
    const r = startDate && endDate ? clampToNow(pickedDaysRange(startDate, endDate), hour * 3_600_000 + 1) : null;
    // The same object while the values stay the same (past days don't change on the hour), so nothing re-runs
    const prev = rangeRef.current;
    if (r && prev && r.start === prev.start && r.end === prev.end) return prev;
    rangeRef.current = r;
    return r;
  }, [startDate, endDate, hour]);
  const groups = GROUP_KEYS.filter((g) => activeGroups[g]).join(",");

  const cache = useRef(new Lru<LoadedSeries>(CACHE_ENTRIES));
  const controller = useRef<AbortController | null>(null);
  const wantedOverview = useRef("");
  const wantedDetail = useRef("");

  const [overview, setOverview] = useState<LoadedSeries | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [detail, setDetail] = useState<LoadedSeries | null>(null);
  const detailRef = useRef<LoadedSeries | null>(null);
  detailRef.current = detail;
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<Error | null>(null);
  const [retry, setRetry] = useState(0);

  // Fetch one range (or take it from the cache). Starting a request aborts whichever one is still running.
  const load = useCallback(async (r: Range, g: string): Promise<LoadedSeries> => {
    const key = `${g}|${r.start}|${r.end}`;
    const cached = cache.current.get(key);
    if (cached) return cached;

    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    const params = new URLSearchParams({ start: new Date(r.start).toISOString(), end: new Date(r.end - 1).toISOString() });
    for (const group of g.split(",")) params.append(group, "true");
    try {
      const res = await fetch(`/api/series?${params.toString()}`, { signal: c.signal }).catch((err) => {
        if (err?.name === "AbortError") throw err;
        console.error("[charts] chart data:", err);
        throw new Error(UNREACHABLE);
      });
      if (!res.ok) throw await errorFrom(res);
      const json: SeriesResponse = await res.json();
      const series = json.series.map(slim);
      const loaded: LoadedSeries = {
        groups: g, range: r, bucketS: json.bucket_seconds, aggregated: json.aggregated, series,
        byKey: new Map(series.map((s) => [seriesKey(s), s])),
      };
      cache.current.set(key, loaded);
      return loaded;
    } finally {
      if (controller.current === c) controller.current = null;
    }
  }, []);

  useEffect(() => () => controller.current?.abort(), []);

  // Overview: whenever the picked days or the groups change.
  useEffect(() => {
    if (!range || !groups) {
      wantedOverview.current = "";
      setOverview(null);
      setError(null);
      setLoading(false);
      return;
    }
    const key = `${groups}|${range.start}|${range.end}`;
    wantedOverview.current = key;
    setError(null);
    const cached = cache.current.get(key);
    if (cached) { // instant, without a spinner flashing for a frame
      setOverview(cached);
      setLoading(false);
      return;
    }
    setLoading(true);
    load(range, groups)
      .then((loaded) => {
        if (wantedOverview.current !== key) return;
        setOverview(loaded);
        setLoading(false);
      })
      .catch((err) => {
        if (wantedOverview.current !== key || err?.name === "AbortError") return;
        setOverview(null); // don't leave the previous range's charts up as if they were this range
        setError(err instanceof Error ? err : new Error(String(err)));
        setLoading(false);
      });
  }, [range, groups, load]);

  // The overview that matches what is picked now (while a new one loads, the old one stays on screen).
  const current = overview && range && overview.groups === groups
    && overview.range.start === range.start && overview.range.end === range.end ? overview : null;

  // Detail: while zoomed, for the settled window.
  useEffect(() => {
    const done = () => {
      wantedDetail.current = "";
      setDetailLoading(false);
      setDetailError(null);
    };
    if (!viewWindow || !current) {
      done();
      setDetail(null);
      return;
    }
    const r = detailRange(viewWindow, current.range, current.bucketS);
    const ideal = pickBucket(r.end - r.start);
    if (ideal >= current.bucketS) { // the overview is already this fine
      done();
      setDetail(null);
      return;
    }
    // Detail already on screen still covers the window, at least as finely as needed: nothing to load.
    const shown = detailRef.current;
    if (shown && shown.groups === groups && shown.range.start <= viewWindow.start && shown.range.end >= viewWindow.end
      && shown.bucketS <= ideal) {
      done();
      return;
    }
    const key = `${groups}|${r.start}|${r.end}`;
    wantedDetail.current = key;
    setDetailError(null);
    const cached = cache.current.get(key);
    if (cached) {
      setDetail(cached);
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    const timer = window.setTimeout(() => {
      load(r, groups)
        .then((loaded) => {
          if (wantedDetail.current !== key) return;
          setDetail(loaded);
          setDetailLoading(false);
        })
        .catch((err) => {
          if (wantedDetail.current !== key || err?.name === "AbortError") return;
          setDetailError(err instanceof Error ? err : new Error(String(err))); // the coarse data stays
          setDetailLoading(false);
        });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [viewWindow, current, groups, load, retry]);

  const zoomTo = useCallback((w: Range | null) => {
    const next = w && range ? normalizeWindow(w, range) : null;
    setViewWindow(next);
  }, [range, setViewWindow]);

  const retryDetail = useCallback(() => setRetry((n) => n + 1), []);

  const showWindow = useCallback((w: Range) => {
    if (range && w.start >= range.start && w.end <= range.end) {
      zoomTo(w);
      return;
    }
    const plan = planWindow(w, Date.now());
    // New days rebuild every chart: let React keep the page responsive meanwhile (e.g. to the next button press)
    startTransition(() => setDays(plan.startDay, plan.endDay, plan.viewWindow));
  }, [range, zoomTo, setDays]);

  // Detail counts only while zoomed and when it belongs to the groups and days picked now; while a new range
  // loads, the resolution shown is unknown (null) rather than the previous range's.
  const activeDetail = viewWindow && current && detail && detail.groups === groups
    && detail.range.start >= current.range.start && detail.range.end <= current.range.end ? detail : null;
  const covers = activeDetail && viewWindow
    && activeDetail.range.start <= viewWindow.start && activeDetail.range.end >= viewWindow.end;
  const shownBucketS = covers ? activeDetail.bucketS : current?.bucketS ?? null;
  const shownAggregated = covers ? activeDetail.aggregated : current?.aggregated ?? false;

  return useMemo(() => ({
    range: overview?.range ?? range,
    viewWindow,
    zoomTo,
    overview,
    detail: activeDetail,
    shownBucketS,
    shownAggregated,
    loading,
    error,
    detailLoading,
    detailError,
    retryDetail,
    showWindow,
  }), [overview, range, viewWindow, zoomTo, activeDetail, shownBucketS, shownAggregated, loading, error, detailLoading,
    detailError, retryDetail, showWindow]);
}
