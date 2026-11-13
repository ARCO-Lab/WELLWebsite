// Unit tests for src/lib/exportJob.ts, which the Download button waits on queued exports with.  npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ExportError, ExportStopped, NetworkError, JOB_FAILED_MESSAGE, POLL_RETRY_DELAYS_S, pollUntilReady, request, sleep,
} from "../src/lib/exportJob.ts";

const json = (body, status = 200) => new Response(JSON.stringify(body), { status });

// A fetch that answers status checks from a list, recording the URLs asked for.
function scripted(replies) {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    const next = replies.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  return { fetchImpl, calls };
}

const noWait = async () => {};

test("polls until the job is ready, reporting progress", async () => {
  const { fetchImpl, calls } = scripted([
    json({ status: "queued" }), json({ status: "running", progress_pct: 42.25 }), json({ status: "ready" }),
  ]);
  const seen = [];
  await pollUntilReady("job 1", 3, { fetchImpl, signal: new AbortController().signal, onStatus: (t) => seen.push(t), wait: noWait });
  assert.equal(calls.length, 3);
  assert.equal(calls[0], "/api/exports/jobs/job%201");
  assert.deepEqual(seen, ["Preparing export (queued)", "Preparing export (running 42.3%)", "Preparing export (ready)"]);
});

test("a 502 or a dropped connection is retried; a failed job is final", async () => {
  const { fetchImpl } = scripted([json({}, 502), new TypeError("offline"), json({ status: "failed" })]);
  const seen = [];
  await assert.rejects(
    pollUntilReady("j", 1, { fetchImpl, signal: new AbortController().signal, onStatus: (t) => seen.push(t), wait: noWait }),
    (e) => e instanceof ExportError && e.message === JOB_FAILED_MESSAGE && e.jobGone,
  );
  assert.deepEqual(seen.slice(0, 2), ["Reconnecting", "Reconnecting"]);
});

test("gives up after the last retry, and a 404 means the job is gone", async () => {
  const many = Array.from({ length: POLL_RETRY_DELAYS_S.length + 1 }, () => new TypeError("offline"));
  await assert.rejects(
    pollUntilReady("j", 1, { fetchImpl: scripted(many).fetchImpl, signal: new AbortController().signal, onStatus() {}, wait: noWait }),
    (e) => e instanceof NetworkError && !e.jobGone,
  );
  await assert.rejects(
    pollUntilReady("j", 1, { fetchImpl: scripted([json({ error: "No such job" }, 404)]).fetchImpl, signal: new AbortController().signal, onStatus() {}, wait: noWait }),
    (e) => e instanceof ExportError && e.message === "No such job" && e.jobGone,
  );
});

test("stops polling as soon as it is aborted (the Download button left the page)", async () => {
  const controller = new AbortController();
  let checks = 0;
  const fetchImpl = async () => { checks++; return json({ status: "running", progress_pct: 1 }); };
  const polling = pollUntilReady("j", 1, { fetchImpl, signal: controller.signal, onStatus() {} }); // the real sleep
  await new Promise((r) => setTimeout(r, 50)); // first check done, now waiting a second before the next
  controller.abort();
  await assert.rejects(polling, ExportStopped);
  const after = checks;
  await new Promise((r) => setTimeout(r, 1200));
  assert.equal(checks, after, "no status check after the abort");
  assert.equal(after, 1);
});

test("an aborted request is ExportStopped, a failed one NetworkError", async () => {
  const controller = new AbortController();
  controller.abort();
  const failing = async () => { throw new TypeError("network"); };
  await assert.rejects(request(failing, "/x", {}, controller.signal), ExportStopped);
  await assert.rejects(request(failing, "/x", {}), NetworkError);
  await assert.rejects(sleep(5, controller.signal), ExportStopped);
});
