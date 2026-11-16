// This file defines useWindRose, which loads the wind rose's counts from /api/windrose: how often the wind blew
// from each of 16 directions at each speed over a range, counted by the database. Only while the wind rose is shown;
// one request per range (a newer one aborts the older), and the last few answers are cached: a range that reaches
// into the last hour (still filling in) for a minute only, so the rose catches up when it is shown again.

import { useEffect, useState } from "react";
import { UNREACHABLE, errorFrom } from "@/lib/seriesLoader";
import { Lru, type Range } from "@/utils/chartWindow";

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

const cache = new Lru<{ data: WindRoseResponse; at: number }>(6); // a few hundred numbers each
const LIVE_WINDOW_MS = 3_600_000, LIVE_TTL_MS = 60_000;

export default function useWindRose(range: Range | null, shown: boolean): WindState {
  const [state, setState] = useState<WindState>({ data: null, loading: false, error: null });
  const start = range?.start, end = range?.end;

  useEffect(() => {
    if (!shown || start === undefined || end === undefined) return;
    const key = `${start}|${end}`;
    const hit = cache.get(key);
    if (hit && !(end > Date.now() - LIVE_WINDOW_MS && Date.now() - hit.at > LIVE_TTL_MS)) {
      setState({ data: hit.data, loading: false, error: null });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ data: s.data, loading: true, error: null }));
    const params = new URLSearchParams({ start: new Date(start).toISOString(), end: new Date(end - 1).toISOString() });
    (async () => {
      const res = await fetch(`/api/windrose?${params.toString()}`, { signal: controller.signal }).catch((err) => {
        if (err?.name === "AbortError") throw err;
        throw new Error(UNREACHABLE);
      });
      if (!res.ok) throw await errorFrom(res, "the wind rose");
      return (await res.json()) as WindRoseResponse;
    })()
      .then((data) => {
        cache.set(key, { data, at: Date.now() });
        setState({ data, loading: false, error: null });
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setState({ data: null, loading: false, error: err instanceof Error ? err : new Error(String(err)) });
      });
    return () => controller.abort();
  }, [shown, start, end]);

  return state;
}
