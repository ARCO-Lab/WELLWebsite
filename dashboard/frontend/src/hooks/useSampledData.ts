// This file defines the useSampledData React hook for fetching and caching filtered creek sampling data from the API.
// It manages loading, error, and caching state, and only fetches data when dates and at least one creek are selected.

import { useEffect, useState, useRef } from "react";
import { siteDayBounds } from "@/utils/siteTime";

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
      // Guard against null dates AND no active creeks. Only fetch if both are set.
      const hasActiveCreeks = Object.values(activeCreeks).some(v => v);
      if (!startDate || !endDate || !hasActiveCreeks) {
        setData([]); // Ensure data is cleared if conditions aren't met
        return;
      }

      setLoading(true);
      setError(null);

      // The picked days in Toronto time, wherever the viewer is
      const { start, end } = siteDayBounds(startDate, endDate);

      const params = new URLSearchParams();
      params.append("start", start);
      params.append("end", end);

      Object.entries(activeCreeks).forEach(([creek, isSelected]) => {
        if (isSelected) {
          params.append(creek, "true");
        }
      });

      const key = `${start}|${end}|${JSON.stringify(activeCreeks)}`;
      if (cache.current.has(key)) {
        setData(cache.current.get(key)!);
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`/api/samples?${params.toString()}`);
        if (!res.ok) {
          // Show the API's own explanation when it gives one (e.g. an invalid date range).
          let message = `Couldn't load sampling data (HTTP ${res.status}).`;
          try {
            const body = await res.json();
            if (typeof body?.error === "string" && body.error) message = body.error;
          } catch {
            // Not JSON; keep the generic message.
          }
          throw new Error(message);
        }

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