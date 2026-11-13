// Tests for src/lib/proxyBackend.ts against a real local HTTP "backend" and a real proxy server, with Node's
// built-in test runner:   npm test
// The first test is the crash Sentry reported on /api/series: a browser reading slowly while the backend finishes
// and closes the connection (as gunicorn does when a worker restarts or an idle connection times out). With fetch
// on Node 22 that killed the server with an uncaught `AssertionError: assert(!this.paused)`.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { proxyToBackend, setRateLimiter } from "../src/lib/proxyBackend.ts";
import { DEFAULT_LIMITS, RateLimiter } from "../src/lib/rateLimit.ts";

const SIZE = 4 * 1024 * 1024; // more than the proxy's stream buffers, so a slow browser makes it pause reading
const CHUNK = Buffer.alloc(64 * 1024, "x");

let backend;
let backendUrl;
const backendEvents = []; // what the backend saw, per request: "finished" or "closed early"
const backendRequests = [];

// Sends SIZE bytes with Content-Length, then closes the connection (the case that crashed fetch). /break stops
// half way, /endless sends a chunk every few milliseconds until the connection is closed, and a path with
// ?work=<ms> works that long before it answers {} (like Flask running a query, which can't notice the browser left).
const answered = []; // the ?work= requests the backend has answered, in order
function backendHandler(req, res) {
  let posted = "";
  req.on("data", (d) => (posted += d));
  req.on("end", () => {
    backendRequests.push({ url: req.url, method: req.method, headers: req.headers, body: posted });
    if (req.url === "/bad-request") {
      res.writeHead(400, { "content-type": "application/json", connection: "close" });
      return res.end(JSON.stringify({ error: "start must be before end" }));
    }
    const work = new URL(req.url, "http://x").searchParams.get("work");
    if (work) {
      res.on("close", () => backendEvents.push(res.writableFinished ? "finished" : "closed early"));
      return setTimeout(() => {
        answered.push(req.url);
        res.writeHead(200, { "content-type": "application/json", "content-length": 2, connection: "close" });
        res.end("{}");
      }, Number(work));
    }
    res.on("close", () => backendEvents.push(res.writableFinished ? "finished" : "closed early"));
    if (req.url === "/endless") {
      res.writeHead(200, { "content-type": "application/json", connection: "close" });
      const timer = setInterval(() => res.write(CHUNK), 5);
      return res.on("close", () => clearInterval(timer));
    }
    res.writeHead(200, { "content-type": "application/json", "content-length": SIZE, connection: "close" });
    let sent = 0;
    (function write() {
      while (sent < SIZE) {
        if (req.url === "/break" && sent >= SIZE / 2) return res.destroy();
        sent += CHUNK.length;
        if (!res.write(CHUNK)) return res.once("drain", write);
      }
      res.end();
    })();
  });
}

// A proxy server that runs proxyToBackend the way the API routes do, with Next's res.status/res.json added.
// The server is closed when the test ends, even if it fails.
async function startProxy(t, path, init) {
  const server = http.createServer((req, res) => {
    res.status = (code) => {
      res.statusCode = code;
      return res;
    };
    res.json = (value) => {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify(value));
    };
    proxyToBackend(req, res, path, init, "test");
  });
  server.listen(0);
  await once(server, "listening");
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  return `http://127.0.0.1:${server.address().port}`;
}

// Collects console.error calls (and silences the sampled [client-ip] log lines) while fn runs.
async function captureErrors(fn) {
  const errors = [];
  const { error, log } = console;
  console.error = (...args) => errors.push(args.map(String).join(" "));
  console.log = () => {};
  try {
    await fn();
  } finally {
    console.error = error;
    console.log = log;
  }
  return errors;
}

