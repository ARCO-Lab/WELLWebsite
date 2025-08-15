import { useEffect, useState, useRef } from "react";

export interface SampledData {
  site_id: string;
  creek_id: string;
  measurement_type: string;
  value: number;
  unit: string;
  recorded_at: string;
}

export interface CreekSelection {
  ancaster: boolean;
  tiffany: boolean;
  sulphur: boolean;
  coldwater: boolean;
  spencer: boolean;
}

const useSampledData = (
  activeCreeks: CreekSelection,
  startDate: Date | null,
  endDate: Date | null
) => {
  const [data, setData] = useState<SampledData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const cache = useRef<Map<string, SampledData[]>>(new Map());

  useEffect(() => {
    const fetchData = async () => {
      // 1. Guard against null dates AND no active creeks. This is the key.
      // If there are no dates OR no active creeks, do absolutely nothing.
      const hasActiveCreeks = Object.values(activeCreeks).some(v => v);
      if (!startDate || !endDate || !hasActiveCreeks) {
        setData([]); // Ensure data is cleared if conditions aren't met
        return;
      }

      // 2. Only now is it safe to proceed.
      setLoading(true);
      setError(null);

      const start = new Date(startDate);
      start.setHours(0, 0, 0, 0);

      const end = new Date(endDate);
      end.setHours(23, 59, 59, 999);

      const params = new URLSearchParams();
      params.append("start", start.toISOString());
      params.append("end", end.toISOString());

      Object.entries(activeCreeks).forEach(([creek, isSelected]) => {
        if (isSelected) {
          params.append(creek, "true");
        }
      });

      const key = `${start.toISOString()}|${end.toISOString()}|${JSON.stringify(activeCreeks)}`;
      if (cache.current.has(key)) {
        setData(cache.current.get(key)!);
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`/api/samples?${params.toString()}`);
        if (!res.ok) throw new Error(`Failed to fetch sampled data: ${res.status}`);

        const json = await res.json();
        cache.current.set(key, json);
        setData(json);
      } catch (err: any) {
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [activeCreeks, startDate, endDate]);

  return { data, loading, error };
};

export default useSampledData;