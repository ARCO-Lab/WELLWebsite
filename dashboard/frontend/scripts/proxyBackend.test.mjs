// Tests for src/lib/proxyBackend.ts against a real local HTTP "backend" and a real proxy server, with Node's
// built-in test runner:   npm test
// The first test is the crash Sentry reported on /api/series: a browser reading slowly while the backend (gunicorn,
// which closes the connection after every response) finishes. With fetch on Node 22 that killed the server with
// an uncaught `AssertionError: assert(!this.paused)`.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { proxyToBackend } from "../src/lib/proxyBackend.ts";

const SIZE = 4 * 1024 * 1024; // well above the socket and stream buffers, so the proxy has to pause
const CHUNK = Buffer.alloc(64 * 1024, "x");

let backend;
let backendUrl;
const backendEvents = []; // what the backend saw, per request: "finished" or "closed early"
const backendRequests = [];

// Sends SIZE bytes like gunicorn: Content-Length, then the connection is closed. /break stops half way.
function backendHandler(req, res) {
  let posted = "";
  req.on("data", (d) => (posted += d));
  req.on("end", () => {
    backendRequests.push({ url: req.url, method: req.method, headers: req.headers, body: posted });
    if (req.url === "/bad-request") {
      res.writeHead(400, { "content-type": "application/json", connection: "close" });
      return res.end(JSON.stringify({ error: "start must be before end" }));
    }
    res.writeHead(200, { "content-type": "application/json", "content-length": SIZE, connection: "close" });
    res.on("close", () => backendEvents.push(res.writableFinished ? "finished" : "closed early"));
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
async function startProxy(path, init) {
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
  return { server, url: `http://127.0.0.1:${server.address().port}` };
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

// GET url; the body isn't read for pauseMs, then is read in full (or the request is dropped when abort is set).
function get(url, { pauseMs = 0, abort = false } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      res.pause();
      setTimeout(() => {
        if (abort) {
          req.destroy();
          return resolve({ status: res.statusCode, aborted: true });
        }
        const parts = [];
        res.on("data", (d) => parts.push(d));
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

after(() => backend.close());

test("a slow browser gets the whole body when the backend closes the connection (no crash)", async () => {
  const { server, url } = await startProxy("/series");
  const errors = await captureErrors(async () => {
    for (let i = 0; i < 8; i++) {
      const result = await get(url, { pauseMs: 150 });
      assert.equal(result.status, 200);
      assert.equal(result.body.length, SIZE);
    }
  });
  assert.deepEqual(errors, []);
  server.close();
});

test("a browser leaving mid-body stops the backend request and logs nothing", async () => {
  const { server, url } = await startProxy("/series");
  backendEvents.length = 0;
  const errors = await captureErrors(async () => {
    const result = await get(url, { pauseMs: 100, abort: true });
    assert.equal(result.aborted, true);
    await waitFor(() => backendEvents.length > 0);
  });
  assert.deepEqual(backendEvents, ["closed early"]);
  assert.deepEqual(errors, []);
  server.close();
});

test("a backend that breaks off mid-body is logged and the response is cut short", async () => {
  const { server, url } = await startProxy("/break");
  let result;
  const errors = await captureErrors(async () => {
    result = await get(url);
  });
  assert.equal(result.status, 200);
  assert.ok(result.error || result.body.length < SIZE, "the browser must not see a complete response");
  assert.equal(errors.length, 1);
  assert.match(errors[0], /Backend response for test broke off/);
  server.close();
});

test("an unreachable backend is a 502 with a message, and is logged", async () => {
  const { server, url } = await startProxy("/series");
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
  server.close();
});

test("the backend's status, body and headers pass through; POST bodies and X-Forwarded-For are sent", async () => {
  const { server, url } = await startProxy("/bad-request", {
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
  server.close();
});
