// Tests for src/lib/rateLimit.ts, with a fake clock:   npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_LIMITS, InFlight, RateLimiter, TokenBuckets, isSlow, limitsFromEnv } from "../src/lib/rateLimit.ts";

function clock(start = 1_000_000) {
  const c = { t: start, now: () => c.t };
  return c;
}

test("a bucket allows a burst, then refills at its rate", () => {
  const c = clock();
  const b = new TokenBuckets(3, 6, c.now); // 3 at once, one every 10 s
  assert.deepEqual([b.take("a"), b.take("a"), b.take("a")], [0, 0, 0]);
  assert.equal(b.take("a"), 10); // seconds until the next token
  assert.equal(b.take("b"), 0, "another address has its own bucket");
  c.t += 5_000;
  assert.equal(b.take("a"), 5);
  c.t += 5_000;
  assert.equal(b.take("a"), 0);
  c.t += 3_600_000;
  assert.deepEqual([b.take("a"), b.take("a"), b.take("a"), b.take("a") > 0], [0, 0, 0, true], "never more than its size");
});

test("a bucket of size 0 or rate 0 is off", () => {
  for (const b of [new TokenBuckets(0, 10), new TokenBuckets(10, 0)]) {
    for (let i = 0; i < 50; i++) assert.equal(b.take("a"), 0);
  }
});

test("in-flight counts are per key, and releasing twice counts once", () => {
  const f = new InFlight(2);
  const r1 = f.acquire("a");
  const r2 = f.acquire("a");
  assert.ok(r1 && r2);
  assert.equal(f.acquire("a"), null);
  assert.ok(f.acquire("b"));
  r1();
  r1();
  assert.equal(f.count("a"), 1);
  assert.ok(f.acquire("a"));
  assert.equal(f.acquire("a"), null);
});

test("slow requests have their own, smaller limits on top of the overall one", () => {
  const c = clock();
  const limiter = new RateLimiter({ burst: 100, perMinute: 100, slowBurst: 2, slowPerMinute: 1, slowConcurrent: 5 }, c.now);
  const a = limiter.check("198.51.100.7", true);
  const b = limiter.check("198.51.100.7", true);
  assert.ok(a.ok && b.ok);
  const refused = limiter.check("198.51.100.7", true);
  assert.deepEqual(refused, { ok: false, retryAfterS: 60 });
  assert.ok(limiter.check("198.51.100.7", false).ok, "fast requests still pass");
  assert.ok(limiter.check("198.51.100.8", true).ok, "another address still passes");
});

test("too many slow requests in flight are refused without using up the slow rate", () => {
  const limiter = new RateLimiter({ ...DEFAULT_LIMITS, slowBurst: 3, slowPerMinute: 1, slowConcurrent: 1 }, clock().now);
  const first = limiter.check("a", true);
  assert.ok(first.ok);
  assert.deepEqual(limiter.check("a", true), { ok: false, retryAfterS: 2 });
  first.release();
  assert.ok(limiter.check("a", true).ok);
  assert.ok(limiter.check("a", false).ok);
});

test("requests without an address aren't limited", () => {
  const limiter = new RateLimiter({ ...DEFAULT_LIMITS, burst: 1, perMinute: 1 }, clock().now);
  for (let i = 0; i < 5; i++) assert.ok(limiter.check("", true).ok);
});

test("which backend paths are slow", () => {
  assert.ok(isSlow("/api/windrose?start=x&end=y"));
  assert.ok(isSlow("/api/data?start=x"));
  assert.ok(isSlow("/api/exports/estimate", "POST"));
  assert.ok(isSlow("/api/exports/jobs", "post"));
  assert.ok(!isSlow("/api/exports/jobs/abc"), "polling a job is cheap");
  assert.ok(!isSlow("/api/series?start=x"));
  assert.ok(!isSlow("/api/latest"));
});

test("limits can be set from the environment; bad values keep the default", () => {
  assert.deepEqual(limitsFromEnv({}), DEFAULT_LIMITS);
  const limits = limitsFromEnv({ RATE_LIMIT_BURST: "50", RATE_LIMIT_SLOW_CONCURRENT: "0", RATE_LIMIT_PER_MINUTE: "lots" });
  assert.equal(limits.burst, 50);
  assert.equal(limits.slowConcurrent, 0);
  assert.equal(limits.perMinute, DEFAULT_LIMITS.perMinute);
});
