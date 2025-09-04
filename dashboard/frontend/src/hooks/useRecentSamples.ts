// This file defines the useRecentSamples React hook for fetching the most recent sampling measurements from the API.
// It auto-refreshes every 7 days and manages loading state.

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

  // Fetches the most recent sampling data from the backend API
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

    // Set up interval to refresh samples every 7 days
    const interval = setInterval(() => {
      fetchRecent();
    }, 7 * 24 * 60 * 60 * 1000); // Refresh every 7 days (1 week)

    return () => clearInterval(interval);
  }, []);

  return { samples, loading };
}
