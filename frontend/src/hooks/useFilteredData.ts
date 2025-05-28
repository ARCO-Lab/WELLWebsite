import { useEffect, useState } from "react";

interface SensorData {
    sensor: string;
    value: number;
    unit: string;
    timestamp: string;
    group_type: string;
    measurement_type: string;
    station_id: string;
}

interface GroupSelection {
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

    useEffect(() => {
        const fetchData = async () => {
            if (!startDate || !endDate) return;

            setLoading(true);
            setError(null);

            const params = new URLSearchParams();
            params.append("start", startDate.toISOString());
            params.append("end", endDate.toISOString());
            if (activeGroups.weather) params.append("weather", "true");
            if (activeGroups.quality) params.append("quality", "true");
            if (activeGroups.gauges) params.append("gauges", "true");

            try {
              const res = await fetch(`/api/data?${params.toString()}`);
              if (!res.ok) throw new Error(`Failed to fetch sensor data: ${res.status}`);

              const json = await res.json();

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