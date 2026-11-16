// Tests for src/lib/rateLimit.ts, with a fake clock:   npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ClientCounter, DEFAULT_LIMITS, InFlight, RateLimiter, TokenBuckets, isSlow, limitsFromEnv, requestKind,
} from "../src/lib/rateLimit.ts";

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
  assert.ok(isSlow("/api/samples?start=x&end=y"));
  assert.ok(!isSlow("/api/series?start=x&end=y&bucket=600&series=a"), "chart tiles are mostly cached");
  assert.ok(isSlow("/api/series?start=x&end=y&group_type=Weather"), "any other range is an aggregate over all of it");
  assert.ok(isSlow("/api/series?start=x&bucket=&group_type=Weather"), "an empty bucket is no bucket");
  assert.ok(!isSlow("/api/latest"));
  assert.ok(!isSlow("/health/data"));
});

test("an export download is its own kind of request", () => {
  assert.equal(requestKind("/api/exports/jobs/0b7e2c1e-0000-4000-8000-000000000001/download"), "download");
  assert.equal(requestKind("/api/exports/jobs/x/download", "POST"), "fast");
  assert.equal(requestKind("/api/exports/jobs/x"), "fast");
  assert.equal(requestKind("/api/windrose?start=x"), "slow");
});

test("an address may have only so many downloads in flight, apart from its slow requests", () => {
  const limiter = new RateLimiter({ ...DEFAULT_LIMITS, slowConcurrent: 1, downloadConcurrent: 2 }, clock().now);
  const first = limiter.check("a", "download");
  const second = limiter.check("a", "download");
  assert.ok(first.ok && second.ok);
  assert.deepEqual(limiter.check("a", "download"), { ok: false, retryAfterS: 10 });
  assert.ok(limiter.check("b", "download").ok, "another address still passes");
  assert.ok(limiter.check("a", "slow").ok, "downloads don't use up the slow requests' places");
  first.release();
  assert.ok(limiter.check("a", "download").ok);
});

test("by default one address may hold at most half of the backend's 12 threads with slow requests", () => {
  assert.equal(DEFAULT_LIMITS.slowConcurrent, 6);
  const limiter = new RateLimiter(DEFAULT_LIMITS, clock().now);
  for (let i = 0; i < 6; i++) assert.ok(limiter.check("a", true).ok);
  assert.equal(limiter.check("a", true).ok, false);
});

test("limits can be set from the environment; bad values keep the default", () => {
  assert.deepEqual(limitsFromEnv({}), DEFAULT_LIMITS);
  const limits = limitsFromEnv({ RATE_LIMIT_BURST: "50", RATE_LIMIT_SLOW_CONCURRENT: "0", RATE_LIMIT_PER_MINUTE: "lots",
    RATE_LIMIT_DOWNLOAD_CONCURRENT: "3" });
  assert.equal(limits.burst, 50);
  assert.equal(limits.slowConcurrent, 0);
  assert.equal(limits.downloadConcurrent, 3);
  assert.equal(limits.perMinute, DEFAULT_LIMITS.perMinute);
});

test("the address counter logs counts, never addresses, at most once per window", () => {
  const c = new ClientCounter(0, 600_000);
  assert.equal(c.record("198.51.100.7", 1_000), null);
  assert.equal(c.record("198.51.100.7", 2_000), null);
  assert.equal(c.record("198.51.100.8", 3_000), null);
  const line = c.record("198.51.100.9", 600_000);
  assert.equal(line, "[client-ip] 2 different client addresses in 3 API requests over the last 10 min");
  assert.ok(!/198\.51/.test(line));
  assert.equal(c.record("198.51.100.9", 600_001), null, "the next window has only just started");
  const capped = new ClientCounter(0, 1000, 2);
  for (const ip of ["a", "b", "c"]) capped.record(ip, 1);
  assert.match(capped.record("d", 1000), /^\[client-ip\] 2\+ different/);
});
