// This file defines the useRecentSamples React hook for fetching the most recent sampling measurements from the API.
// It auto-refreshes every 7 days and manages loading state.

import { useCallback, useEffect, useRef, useState } from "react";

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
  // Set when the last fetch failed, so the panel can say so (and offer a retry) instead of showing "No data".
  const [error, setError] = useState(false);

  // Fetches overlap when Retry is pressed during a refresh; only the newest one's reply counts.
  const latestRequest = useRef(0);

  // Fetches the most recent sampling data from the backend API
  const fetchRecent = useCallback(async () => {
    const request = ++latestRequest.current;
    try {
      const res = await fetch("/api/recent");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (request !== latestRequest.current) return;
      // Keep the last good values unless the reply is the expected list.
      if (!Array.isArray(data)) throw new Error("Unexpected response");
      setSamples(data);
      setError(false);
    } catch (err) {
      if (request !== latestRequest.current) return;
      console.error("[ERROR] Failed to fetch recent samples:", err);
      setError(true);
    } finally {
      if (request === latestRequest.current) setLoading(false);
    }
  }, []);

  // Try again now, showing the loading placeholder while it does.
  const retry = useCallback(() => {
    setLoading(true);
    fetchRecent();
  }, [fetchRecent]);

  useEffect(() => {
    fetchRecent();

    // Set up interval to refresh samples every 7 days
    const interval = setInterval(() => {
      fetchRecent();
    }, 7 * 24 * 60 * 60 * 1000); // Refresh every 7 days (1 week)

    return () => clearInterval(interval);
  }, [fetchRecent]);

  return { samples, loading, error, retry };
}