// GET url; the body isn't read for pauseMs, then is read in full, waiting slowMs after each chunk (or the request
// is dropped when abort is set).
function get(url, { pauseMs = 0, slowMs = 0, abort = false } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      res.pause();
      setTimeout(() => {
        if (abort) {
          req.destroy();
          return resolve({ status: res.statusCode, aborted: true });
        }
        const parts = [];
        res.on("data", (d) => {
          parts.push(d);
          if (slowMs) {
            res.pause();
            setTimeout(() => res.resume(), slowMs);
          }
        });
        res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(parts) }));
        res.on("error", (error) => resolve({ status: res.statusCode, error, body: Buffer.concat(parts) }));
        res.resume();
      }, pauseMs);
    });
    req.on("error", (error) => (abort ? resolve({ aborted: true }) : reject(error)));
  });
}

const waitFor = async (check) => {
  for (let i = 0; i < 200 && !check(); i++) await new Promise((r) => setTimeout(r, 10));
};

before(async () => {
  backend = http.createServer(backendHandler);
  backend.listen(0);
  await once(backend, "listening");
  backendUrl = `http://127.0.0.1:${backend.address().port}`;
  process.env.FLASK_API_URL = backendUrl;
});

after(() => {
  backend.closeAllConnections();
  backend.close();
});

test("a slow browser gets the whole body when the backend closes the connection (no crash)", async (t) => {
  const url = await startProxy(t, "/series");
  const errors = await captureErrors(async () => {
    for (let i = 0; i < 6; i++) {
      const result = await get(url, { pauseMs: 100, slowMs: 1 });
      assert.equal(result.status, 200);
      assert.equal(result.body.length, SIZE);
    }
  });
  assert.deepEqual(errors, []);
});

test("a browser leaving mid-body stops the backend request and logs nothing", async (t) => {
  const url = await startProxy(t, "/endless");
  backendEvents.length = 0;
  const errors = await captureErrors(async () => {
    const result = await get(url, { pauseMs: 100, abort: true });
    assert.equal(result.aborted, true);
    await waitFor(() => backendEvents.length > 0);
  });
  assert.deepEqual(backendEvents, ["closed early"]);
  assert.deepEqual(errors, []);
});

test("a backend that breaks off mid-body is logged and the response is cut short", async (t) => {
  const url = await startProxy(t, "/break");
  let result;
  const errors = await captureErrors(async () => {
    result = await get(url);
  });
  assert.equal(result.status, 200);
  assert.ok(result.error || result.body.length < SIZE, "the browser must not see a complete response");
  assert.equal(errors.length, 1);
  assert.match(errors[0], /Backend response for test broke off/);
});

test("an unreachable backend is a 502 with a message, and is logged", async (t) => {
  const url = await startProxy(t, "/series");
  const closed = http.createServer();
  closed.listen(0);
  await once(closed, "listening");
  const port = closed.address().port;
  closed.close();
  await once(closed, "close");
  process.env.FLASK_API_URL = `http://127.0.0.1:${port}`;
  let result;
  const errors = await captureErrors(async () => {
    result = await get(url);
  });
  process.env.FLASK_API_URL = backendUrl;
  assert.equal(result.status, 502);
  assert.match(result.body.toString(), /didn't respond/);
  assert.equal(errors.length, 1);
  assert.match(errors[0], /Failed to reach the Flask backend for test/);
});

test("the backend's status, body and headers pass through; POST bodies and X-Forwarded-For are sent", async (t) => {
  const url = await startProxy(t, "/bad-request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start: "é" }),
  });
  backendRequests.length = 0;
  let result;
  const errors = await captureErrors(async () => {
    result = await get(url);
  });
  assert.equal(result.status, 400);
  assert.equal(result.headers["content-type"], "application/json");
  assert.deepEqual(JSON.parse(result.body.toString()), { error: "start must be before end" });
  const [sent] = backendRequests;
  assert.equal(sent.method, "POST");
  assert.equal(sent.body, '{"start":"é"}');
  assert.equal(sent.headers["content-type"], "application/json");
  assert.equal(sent.headers["x-forwarded-for"], "127.0.0.1");
  assert.deepEqual(errors, []);
});

