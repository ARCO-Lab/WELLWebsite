// Tests for src/pages/api/samples/validate.ts: the route must answer JSON for any input, never Next's bare
// text/HTML "Invalid JSON" / "Body exceeded ..." page (which the cross-origin WordPress checker, calling res.json(),
// reads as "the checker couldn't read that one"). These cover the body-parsing paths that return before the backend
// is called; the wrong-format CSV -> problems path is covered by the backend's tests/test_sampling_route.py.   npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import handler from "../src/pages/api/samples/validate.ts";

// A fake request: method, headers, and a body delivered as the async iteration the handler reads (Next hands the
// route the raw Node stream when bodyParser is off).
function fakeReq(method, body, headers = {}) {
  const chunks = body == null ? [] : [Buffer.from(body)];
  return {
    method,
    headers,
    async *[Symbol.asyncIterator]() {
      for (const chunk of chunks) yield chunk;
    },
  };
}

// A fake response that records the status, the JSON body, and headers, like the real NextApiResponse.
function fakeRes() {
  return {
    headers: {},
    statusCode: null,
    body: undefined,
    ended: false,
    setHeader(name, value) {
      this.headers[name.toLowerCase()] = value;
    },
    getHeader(name) {
      return this.headers[name.toLowerCase()];
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(payload) {
      this.body = payload;
      this.ended = true;
      return this;
    },
    end() {
      this.ended = true;
      return this;
    },
  };
}

test("a non-POST method is a JSON 405 with an Allow header", async () => {
  const res = fakeRes();
  await handler(fakeReq("GET"), res);
  assert.equal(res.statusCode, 405);
  assert.deepEqual(res.body, { error: "Method not allowed" });
  assert.equal(res.getHeader("allow"), "POST, OPTIONS");
});

test("a malformed JSON body is a JSON 400, not Next's bare 'Invalid JSON'", async () => {
  const res = fakeRes();
  // What a naive client string-building JSON around a CSV would send: a raw newline and quote break the JSON.
  await handler(fakeReq("POST", '{"csv":"a,b\nc,"d"}', { "content-type": "application/json" }), res);
  assert.equal(res.statusCode, 400);
  assert.match(res.body.error, /Send the CSV as JSON/);
});

test("a body that is not JSON at all is a JSON 400", async () => {
  const res = fakeRes();
  await handler(fakeReq("POST", "ID,Timestamp,Group\n1,2026-10-01,Weather", { "content-type": "application/json" }), res);
  assert.equal(res.statusCode, 400);
  assert.match(res.body.error, /Send the CSV as JSON/);
});

test("an empty body asks for a CSV (JSON 400), not a parse error", async () => {
  const res = fakeRes();
  await handler(fakeReq("POST", "", { "content-type": "application/json" }), res);
  assert.equal(res.statusCode, 400);
  assert.match(res.body.error, /Paste your CSV/);
});

test("a body whose csv is not a string is a JSON 400", async () => {
  const res = fakeRes();
  await handler(fakeReq("POST", '{"csv":123}', { "content-type": "application/json" }), res);
  assert.equal(res.statusCode, 400);
  assert.match(res.body.error, /Paste your CSV/);
});

test("an oversized body is a JSON 413, not Next's bare 'Body exceeded ... limit'", async () => {
  const res = fakeRes();
  const huge = "x".repeat(3_000_001);
  await handler(fakeReq("POST", huge, { "content-type": "application/json" }), res);
  assert.equal(res.statusCode, 413);
  assert.match(res.body.error, /too large to check here/);
});
