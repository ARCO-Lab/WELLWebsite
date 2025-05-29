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

    const fetchLatest = async () => {
        try {
            const res = await fetch("/api/latest");
            const data = await res.json();
            setMetrics(data);
        } catch (err) {
            console.error("[ERROR] Failed to fetch latest metrics:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLatest();

        const interval = setInterval(() => {
            fetchLatest();
        }, 10 * 60 * 1000); // Refresh every 10 minutes

        return () => clearInterval(interval);
    }, []);

    return { metrics, loading };
}