// Unit tests for src/lib/earlyErrors.ts: errors thrown before Sentry loads are kept and reported once it has.
//   npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import { bufferEarlyErrors } from "../src/lib/earlyErrors.ts";

// An "error" event as the browser fires it (ErrorEvent isn't in Node), and an "unhandledrejection" one.
const errorEvent = (error, message = "") => Object.assign(new Event("error"), { error, message });
const rejection = (reason) => Object.assign(new Event("unhandledrejection"), { reason });

test("keeps uncaught errors and rejections, then reports them in order and stops listening", () => {
  const target = new EventTarget();
  const early = bufferEarlyErrors(target, 10);
  const boom = new Error("boom");
  target.dispatchEvent(errorEvent(boom));
  target.dispatchEvent(rejection("rejected"));
  target.dispatchEvent(errorEvent(undefined, "Script error.")); // cross-origin: a message only

  const captured = [];
  early.flush((e) => captured.push(e));
  assert.deepEqual(captured, [boom, "rejected", "Script error."]);

  target.dispatchEvent(errorEvent(new Error("later"))); // Sentry's own handlers see these now
  early.flush((e) => captured.push(e));
  assert.equal(captured.length, 3);
});

test("keeps at most `max`", () => {
  const target = new EventTarget();
  const early = bufferEarlyErrors(target, 10);
  for (let i = 0; i < 25; i++) target.dispatchEvent(errorEvent(new Error(`e${i}`)));
  const captured = [];
  early.flush((e) => captured.push(e.message));
  assert.deepEqual(captured, Array.from({ length: 10 }, (_, i) => `e${i}`));
});