test("an invalid FLASK_API_URL is a 502 with a message, and is logged", async (t) => {
  const url = await startProxy(t, "/series");
  process.env.FLASK_API_URL = "not a url";
  let result;
  const errors = await captureErrors(async () => {
    result = await get(url);
  });
  process.env.FLASK_API_URL = backendUrl;
  assert.equal(result.status, 502);
  assert.match(result.body.toString(), /didn't respond/);
  assert.equal(errors.length, 1);
  assert.match(errors[0], /^\[ERROR\] Failed to reach the Flask backend for test/);
});

test("connections to a keep-alive backend (like gunicorn's --keep-alive) are reused", async (t) => {
  // Answers with Content-Length and leaves the connection open, and records which socket each request came on.
  const sockets = [];
  const keepAlive = http.createServer((req, res) => {
    sockets.push(req.socket);
    res.writeHead(200, { "content-type": "application/json", "content-length": 2 });
    res.end("{}");
  });
  keepAlive.listen(0);
  await once(keepAlive, "listening");
  t.after(() => {
    keepAlive.closeAllConnections();
    keepAlive.close();
  });
  const url = await startProxy(t, "/latest");
  process.env.FLASK_API_URL = `http://127.0.0.1:${keepAlive.address().port}`;
  const results = [];
  const errors = await captureErrors(async () => {
    results.push(await get(url));
    results.push(await get(url));
  });
  process.env.FLASK_API_URL = backendUrl;
  for (const result of results) {
    assert.equal(result.status, 200);
    assert.equal(result.body.toString(), "{}");
  }
  assert.equal(sockets.length, 2);
  assert.equal(sockets[0], sockets[1], "the second request must reuse the first connection");
  assert.deepEqual(errors, []);
});

test("an address over the rate limit gets a 429 with Retry-After, and the backend isn't called", async (t) => {
  setRateLimiter(new RateLimiter({ ...DEFAULT_LIMITS, burst: 2, perMinute: 1 }));
  t.after(() => setRateLimiter(null));
  const url = await startProxy(t, "/bad-request");
  const seen = backendRequests.length;
  const results = [];
  await captureErrors(async () => {
    for (let i = 0; i < 3; i++) results.push(await get(url));
  });
  assert.deepEqual(results.map((r) => r.status), [400, 400, 429]);
  assert.equal(results[2].headers["retry-after"], "60");
  assert.match(JSON.parse(results[2].body.toString()).error, /Too many requests/);
  assert.equal(backendRequests.length, seen + 2);
});

test("an address may have only so many slow requests in flight; a finished one frees its place", async (t) => {
  setRateLimiter(new RateLimiter({ ...DEFAULT_LIMITS, slowConcurrent: 1 }));
  t.after(() => setRateLimiter(null));
  const url = await startProxy(t, "/api/windrose?start=a&end=b");
  await captureErrors(async () => {
    const seen = backendRequests.length;
    const first = get(url, { pauseMs: 300 }); // its 4 MB body is still being sent while the next one asks
    await waitFor(() => backendRequests.length > seen);
    const second = await get(url);
    assert.equal(second.status, 429);
    assert.equal(second.headers["retry-after"], "2");
    assert.equal((await first).status, 200);
    await new Promise((r) => setTimeout(r, 50)); // the proxy sees its response close just after the browser has it
    assert.equal((await get(url)).status, 200);
  });
});

// Sends a GET and drops it after `ms`, before any answer has arrived.
function dropAfter(url, ms) {
  return new Promise((resolve) => {
    const req = http.get(url, () => {});
    req.on("error", () => {});
    setTimeout(() => {
      req.destroy();
      resolve();
    }, ms);
  });
}

test("a slow request dropped by the browser keeps its place until the backend has answered", async (t) => {
  // The backend can't tell the browser left while it works, so dropping requests must not free their places
  setRateLimiter(new RateLimiter({ ...DEFAULT_LIMITS, slowConcurrent: 1 }));
  t.after(() => setRateLimiter(null));
  const url = await startProxy(t, "/api/data?work=400");
  answered.length = 0;
  const errors = await captureErrors(async () => {
    await dropAfter(url, 50);
    const refused = await get(url);
    assert.equal(refused.status, 429, "the dropped request's backend work is still going on");
    await waitFor(() => answered.length === 1);
    await new Promise((r) => setTimeout(r, 50)); // the proxy drops the answer nobody is waiting for
    assert.equal((await get(url)).status, 200, "its place is free once the backend has answered");
  });
  assert.deepEqual(errors, []);
});

test("a dropped request's backend work is let finish, not cut off, and is answered to nobody", async (t) => {
  const url = await startProxy(t, "/api/data?work=150&n=2");
  answered.length = 0;
  backendEvents.length = 0;
  const errors = await captureErrors(async () => {
    await dropAfter(url, 30);
    await waitFor(() => backendEvents.length === 1);
  });
  assert.deepEqual(answered, ["/api/data?work=150&n=2"]);
  assert.deepEqual(backendEvents, ["finished"], "the backend's connection stays open until it has answered");
  assert.deepEqual(errors, []);
});

test("an address may have only so many export downloads in flight", async (t) => {
  setRateLimiter(new RateLimiter({ ...DEFAULT_LIMITS, downloadConcurrent: 1 }));
  t.after(() => setRateLimiter(null));
  const url = await startProxy(t, "/api/exports/jobs/00000000-0000-4000-8000-000000000001/download");
  await captureErrors(async () => {
    const seen = backendRequests.length;
    const first = get(url, { pauseMs: 300 }); // its 4 MB body is still being sent while the next one asks
    await waitFor(() => backendRequests.length > seen);
    const second = await get(url);
    assert.equal(second.status, 429);
    assert.equal(second.headers["retry-after"], "10");
    assert.equal((await first).status, 200);
    await new Promise((r) => setTimeout(r, 50));
    assert.equal((await get(url)).status, 200);
  });
});

test("a transfer still going after PROXY_BODY_MAX_MS is stopped, and the backend sees it end", async (t) => {
  process.env.PROXY_BODY_MAX_MS = "200";
  t.after(() => delete process.env.PROXY_BODY_MAX_MS);
  const url = await startProxy(t, "/endless");
  backendEvents.length = 0;
  const warnings = [];
  const { warn } = console;
  console.warn = (...args) => warnings.push(args.map(String).join(" "));
  let result;
  try {
    const errors = await captureErrors(async () => {
      result = await get(url);
      await waitFor(() => backendEvents.length > 0);
    });
    assert.deepEqual(errors, []);
  } finally {
    console.warn = warn;
  }
  assert.equal(result.status, 200);
  assert.ok(result.error, "the browser must not see a complete response");
  assert.deepEqual(backendEvents, ["closed early"]);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /stopped: still sending after 0.2 s/);
});

test("a route can keep its own answer for an unreachable backend (the health check's 503)", async (t) => {
  const failure = { status: 503, body: { status: "error", error: "backend unreachable" } };
  const url = await startProxy(t, "/health/data", { failure });
  const closed = http.createServer();
  closed.listen(0);
  await once(closed, "listening");
  const port = closed.address().port;
  closed.close();
  await once(closed, "close");
  process.env.FLASK_API_URL = `http://127.0.0.1:${port}`;
  let result;
  const errors = await captureErrors(async () => {
    result = await get(url);
  });
  process.env.FLASK_API_URL = backendUrl;
  assert.equal(result.status, 503);
  assert.deepEqual(JSON.parse(result.body.toString()), failure.body);
  assert.equal(errors.length, 1, "still logged");
});
