// This file defines useWindRose, which loads the wind rose's counts from /api/windrose: how often the wind blew
// from each of 16 directions at each speed over the picked days, counted by the database. Only while the wind
// rose is shown; one request per range (a newer one aborts the older), and the last few answers are cached.

import { useEffect, useState } from "react";
import { UNREACHABLE, errorFrom, type WindRoseResponse, type WindState } from "@/hooks/useChartSeries";
import { Lru, type Range } from "@/utils/chartWindow";

const cache = new Lru<WindRoseResponse>(6); // a few hundred numbers each

export default function useWindRose(range: Range | null, shown: boolean): WindState {
  const [state, setState] = useState<WindState>({ data: null, loading: false, error: null });
  const start = range?.start, end = range?.end;

  useEffect(() => {
    if (!shown || start === undefined || end === undefined) return;
    const key = `${start}|${end}`;
    const cached = cache.get(key);
    if (cached) {
      setState({ data: cached, loading: false, error: null });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ data: s.data, loading: true, error: null }));
    const params = new URLSearchParams({ start: new Date(start).toISOString(), end: new Date(end - 1).toISOString() });
    (async () => {
      const res = await fetch(`/api/windrose?${params.toString()}`, { signal: controller.signal }).catch((err) => {
        if (err?.name === "AbortError") throw err;
        console.error("[charts] wind rose:", err);
        throw new Error(UNREACHABLE);
      });
      if (!res.ok) throw await errorFrom(res, "the wind rose");
      return (await res.json()) as WindRoseResponse;
    })()
      .then((data) => {
        cache.set(key, data);
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
