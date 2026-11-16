// Tests for src/lib/publicCors.ts: the CORS the sampling checker opens to the WordPress origin only, and the
// preflight it answers.   npm test

import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { handlePublicCors, allowedOrigins } from "../src/lib/publicCors.ts";

// A fake NextApiResponse that records headers, the status, and whether it was ended.
function fakeRes() {
  return {
    headers: {},
    statusCode: null,
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
    end() {
      this.ended = true;
      return this;
    },
  };
}

const req = (method, origin) => ({ method, headers: origin === undefined ? {} : { origin } });

afterEach(() => {
  delete process.env.WORDPRESS_ORIGIN;
});

test("a POST from the WordPress origin gets the CORS headers and is served", () => {
  const res = fakeRes();
  const handled = handlePublicCors(req("POST", "https://well.mcmaster.ca"), res);
  assert.equal(handled, false, "the caller should carry on");
  assert.equal(res.getHeader("access-control-allow-origin"), "https://well.mcmaster.ca");
  assert.equal(res.getHeader("access-control-allow-methods"), "POST, OPTIONS");
  assert.equal(res.getHeader("access-control-allow-headers"), "Content-Type");
  assert.equal(res.getHeader("vary"), "Origin");
  assert.equal(res.ended, false);
});

test("the www form of the WordPress origin is allowed too", () => {
  const res = fakeRes();
  handlePublicCors(req("POST", "https://www.well.mcmaster.ca"), res);
  assert.equal(res.getHeader("access-control-allow-origin"), "https://www.well.mcmaster.ca");
});

test("another origin gets no allow-origin header, so the browser blocks the read", () => {
  const res = fakeRes();
  const handled = handlePublicCors(req("POST", "https://evil.example.com"), res);
  assert.equal(handled, false);
  assert.equal(res.getHeader("access-control-allow-origin"), undefined);
  assert.equal(res.getHeader("vary"), "Origin");
});

test("an OPTIONS preflight from the WordPress origin is answered 204 with the headers", () => {
  const res = fakeRes();
  const handled = handlePublicCors(req("OPTIONS", "https://well.mcmaster.ca"), res);
  assert.equal(handled, true, "the caller must return");
  assert.equal(res.statusCode, 204);
  assert.equal(res.ended, true);
  assert.equal(res.getHeader("access-control-allow-origin"), "https://well.mcmaster.ca");
});

test("an OPTIONS preflight from another origin is answered 204 with no allow-origin", () => {
  const res = fakeRes();
  const handled = handlePublicCors(req("OPTIONS", "https://evil.example.com"), res);
  assert.equal(handled, true);
  assert.equal(res.statusCode, 204);
  assert.equal(res.getHeader("access-control-allow-origin"), undefined);
});

test("a request with no Origin header (server-to-server) is served without CORS headers", () => {
  const res = fakeRes();
  const handled = handlePublicCors(req("POST"), res);
  assert.equal(handled, false);
  assert.equal(res.getHeader("access-control-allow-origin"), undefined);
});

test("WORDPRESS_ORIGIN overrides the allowed origins", () => {
  process.env.WORDPRESS_ORIGIN = "https://staging.well.example , https://well.mcmaster.ca";
  assert.deepEqual(allowedOrigins(), ["https://staging.well.example", "https://well.mcmaster.ca"]);
  const res = fakeRes();
  handlePublicCors(req("POST", "https://staging.well.example"), res);
  assert.equal(res.getHeader("access-control-allow-origin"), "https://staging.well.example");
});

test("a custom GET+OPTIONS method list is reflected", () => {
  const res = fakeRes();
  handlePublicCors(req("GET", "https://well.mcmaster.ca"), res, "GET, OPTIONS");
  assert.equal(res.getHeader("access-control-allow-methods"), "GET, OPTIONS");
});
