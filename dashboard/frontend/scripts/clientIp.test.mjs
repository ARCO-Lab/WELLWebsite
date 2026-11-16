// Tests for src/lib/clientIp.ts: which address a request counts as, which every per-visitor limit (lib/rateLimit.ts
// and the backend's export quota) depends on.   npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import { clientIp, logClientIpSample, trustedProxies } from "../src/lib/clientIp.ts";

const req = (peer, xff) => ({ socket: { remoteAddress: peer }, headers: xff === undefined ? {} : { "x-forwarded-for": xff } });
const PROXIES = trustedProxies("130.113.68.30, 10.0.0.2");

test("a request from an address that isn't a trusted proxy is that address, whatever X-Forwarded-For says", () => {
  assert.equal(clientIp(req("203.0.113.5", "198.51.100.7"), PROXIES), "203.0.113.5");
  assert.equal(clientIp(req("::ffff:203.0.113.5", "198.51.100.7"), PROXIES), "203.0.113.5", "IPv4 on an IPv6 socket");
  assert.equal(clientIp(req("203.0.113.5"), PROXIES), "203.0.113.5");
});

test("through a trusted proxy, the client is the rightmost hop that isn't a trusted proxy", () => {
  assert.equal(clientIp(req("130.113.68.30", "198.51.100.7"), PROXIES), "198.51.100.7");
  assert.equal(clientIp(req("::ffff:130.113.68.30", "198.51.100.7"), PROXIES), "198.51.100.7");
  // What the browser sent itself is to the left, and is never taken
  assert.equal(clientIp(req("130.113.68.30", "6.6.6.6, 198.51.100.7"), PROXIES), "198.51.100.7");
  // Two proxies in a row, each appending what it saw: the trusted hops on the right are skipped
  assert.equal(clientIp(req("10.0.0.2", "6.6.6.6, 198.51.100.7, 130.113.68.30"), PROXIES), "198.51.100.7");
  // The header sent twice counts as one list, in order
  assert.equal(clientIp(req("130.113.68.30", ["6.6.6.6", "198.51.100.7"]), PROXIES), "198.51.100.7");
  assert.equal(clientIp(req("130.113.68.30", " 198.51.100.7 ,, "), PROXIES), "198.51.100.7", "spaces and empty hops");
});

test("a trusted proxy with no client in X-Forwarded-For is the client itself", () => {
  assert.equal(clientIp(req("130.113.68.30"), PROXIES), "130.113.68.30");
  assert.equal(clientIp(req("130.113.68.30", ""), PROXIES), "130.113.68.30");
  assert.equal(clientIp(req("10.0.0.2", "130.113.68.30"), PROXIES), "130.113.68.30", "every hop a trusted proxy");
});

test("with no trusted proxies, X-Forwarded-For is never believed", () => {
  assert.equal(clientIp(req("130.113.68.30", "198.51.100.7"), trustedProxies("")), "130.113.68.30");
  assert.deepEqual([...trustedProxies(" ::ffff:10.0.0.2 ,,130.113.68.30 ")], ["10.0.0.2", "130.113.68.30"]);
});

test("a request with no known peer address has none", () => {
  assert.equal(clientIp({ socket: {}, headers: { "x-forwarded-for": "198.51.100.7" } }, PROXIES), "");
});

test("the sample log line is written at most every 10 minutes", () => {
  const { info } = console;
  const lines = [];
  console.info = (line) => lines.push(line);
  try {
    const t = 4e12; // later than any sample logged by another test in this process
    assert.equal(logClientIpSample(req("203.0.113.5"), "203.0.113.5", t), true);
    assert.equal(logClientIpSample(req("203.0.113.5"), "203.0.113.5", t + 60_000), false);
    assert.equal(logClientIpSample(req("203.0.113.5"), "203.0.113.5", t + 10 * 60_000), true);
  } finally {
    console.info = info;
  }
  assert.equal(lines.length, 2);
  assert.match(lines[0], /^\[client-ip\] connection=203\.0\.113\.5 x-forwarded-for=- trusted=.* chosen=203\.0\.113\.5$/);
});
