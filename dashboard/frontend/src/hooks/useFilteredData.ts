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
        const fetchData = async () => {
            if (!startDate || !endDate) return;

            setLoading(true);
            setError(null);

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
            if (cache.current.has(key)) {
              setData(cache.current.get(key)!);
              setLoading(false);
              return;
            }

            try {
              // Fetch filtered sensor data from the backend API
              const res = await fetch(`/api/data?${params.toString()}`);
              if (!res.ok) throw new Error(`Failed to fetch sensor data: ${res.status}`);

              const json = await res.json();

              const key = `${start.toISOString()}|${end.toISOString()}|${JSON.stringify(activeGroups)}`;
              cache.current.set(key, json);
              setData(json);
            } catch (err: any) {
              setError(err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
      }, [activeGroups, startDate, endDate]);

    return { data, loading, error };
};

export default useFilteredData;