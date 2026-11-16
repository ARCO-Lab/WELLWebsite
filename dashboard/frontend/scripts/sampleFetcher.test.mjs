// Unit tests for src/lib/sampleFetcher.ts (what useSampledData fetches with): only the newest selection's reply
// counts, whatever order the replies arrive in.  npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import { SampleFetcher } from "../src/lib/sampleFetcher.ts";

const row = (site) => ({ site_id: site, creek_id: "1", measurement_type: "pH", value: 7, unit: "", recorded_at: "2025-05-01T00:00:00" });

// A fetch whose replies are released by hand, in any order. Aborting a request rejects it, as the browser does.
function manualFetch() {
  const pending = new Map();
  const calls = [];
  const fetchImpl = (url, init) => new Promise((resolve, reject) => {
    calls.push(url);
    pending.set(url, resolve);
    init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });
  const reply = (url, body, status = 200) => pending.get(url)(new Response(JSON.stringify(body), { status }));
  return { fetchImpl, reply, calls };
}

test("a late reply to an older selection is dropped, and the newer one is shown", async () => {
  const { fetchImpl, reply } = manualFetch();
  const f = new SampleFetcher(fetchImpl);
  const first = f.load("a", "/a");
  const second = f.load("a+b", "/ab");
  reply("/ab", [row("2"), row("8")]); // the newer reply arrives first
  reply("/a", [row("2")]);
  assert.deepEqual(await second, { key: "a+b", data: [row("2"), row("8")], error: null });
  assert.equal(await first, null);
});

test("the older reply arriving first does not count either", async () => {
  const { fetchImpl, reply } = manualFetch();
  const f = new SampleFetcher(fetchImpl);
  const first = f.load("a", "/a");
  const second = f.load("b", "/b");
  reply("/a", [row("2")]);
  assert.equal(await first, null);
  reply("/b", [row("8")]);
  assert.equal((await second).key, "b");
});

test("replies are cached by selection, so going back to one needs no request", async () => {
  const { fetchImpl, reply, calls } = manualFetch();
  const f = new SampleFetcher(fetchImpl);
  const first = f.load("a", "/a");
  reply("/a", [row("2")]);
  await first;
  const again = await f.load("a", "/a");
  assert.deepEqual(again.data, [row("2")]);
  assert.equal(calls.length, 1);
});

test("an error reply gives the API's message, unless it was superseded", async () => {
  const { fetchImpl, reply } = manualFetch();
  const f = new SampleFetcher(fetchImpl);
  const failed = f.load("a", "/a");
  reply("/a", { error: "Invalid date range" }, 400);
  const result = await failed;
  assert.equal(result.data, null);
  assert.equal(result.error.message, "Invalid date range");

  const old = f.load("b", "/b");
  const next = f.load("c", "/c");
  reply("/b", { error: "boom" }, 500);
  reply("/c", []);
  assert.equal(await old, null);
  assert.deepEqual((await next).data, []);
});

test("cancel() drops the request in flight", async () => {
  const { fetchImpl } = manualFetch();
  const f = new SampleFetcher(fetchImpl);
  const pending = f.load("a", "/a");
  f.cancel();
  assert.equal(await pending, null);
});

test("the proxy's 429 for too many requests in flight is shown as its message, not as a failure code", async () => {
  // What lib/proxyBackend.ts answers when an address has too many slow requests (sampling rows count as slow)
  const { fetchImpl, reply } = manualFetch();
  const f = new SampleFetcher(fetchImpl);
  const loading = f.load("a", "/a");
  reply("/a", { error: "Too many requests from your address. Please wait a moment and try again." }, 429);
  const result = await loading;
  assert.equal(result.data, null);
  assert.equal(result.error.message, "Too many requests from your address. Please wait a moment and try again.");
});
