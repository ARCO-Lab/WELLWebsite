import { useCallback, useMemo, useRef, useState } from "react";

const BUCKET_SIZE_MS = 6 * 60 * 60 * 1000;
const PREFETCH_BUCKETS = 1;
const REQUEST_TIMEOUT_MS = 15000;

export interface ViewportCacheMetadata {
  totalBuckets: number;
  inFlightRequests: number;
}

interface SensorData {
  measurement_type: string;
  unit: string;
  recorded_at: string | Date;
  value: number;
}

interface CacheBucket {
  data: SensorData[];
  fetchedAt: number;
}

interface GroupSelection {
  gauges: boolean;
  weather: boolean;
  quality: boolean;
}

interface GetCachedDataOptions {
  minTs: number;
  maxTs: number;
  activeGroups: GroupSelection;
  granularity?: string;
  prefetchAdjacent?: boolean;
}

const getRangeBuckets = (minTs: number, maxTs: number): Array<{ start: number; end: number }> => {
  const buckets: Array<{ start: number; end: number }> = [];
  let current = Math.floor(minTs / BUCKET_SIZE_MS) * BUCKET_SIZE_MS;
  while (current <= maxTs) {
    buckets.push({ start: current, end: current + BUCKET_SIZE_MS });
    current += BUCKET_SIZE_MS;
  }
  return buckets;
};

const toGroupParamKey = (groups: GroupSelection): string => {
  return [
    groups.weather ? "weather" : "",
    groups.quality ? "quality" : "",
    groups.gauges ? "gauges" : "",
  ]
    .filter(Boolean)
    .join(",");
};

export default function useViewportCache() {
  const cacheRef = useRef<Map<string, CacheBucket>>(new Map());
  const inFlightRef = useRef<Map<string, Promise<SensorData[]>>>(new Map());
  const abortRef = useRef<Map<string, AbortController>>(new Map());
  const [inFlightRequests, setInFlightRequests] = useState(0);

  const buildBucketKey = useCallback(
    (start: number, end: number, activeGroups: GroupSelection, granularity: string) =>
      `${start}|${end}|${toGroupParamKey(activeGroups)}|${granularity}`,
    []
  );

  const fetchBucket = useCallback(
    async (start: number, end: number, activeGroups: GroupSelection, granularity: string): Promise<SensorData[]> => {
      const key = buildBucketKey(start, end, activeGroups, granularity);

      const cached = cacheRef.current.get(key);
      if (cached) {
        return cached.data;
      }

      const existing = inFlightRef.current.get(key);
      if (existing) {
        return existing;
      }

      const controller = new AbortController();
      abortRef.current.set(key, controller);
      setInFlightRequests((n) => n + 1);

      const promise = (async () => {
        const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        try {
          const params = new URLSearchParams();
          params.append("start", new Date(start).toISOString());
          params.append("end", new Date(end).toISOString());
          params.append("granularity", granularity);
          if (activeGroups.weather) params.append("weather", "true");
          if (activeGroups.quality) params.append("quality", "true");
          if (activeGroups.gauges) params.append("gauges", "true");

          const res = await fetch(`/api/data?${params.toString()}`, {
            signal: controller.signal,
          });
          if (!res.ok) {
            throw new Error(`Viewport cache request failed with ${res.status}`);
          }

          const payload = await res.json();
          const rows: SensorData[] = Array.isArray(payload) ? payload : payload?.data || [];

          cacheRef.current.set(key, {
            data: rows,
            fetchedAt: Date.now(),
          });
          return rows;
        } finally {
          clearTimeout(timeout);
          inFlightRef.current.delete(key);
          abortRef.current.delete(key);
          setInFlightRequests((n) => Math.max(0, n - 1));
        }
      })();

      inFlightRef.current.set(key, promise);
      return promise;
    },
    [buildBucketKey]
  );

  const getCachedDataForRange = useCallback(
    async ({
      minTs,
      maxTs,
      activeGroups,
      granularity = "auto",
      prefetchAdjacent = true,
    }: GetCachedDataOptions): Promise<SensorData[]> => {
      const buckets = getRangeBuckets(minTs, maxTs);
      const rowsByBucket = await Promise.all(
        buckets.map((b) => fetchBucket(b.start, b.end, activeGroups, granularity))
      );

      if (prefetchAdjacent) {
        const first = buckets[0];
        const last = buckets[buckets.length - 1];
        if (first && last) {
          const prevStart = first.start - BUCKET_SIZE_MS * PREFETCH_BUCKETS;
          const prevEnd = first.start;
          const nextStart = last.end;
          const nextEnd = last.end + BUCKET_SIZE_MS * PREFETCH_BUCKETS;
          fetchBucket(prevStart, prevEnd, activeGroups, granularity).catch(() => undefined);
          fetchBucket(nextStart, nextEnd, activeGroups, granularity).catch(() => undefined);
        }
      }

      return rowsByBucket.flat().sort((a, b) => {
        const aTs = new Date(a.recorded_at).getTime();
        const bTs = new Date(b.recorded_at).getTime();
        return aTs - bTs;
      });
    },
    [fetchBucket]
  );

  const clearCache = useCallback(() => {
    cacheRef.current.clear();
    inFlightRef.current.forEach((_, key) => abortRef.current.get(key)?.abort());
    inFlightRef.current.clear();
    abortRef.current.clear();
    setInFlightRequests(0);
  }, []);

  const pruneCacheOlderThan = useCallback((olderThanMs: number) => {
    const cutoff = Date.now() - olderThanMs;
    const toDelete: string[] = [];
    cacheRef.current.forEach((value, key) => {
      if (value.fetchedAt < cutoff) {
        toDelete.push(key);
      }
    });
    toDelete.forEach((key) => cacheRef.current.delete(key));
  }, []);

  const metadata = useMemo<ViewportCacheMetadata>(
    () => ({
      totalBuckets: cacheRef.current.size,
      inFlightRequests,
    }),
    [inFlightRequests]
  );

  return {
    getCachedDataForRange,
    clearCache,
    pruneCacheOlderThan,
    metadata,
  };
}