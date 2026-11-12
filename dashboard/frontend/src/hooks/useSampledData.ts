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

const useSampledData = (
  activeCreeks: CreekSelection,
  startDate: Date | null,
  endDate: Date | null
) => {
  const [data, setData] = useState<SampledData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

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
  const wantedKey = wanted?.key ?? "";

  // The last selection whose reply was shown. Until it is the wanted one the data is not this selection's yet, so the
  // hook reports loading: right after a creek is ticked, before the request has even started, an empty list must not
  // read as "no samples in this range".
  const [doneKey, setDoneKey] = useState("");

  useEffect(() => {
    const f = (fetcher.current ??= new SampleFetcher());
    if (!wanted) {
      f.cancel();
      setData([]);
      setLoading(false); // a request that was in flight never answers now
      return;
    }
    let live = true;
    setLoading(true);
    setError(null);
    f.load(wanted.key, wanted.url).then((result) => {
      if (!result || !live) return; // superseded by a newer selection, whose reply will answer
      if (result.error) setError(result.error);
      else setData(result.data ?? []);
      setLoading(false);
      setDoneKey(result.key);
    });
    // A newer selection (or leaving the page) aborts this request.
    return () => {
      live = false;
      f.cancel();
    };
  }, [wanted]);

  return { data, loading: loading || (wantedKey !== "" && doneKey !== wantedKey), error };
};

export default useSampledData;
