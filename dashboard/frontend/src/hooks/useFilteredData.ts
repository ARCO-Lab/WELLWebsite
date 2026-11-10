// This file defines the useFilteredData React hook for fetching and caching filtered sensor data from the API.
// It manages loading, error, and caching state for efficient data retrieval.

import { useEffect, useState, useRef } from "react";

export interface SensorData {
    sensor: string;
    value: number;
    unit: string;
    recorded_at: string;
    group_type: string;
    measurement_type: string;
    station_id: string;
}

export interface GroupSelection {
    gauges: boolean;
    weather: boolean;
    quality: boolean
}

// Ranges kept in memory, most recent last. Raw payloads can be tens of MB, so keep only a few.
const CACHE_SIZE = 5;

const useFilteredData = (
    activeGroups: GroupSelection,
    startDate: Date | null,
    endDate: Date | null
) => {
    const [data, setData] = useState<SensorData[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const cache = useRef<Map<string, SensorData[]>>(new Map());

    useEffect(() => {
        if (!startDate || !endDate) return;

        // A newer range (or unmount) cancels this request, and its response is ignored if it still arrives.
        const controller = new AbortController();
        let stale = false;

        // Normalize dates to cover the full selected range
        const start = new Date(startDate);
        start.setHours(0, 0, 0, 0); // Normalize to start of day

        const end = new Date(endDate);
        end.setHours(23, 59, 59, 999); // Normalize to end of day

        // Build cache key based on date range and group selection
        const params = new URLSearchParams();
        params.append("start", start.toISOString());
        params.append("end", end.toISOString());
        if (activeGroups.weather) params.append("weather", "true");
        if (activeGroups.quality) params.append("quality", "true");
        if (activeGroups.gauges) params.append("gauges", "true");

        const key = `${start.toISOString()}|${end.toISOString()}|${JSON.stringify(activeGroups)}`;
        const cached = cache.current.get(key);
        if (cached) {
            cache.current.delete(key); // mark as most recently used
            cache.current.set(key, cached);
            setData(cached);
            setError(null);
            setLoading(false);
            return;
        }

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                // Fetch filtered sensor data from the backend API
                const res = await fetch(`/api/data?${params.toString()}`, { signal: controller.signal });
                if (!res.ok) {
                    // e.g. 413 when the range has more readings than the charts can show; the API says what to do
                    let message = `Couldn't load sensor data (HTTP ${res.status}).`;
                    try {
                        const body = await res.json();
                        if (body?.error) message = body.error;
                    } catch {
                        // keep the generic message
                    }
                    throw new Error(message);
                }

                const json: SensorData[] = await res.json();
                if (stale) return;

                cache.current.set(key, json);
                while (cache.current.size > CACHE_SIZE) {
                    cache.current.delete(cache.current.keys().next().value as string);
                }
                setData(json);
            } catch (err: any) {
                if (stale || err?.name === "AbortError") return;
                setData([]); // don't leave the previous range's charts up as if they were this range
                setError(err instanceof Error ? err : new Error(String(err)));
            } finally {
                if (!stale) setLoading(false);
            }
        };

        fetchData();
        return () => {
            stale = true;
            controller.abort();
        };
    }, [activeGroups, startDate, endDate]);

    return { data, loading, error };
};

export default useFilteredData;
