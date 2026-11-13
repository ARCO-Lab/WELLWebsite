// Fetches creek sampling rows (/api/samples) for useSampledData, one selection at a time. Only the newest request
// counts: starting a new one aborts the one before, and a reply that still arrives for an older request is dropped.
// Without this, a slow reply to an earlier selection could land after a quicker one and leave the charts showing the
// wrong creeks, or waiting for good. Replies are cached by selection, so ticking a creek back on is instant.

export interface SampledData {
  site_id: string;
  creek_id: string;
  measurement_type: string;
  value: number;
  unit: string;
  recorded_at: string;
}

export interface SampleResult {
  key: string; // the selection this answers
  data: SampledData[] | null; // null when the request failed
  error: Error | null;
}

type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

// The message for a failed reply: the API's own explanation when it gives one (e.g. an invalid date range).
async function failure(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    if (typeof body?.error === "string" && body.error) return new Error(body.error);
  } catch {
    // Not JSON; keep the generic message.
  }
  return new Error(`Couldn't load sampling data (HTTP ${res.status}).`);
}

export class SampleFetcher {
  private cache = new Map<string, SampledData[]>();
  private current: AbortController | null = null;
  private fetchImpl: Fetch;

  // A wrapper rather than fetch itself: the browser's fetch throws "Illegal invocation" when called as a method of
  // another object.
  constructor(fetchImpl: Fetch = (input, init) => fetch(input, init)) {
    this.fetchImpl = fetchImpl;
  }

  /** Loads one selection. Resolves with its result, or with null if a later load() or cancel() superseded it (its
   *  caller should then do nothing: the newer request will answer). */
  async load(key: string, url: string): Promise<SampleResult | null> {
    this.cancel();
    const cached = this.cache.get(key);
    if (cached) return { key, data: cached, error: null };

    const controller = new AbortController();
    this.current = controller;
    const stillWanted = () => this.current === controller && !controller.signal.aborted;
    try {
      const res = await this.fetchImpl(url, { signal: controller.signal });
      if (!res.ok) {
        const error = await failure(res);
        return stillWanted() ? { key, data: null, error } : null;
      }
      const json = await res.json();
      if (!stillWanted()) return null;
      if (!Array.isArray(json)) return { key, data: null, error: new Error("Unexpected reply from the server.") };
      this.cache.set(key, json);
      return { key, data: json, error: null };
    } catch (err) {
      if (!stillWanted()) return null; // aborted, or failed after being superseded
      return { key, data: null, error: err instanceof Error ? err : new Error(String(err)) };
    } finally {
      if (this.current === controller) this.current = null;
    }
  }

  /** Stops waiting for the request in flight (its load() resolves with null). */
  cancel(): void {
    this.current?.abort();
    this.current = null;
  }
}
