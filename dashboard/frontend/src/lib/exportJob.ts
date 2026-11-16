// Requests and polling for the Download button (components/Download.tsx): fetch with readable errors, and waiting on
// a queued export until its file is ready. Everything takes an AbortSignal, so the button can stop waiting when it
// leaves the page (switching tabs unmounts it) instead of polling on unseen and starting a download later without
// warning. No React here, so scripts/exportJob.test.mjs can test it with Node.

// An error whose message was written for the user; any other error is shown as a generic message. `jobGone` means the
// queued job can't be picked up again (it failed, expired or no longer exists), so Try again must start a new one.
export class ExportError extends Error {
  jobGone = false;
  constructor(message: string, jobGone = false) {
    super(message);
    this.jobGone = jobGone;
  }
}

// fetch() itself failed: the request got no reply (offline, DNS failure, connection reset).
export class NetworkError extends ExportError {
  constructor() {
    super("Could not reach the server. Check your connection.");
  }
}

// The wait was cancelled through its AbortSignal: nobody is waiting for the answer any more.
export class ExportStopped extends Error {
  constructor() {
    super("Export stopped");
  }
}

// Shown for a queued export that failed on the server. The job's own error_message isn't shown: the server
// keeps only safe text there, but this way nothing internal can reach the page whatever the backend stores.
export const JOB_FAILED_MESSAGE = "The server couldn't build this export. Please try again later.";
export const RETRYABLE_STATUSES = [502, 503, 504];
export const POLL_RETRY_DELAYS_S = [2, 4, 8, 16]; // waits before each retry of a status check that failed
export const POLL_MAX_MINUTES = 30; // stop waiting on a job after this long (Try again resumes it)

export type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

/** Waits `seconds`, or rejects with ExportStopped as soon as the signal aborts. */
export function sleep(seconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new ExportStopped());
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", stop);
      resolve();
    }, seconds * 1000);
    const stop = () => {
      clearTimeout(timer);
      reject(new ExportStopped());
    };
    signal?.addEventListener("abort", stop, { once: true });
  });
}

/** fetch(), with the errors fetch() itself throws turned into a NetworkError (or ExportStopped once aborted). */
export async function request(fetchImpl: Fetch, input: string, init: RequestInit = {}, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetchImpl(input, { ...init, signal });
  } catch {
    if (signal?.aborted) throw new ExportStopped();
    throw new NetworkError();
  }
}

/** The JSON body of a successful reply. A proxy or server error page can arrive with a 200 too. */
export async function readJson(res: Response) {
  try {
    return await res.json();
  } catch {
    throw new ExportError("The server sent an unexpected reply.");
  }
}

/** The message for a failed API reply: the JSON body's `error` if there is one, otherwise the fallback and status.
 *  The proxies pass the backend's reply through, so an unexpected failure can be an HTML page instead of JSON. */
export async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.error === "string" && body.error) return body.error;
  } catch {
    // Not JSON; use the fallback.
  }
  return `${fallback} (HTTP ${res.status})`;
}

export interface PollOptions {
  fetchImpl: Fetch;
  signal: AbortSignal;
  onStatus: (text: string) => void; // progress for the button's label
  wait?: (seconds: number, signal: AbortSignal) => Promise<void>; // sleep(), replaceable in tests
  now?: () => number;
}

/** Waits for a queued export to finish. A status check that gets no reply or a 502/503/504 (the server restarting or
 *  briefly overloaded) is retried with growing waits, since the job keeps running meanwhile; a 404 or a failed or
 *  expired job is final. Rejects with ExportStopped as soon as the signal aborts. */
export async function pollUntilReady(jobId: string, pollIntervalSeconds: number, opts: PollOptions): Promise<void> {
  const { fetchImpl, signal, onStatus, wait = sleep, now = Date.now } = opts;
  const deadline = now() + POLL_MAX_MINUTES * 60_000;
  let retries = 0;
  for (;;) {
    if (signal.aborted) throw new ExportStopped();
    if (now() > deadline) {
      throw new ExportError("The export is taking longer than expected. Press Try again to keep waiting for it.");
    }

    let statusRes: Response | null = null;
    try {
      statusRes = await request(fetchImpl, `/api/exports/jobs/${encodeURIComponent(jobId)}`, {}, signal);
    } catch (error) {
      if (!(error instanceof NetworkError)) throw error;
    }
    if (!statusRes || RETRYABLE_STATUSES.includes(statusRes.status)) {
      if (retries >= POLL_RETRY_DELAYS_S.length) {
        throw statusRes
          ? new ExportError(await readError(statusRes, "Failed to check the export's progress"))
          : new NetworkError();
      }
      onStatus("Reconnecting");
      await wait(POLL_RETRY_DELAYS_S[retries++], signal);
      continue;
    }
    if (!statusRes.ok) {
      throw new ExportError(await readError(statusRes, "Failed to check the export's progress"), statusRes.status === 404);
    }
    retries = 0;

    const status = await readJson(statusRes);
    if (signal.aborted) throw new ExportStopped();
    const progress = typeof status.progress_pct === "number" ? status.progress_pct.toFixed(1) : "0.0";
    onStatus(`Preparing export (${status.status}${status.status === "running" ? ` ${progress}%` : ""})`);

    if (status.status === "ready") return;
    if (status.status === "failed") throw new ExportError(JOB_FAILED_MESSAGE, true);
    if (status.status === "expired") throw new ExportError("Export expired before download", true);

    await wait(Math.max(1, pollIntervalSeconds), signal);
  }
}
