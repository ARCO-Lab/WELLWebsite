// Per-visitor limits on the API routes that call the backend (used by lib/proxyBackend.ts), so one address can't
// keep the backend's 12 threads busy or flood it with requests. Everything is kept in this process's memory: the
// dashboard runs as one Node process, and a restart forgetting the counts is harmless.
//
// Two token buckets per address: every request takes a token from the first, and a slow request (one that can hold
// a backend thread for seconds: the wind rose, raw data, sampling rows, chart series without a bucket, export
// estimates, direct exports and new export jobs) also takes one from the second. A bucket refills at a steady rate up
// to its size, so short bursts (a page load, a chart zoomed quickly) pass while a sustained flood gets 429s. On top of
// that, an address may have only so many slow requests in flight at once, and only so many export downloads (a
// download holds a backend thread for as long as the browser takes to read it). The backend has 12 threads
// (dashboard/backend/Dockerfile), so one address can hold at most half of them with slow requests. A slow request
// counts until the backend has finished it, even if the browser gave up on it first (lib/proxyBackend.ts), so one
// person who changes the wind rose's range or the sampling filters quickly can have several abandoned requests still
// counting: 6 leaves them room for that, and still leaves half the threads to everyone else. The rate limits
// are generous for one person; addresses shared by many people (a campus NAT) are why they are this high. Each can be
// changed with an environment variable (see limitsFromEnv); 0 turns one off.
//
// ClientCounter logs, at most every 10 minutes, how many different addresses made requests: if it stays at 1 while
// the site has visitors, every visitor is seen as the same address and shares one budget (see lib/clientIp.ts).

export type Limits = {
  burst: number; // requests one address may make at once
  perMinute: number; // and sustained, per minute
  slowBurst: number;
  slowPerMinute: number;
  slowConcurrent: number; // slow requests one address may have in flight
  downloadConcurrent: number; // export downloads one address may have in flight
};

export const DEFAULT_LIMITS: Limits = {
  burst: 600, perMinute: 600, slowBurst: 120, slowPerMinute: 120, slowConcurrent: 6, downloadConcurrent: 2,
};

// What a request costs the backend: "slow" requests can hold a thread for seconds, and a "download" holds one while
// the file is sent. Everything else is "fast".
export type RequestKind = "fast" | "slow" | "download";

/** Counts the different client addresses seen in each window of `windowMs`, and once a window has ended, on the next
 *  request, gives the line to log: counts only, never an address. At most `cap` addresses are remembered per window. */
export class ClientCounter {
  private seen = new Set<string>();
  private requests = 0;
  private since: number;
  private windowMs: number;
  private cap: number;

  constructor(now: number, windowMs = 10 * 60_000, cap = 100_000) {
    this.since = now;
    this.windowMs = windowMs;
    this.cap = cap;
  }

  record(ip: string, now: number): string | null {
    let line: string | null = null;
    if (now - this.since >= this.windowMs) {
      const n = this.seen.size >= this.cap ? `${this.cap}+` : String(this.seen.size);
      const minutes = Math.round((now - this.since) / 60_000);
      line = `[client-ip] ${n} different client addresses in ${this.requests} API requests over the last ${minutes} min`;
      this.seen.clear();
      this.requests = 0;
      this.since = now;
    }
    this.requests++;
    if (ip && this.seen.size < this.cap) this.seen.add(ip);
    return line;
  }
}

// Backend paths (without the query) whose requests count as slow, by method.
const SLOW: Record<string, string[]> = {
  "/api/windrose": ["GET"],
  "/api/data": ["GET"],
  "/api/samples": ["GET"],
  "/api/exports/estimate": ["POST"],
  "/api/exports/sync": ["POST"],
  "/api/exports/jobs": ["POST"],
};
const DOWNLOAD = /^\/api\/exports\/jobs\/[^/]+\/download$/;

export function requestKind(path: string, method = "GET"): RequestKind {
  const [bare, query = ""] = path.split("?", 2);
  const m = method.toUpperCase();
  if (m === "GET" && DOWNLOAD.test(bare)) return "download";
  if (SLOW[bare]?.includes(m)) return "slow";
  // Chart tiles (with a bucket) are mostly answered from the backend's cache; any other range is an aggregate
  // over all of it
  if (bare === "/api/series" && m === "GET" && !new URLSearchParams(query).get("bucket")) return "slow";
  return "fast";
}

export function isSlow(path: string, method = "GET"): boolean {
  return requestKind(path, method) === "slow";
}

