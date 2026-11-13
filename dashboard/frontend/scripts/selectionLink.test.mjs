// Unit tests for src/utils/selectionLink.ts: what a shared link says is ticked.  npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import { namesFromParam, searchWithSelection } from "../src/utils/selectionLink.ts";

const GROUPS = ["gauges", "weather", "quality"];

test("namesFromParam keeps known names, in their usual order", () => {
  assert.deepEqual(namesFromParam("quality,gauges", GROUPS), ["gauges", "quality"]);
  assert.deepEqual(namesFromParam(" weather , nope,,", GROUPS), ["weather"]);
  assert.deepEqual(namesFromParam(null, GROUPS), []);
  assert.deepEqual(namesFromParam("", GROUPS), []);
});

test("searchWithSelection writes the ticks next to the dates, and drops empty ones", () => {
  const dates = "?from=2026-10-31T00%3A00&to=2026-11-02T00%3A00";
  assert.equal(
    searchWithSelection(dates, "sensor", ["gauges", "weather"], []),
    "?from=2026-10-31T00%3A00&to=2026-11-02T00%3A00&groups=gauges,weather",
  );
  assert.equal(searchWithSelection("?groups=gauges&creeks=tiffany", "sampling", [], ["ancaster"]), "?creeks=ancaster&tab=sampling");
  assert.equal(searchWithSelection("?tab=sampling&groups=weather", "sensor", [], []), "");
});

test("a written link reads back as the same selection", () => {
  const q = new URLSearchParams(searchWithSelection("", "sampling", ["quality"], ["coldwater", "spencer"]));
  assert.deepEqual(namesFromParam(q.get("groups"), GROUPS), ["quality"]);
  assert.deepEqual(namesFromParam(q.get("creeks"), ["ancaster", "coldwater", "spencer"]), ["coldwater", "spencer"]);
  assert.equal(q.get("tab"), "sampling");
});
