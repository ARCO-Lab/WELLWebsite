// This file defines the useSampledData React hook for fetching and caching filtered creek sampling data from the API.
// It manages loading, error, and caching state, and only fetches data when dates and at least one creek are selected.
// Requests go through SampleFetcher, so only the newest selection's reply is ever shown.

import { useEffect, useMemo, useState, useRef } from "react";
import { siteDayBounds } from "@/utils/siteTime";
import { SampleFetcher, type SampledData } from "@/lib/sampleFetcher";

export type { SampledData };

export interface CreekSelection {
  ancaster: boolean;
  tiffany: boolean;
  sulphur: boolean;
  coldwater: boolean;
  spencer: boolean;
}

const NO_ROWS: SampledData[] = [];

const useSampledData = (
  activeCreeks: CreekSelection,
  startDate: Date | null,
  endDate: Date | null
) => {
  // The last rows fetched (kept on screen, under a spinner, while the next selection loads or after it fails), and
  // the last selection that was answered, with its error if it failed.
  const [data, setData] = useState<SampledData[]>(NO_ROWS);
  const [done, setDone] = useState<{ key: string; error: Error | null }>({ key: "", error: null });

  const fetcher = useRef<SampleFetcher | null>(null);

  // What is wanted now (null for nothing): its cache key and its URL. The picked days are Toronto days, wherever the
  // viewer is.
  const wanted = useMemo(() => {
    if (!startDate || !endDate || !Object.values(activeCreeks).some(v => v)) return null;
    const { start, end } = siteDayBounds(startDate, endDate);
    const params = new URLSearchParams({ start, end });
    Object.entries(activeCreeks).forEach(([creek, isSelected]) => {
      if (isSelected) params.append(creek, "true");
    });
    return { key: `${start}|${end}|${JSON.stringify(activeCreeks)}`, url: `/api/samples?${params.toString()}` };
  }, [activeCreeks, startDate, endDate]);

  useEffect(() => {
    const f = (fetcher.current ??= new SampleFetcher());
    if (!wanted) {
      f.cancel(); // a request in flight never answers now
      return;
    }
    let live = true;
    f.load(wanted.key, wanted.url).then((result) => {
      if (!result || !live) return; // superseded by a newer selection, whose reply will answer
      if (result.data) setData(result.data);
      setDone({ key: result.key, error: result.error });
    });
    // A newer selection (or leaving the page) aborts this request.
    return () => {
      live = false;
      f.cancel();
    };
  }, [wanted]);

  // Until the wanted selection is answered the data is not its own yet, so the hook reports loading: right after a
  // creek is ticked, before the request has even started, an empty list must not read as "no samples in this range".
  const answered = wanted !== null && done.key === wanted.key;
  return {
    data: wanted ? data : NO_ROWS,
    loading: wanted !== null && !answered,
    error: answered ? done.error : null,
  };
};

export default useSampledData;