function num(value: string | undefined, fallback: number): number {
  if (value === undefined || value.trim() === "") return fallback;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

/** The limits, with any of RATE_LIMIT_BURST, RATE_LIMIT_PER_MINUTE, RATE_LIMIT_SLOW_BURST, RATE_LIMIT_SLOW_PER_MINUTE,
 *  RATE_LIMIT_SLOW_CONCURRENT and RATE_LIMIT_DOWNLOAD_CONCURRENT set in the environment replacing the default. */
export function limitsFromEnv(env: Record<string, string | undefined> = process.env): Limits {
  return {
    burst: num(env.RATE_LIMIT_BURST, DEFAULT_LIMITS.burst),
    perMinute: num(env.RATE_LIMIT_PER_MINUTE, DEFAULT_LIMITS.perMinute),
    slowBurst: num(env.RATE_LIMIT_SLOW_BURST, DEFAULT_LIMITS.slowBurst),
    slowPerMinute: num(env.RATE_LIMIT_SLOW_PER_MINUTE, DEFAULT_LIMITS.slowPerMinute),
    slowConcurrent: num(env.RATE_LIMIT_SLOW_CONCURRENT, DEFAULT_LIMITS.slowConcurrent),
    downloadConcurrent: num(env.RATE_LIMIT_DOWNLOAD_CONCURRENT, DEFAULT_LIMITS.downloadConcurrent),
  };
}

type Bucket = { tokens: number; at: number };

/** Token buckets by key: `size` tokens at most, refilled at `perMinute`. Full buckets are forgotten now and then, so
 *  the map holds only addresses seen recently. */
export class TokenBuckets {
  private buckets = new Map<string, Bucket>();
  private lastSweep = 0;
  private size: number;
  private perMinute: number;
  private now: () => number;

  // Plain fields, not parameter properties: npm test runs this file with Node's type stripping, which lacks them.
  constructor(size: number, perMinute: number, now: () => number = Date.now) {
    this.size = size;
    this.perMinute = perMinute;
    this.now = now;
  }

  private level(b: Bucket, t: number): number {
    return Math.min(this.size, b.tokens + ((t - b.at) / 60_000) * this.perMinute);
  }

  /** Takes a token for `key`: 0 if there was one, otherwise the whole seconds until there will be. */
  take(key: string): number {
    if (this.size <= 0 || this.perMinute <= 0) return 0; // off
    const t = this.now();
    this.sweep(t);
    const b = this.buckets.get(key) ?? { tokens: this.size, at: t };
    const tokens = this.level(b, t);
    if (tokens >= 1) {
      this.buckets.set(key, { tokens: tokens - 1, at: t });
      return 0;
    }
    this.buckets.set(key, { tokens, at: t });
    return Math.max(1, Math.ceil(((1 - tokens) * 60) / this.perMinute));
  }

  /** Gives back a token taken by take() (for a request refused by a later check). */
  refund(key: string): void {
    const b = this.buckets.get(key);
    if (b) b.tokens = Math.min(this.size, b.tokens + 1);
  }

  private sweep(t: number): void {
    if (t - this.lastSweep < 60_000) return;
    this.lastSweep = t;
    for (const [key, b] of this.buckets) if (this.level(b, t) >= this.size) this.buckets.delete(key);
  }
}

/** How many requests each key has in flight, up to `max`. */
export class InFlight {
  private counts = new Map<string, number>();
  private max: number;

  constructor(max: number) {
    this.max = max;
  }

  /** Counts a request for `key` and returns the function that ends it, or null when `key` is at the limit. */
  acquire(key: string): (() => void) | null {
    if (this.max <= 0) return () => {}; // off
    const n = this.counts.get(key) ?? 0;
    if (n >= this.max) return null;
    this.counts.set(key, n + 1);
    let done = false;
    return () => {
      if (done) return;
      done = true;
      const left = (this.counts.get(key) ?? 1) - 1;
      if (left > 0) this.counts.set(key, left);
      else this.counts.delete(key);
    };
  }

  count(key: string): number {
    return this.counts.get(key) ?? 0;
  }
}

export type Verdict = { ok: true; release: () => void } | { ok: false; retryAfterS: number };

/** The limits for every request of the process. */
export class RateLimiter {
  private all: TokenBuckets;
  private slow: TokenBuckets;
  private inFlight: InFlight;
  private downloads: InFlight;

  constructor(limits: Limits = limitsFromEnv(), now: () => number = Date.now) {
    this.all = new TokenBuckets(limits.burst, limits.perMinute, now);
    this.slow = new TokenBuckets(limits.slowBurst, limits.slowPerMinute, now);
    this.inFlight = new InFlight(limits.slowConcurrent);
    this.downloads = new InFlight(limits.downloadConcurrent ?? DEFAULT_LIMITS.downloadConcurrent);
  }

  /** Whether a request from `ip` may go ahead (`kind`: see RequestKind; true and false mean slow and fast). When it
   *  may, `release` must be called once the backend has finished with it. A request with no known address isn't
   *  limited (it can only come from inside the server's own network). */
  check(ip: string, kind: RequestKind | boolean): Verdict {
    if (!ip) return { ok: true, release: () => {} };
    const k: RequestKind = kind === true ? "slow" : kind === false ? "fast" : kind;
    const wait = this.all.take(ip);
    if (wait) return { ok: false, retryAfterS: wait };
    if (k === "download") {
      const release = this.downloads.acquire(ip);
      return release ? { ok: true, release } : { ok: false, retryAfterS: 10 };
    }
    if (k === "fast") return { ok: true, release: () => {} };
    const slowWait = this.slow.take(ip);
    if (slowWait) return { ok: false, retryAfterS: slowWait };
    const release = this.inFlight.acquire(ip);
    if (!release) {
      this.slow.refund(ip); // not run, so it shouldn't count against the rate as well
      return { ok: false, retryAfterS: 2 };
    }
    return { ok: true, release };
  }
}
