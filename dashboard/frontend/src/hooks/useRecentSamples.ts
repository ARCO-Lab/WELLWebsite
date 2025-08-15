import { useEffect, useState } from "react";

export interface RecentSample {
  site_id: number;
  creek_id: string;
  measurement_type: string;
  value: number;
  unit: string;
  recorded_at: string;
}

export default function useRecentSamples() {
  const [samples, setSamples] = useState<RecentSample[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRecent = async () => {
    try {
      const res = await fetch("/api/recent");
      const data = await res.json();
      setSamples(data);
    } catch (err) {
      console.error("[ERROR] Failed to fetch recent samples:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecent();

    const interval = setInterval(() => {
      fetchRecent();
    }, 7 * 24 * 60 * 60 * 1000); // Refresh every 7 days (1 week)

    return () => clearInterval(interval);
  }, []);

  return { samples, loading };
}
