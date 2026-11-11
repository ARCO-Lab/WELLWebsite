// This file defines the useLatestMetrics React hook for fetching the latest sensor metrics from the API.
// It auto-refreshes every 10 minutes and manages loading state.

import { useCallback, useEffect, useRef, useState }  from "react";

export interface Metric {
    station_id: string;
    group_type: string;
    measurement_type: string;
    value: number;
    unit: string;
    recorded_at: string;
}

export default function useLatestMetrics() {
    const [metrics, setMetrics] = useState<Metric[]>([]);
    const [loading, setLoading] = useState(true);
    // Set when the last fetch failed, so the panel can say so (and offer a retry) instead of showing "No data".
    const [error, setError] = useState(false);

    // Fetches overlap when Retry is pressed during a refresh; only the newest one's reply counts.
    const latestRequest = useRef(0);

    // Fetches the latest metrics from the backend API
    const fetchLatest = useCallback(async () => {
        const request = ++latestRequest.current;
        try {
            const res = await fetch("/api/latest");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (request !== latestRequest.current) return;
            // Keep the last good values unless the reply is the expected list.
            if (!Array.isArray(data)) throw new Error("Unexpected response");
            setMetrics(data);
            setError(false);
        } catch (err) {
            if (request !== latestRequest.current) return;
            console.error("[ERROR] Failed to fetch latest metrics:", err);
            setError(true);
        } finally {
            if (request === latestRequest.current) setLoading(false);
        }
    }, []);

    // Try again now, showing the loading placeholder while it does.
    const retry = useCallback(() => {
        setLoading(true);
        fetchLatest();
    }, [fetchLatest]);

    useEffect(() => {
        fetchLatest();

        // Set up interval to refresh metrics every 10 minutes
        const interval = setInterval(() => {
            fetchLatest();
        }, 10 * 60 * 1000); // Refresh every 10 minutes

        return () => clearInterval(interval);
    }, [fetchLatest]);

    return { metrics, loading, error, retry };
}