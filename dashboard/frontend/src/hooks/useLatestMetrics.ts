// This file defines the useLatestMetrics React hook for fetching the latest sensor metrics from the API.
// It auto-refreshes every 10 minutes and manages loading state.

import { useEffect, useState }  from "react";

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

    // Fetches the latest metrics from the backend API
    const fetchLatest = async () => {
        try {
            const res = await fetch("/api/latest");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            // Keep the last good values unless the reply is the expected list.
            if (!Array.isArray(data)) throw new Error("Unexpected response");
            setMetrics(data);
        } catch (err) {
            console.error("[ERROR] Failed to fetch latest metrics:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLatest();

        // Set up interval to refresh metrics every 10 minutes
        const interval = setInterval(() => {
            fetchLatest();
        }, 10 * 60 * 1000); // Refresh every 10 minutes

        return () => clearInterval(interval);
    }, []);

    return { metrics, loading };
}