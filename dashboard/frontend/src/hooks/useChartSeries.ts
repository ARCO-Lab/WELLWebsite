// This file defines useChartSeries, which loads the sensor charts' data from /api/series, and the context that
// shares it (and the one zoom window all charts follow) with every chart on the page and in the modal.
//
// - Overview: the picked days, for the active groups, in one request; /api/series aggregates it to ~2,000
//   points per series.
// - Detail: while zoomed, once the window has settled for 300 ms, one more request for the window plus half its
//   width on each side, snapped to the overview's bucket grid. Charts draw overview points outside that range
//   and detail points inside it, so data is never blank: coarse first, then sharper in place.
// - One AbortController for all of them: a new request cancels the previous one, and a response that is no longer
//   wanted is ignored. The last 20 responses are cached, so zooming out, Reset and revisits need no request.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { GroupSelection, SensorData } from "@/hooks/useFilteredData";
import { Lru, detailRange, normalizeWindow, pickBucket, pickedDaysRange, type Range } from "@/utils/chartWindow";

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

// One loaded response, with what it was loaded for and its series indexed by seriesKey.
export interface LoadedSeries {
  groups: string;
  range: Range;
  bucketS: number;
  aggregated: boolean;
  byKey: Map<string, ApiSeries>;
  series: ApiSeries[];
}

export const seriesKey = (s: Pick<ApiSeries, "group_type" | "station_id" | "measurement_type" | "unit">) =>
  `${s.group_type}|${s.station_id}|${s.measurement_type}|${s.unit}`;

const CACHE_ENTRIES = 20;
const DEBOUNCE_MS = 300;
const GROUP_KEYS = ["weather", "quality", "gauges"] as const;

async function errorFrom(res: Response): Promise<Error> {
  let message = `Couldn't load chart data (HTTP ${res.status}).`;
  try {
    const body = await res.json();
    if (body?.error) message = body.error;
  } catch {
    // keep the generic message
  }
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
  // Raw readings for the wind rose (fetched only while it is shown)
  wind: { data: SensorData[]; loading: boolean; error: Error | null };
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
  wind: ChartView["wind"],
): ChartView {
  const range = useMemo(
    () => (startDate && endDate ? pickedDaysRange(startDate, endDate) : null),
    [startDate, endDate]
  );
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
      const res = await fetch(`/api/series?${params.toString()}`, { signal: c.signal });
      if (!res.ok) throw await errorFrom(res);
      const json: SeriesResponse = await res.json();
      const loaded: LoadedSeries = {
        groups: g, range: r, bucketS: json.bucket_seconds, aggregated: json.aggregated, series: json.series,
        byKey: new Map(json.series.map((s) => [seriesKey(s), s])),
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

  const activeDetail = viewWindow && detail && detail.groups === groups ? detail : null;
  const covers = activeDetail && viewWindow
    && activeDetail.range.start <= viewWindow.start && activeDetail.range.end >= viewWindow.end;
  const shownBucketS = covers ? activeDetail.bucketS : overview?.bucketS ?? null;
  const shownAggregated = covers ? activeDetail.aggregated : overview?.aggregated ?? false;

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
    wind,
  }), [overview, range, viewWindow, zoomTo, activeDetail, shownBucketS, shownAggregated, loading, error, detailLoading,
    detailError, retryDetail, wind]);
}
