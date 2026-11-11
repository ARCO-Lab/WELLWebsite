// Unit tests for src/utils/siteTime.ts, run in several viewer time zones: the picked days must mean the same
// Toronto days whether the browser is in Toronto, Vancouver, Kolkata or UTC.
//   npm test

import { test } from "node:test";
import assert from "node:assert/strict";
import { siteMidnight, siteDay, siteDayBounds, dayStamp } from "../src/utils/siteTime.ts";

const ZONES = ["America/Toronto", "America/Vancouver", "Asia/Kolkata", "UTC", "Pacific/Auckland"];

// Node applies a new TZ to Date's local-time methods as soon as it is assigned.
function inZone(tz, fn) {
  const before = process.env.TZ;
  process.env.TZ = tz;
  try {
    fn();
  } finally {
    if (before === undefined) delete process.env.TZ;
    else process.env.TZ = before;
  }
}

test("siteMidnight is Toronto midnight, in winter and summer", () => {
  assert.equal(new Date(siteMidnight(2026, 10, 10)).toISOString(), "2026-11-10T05:00:00.000Z"); // EST
  assert.equal(new Date(siteMidnight(2026, 6, 1)).toISOString(), "2026-07-01T04:00:00.000Z"); // EDT
  // Days that change the clocks: midnight is still before the change
  assert.equal(new Date(siteMidnight(2026, 2, 8)).toISOString(), "2026-03-08T05:00:00.000Z");
  assert.equal(new Date(siteMidnight(2026, 10, 1)).toISOString(), "2026-11-01T04:00:00.000Z");
});

for (const tz of ZONES) {
  test(`picked days mean the same Toronto days with the browser in ${tz}`, () => {
    inZone(tz, () => {
      // What the date picker hands over for Nov 10 and Nov 11, 2026: local midnight of those calendar days
      const { start, end } = siteDayBounds(new Date(2026, 10, 10), new Date(2026, 10, 11));
      assert.equal(start, "2026-11-10T05:00:00.000Z");
      assert.equal(end, "2026-11-12T04:59:59.999Z");
      // A Date with a time of day still means its calendar day
      assert.deepEqual(siteDayBounds(new Date(2026, 10, 10, 23, 30), new Date(2026, 10, 11, 0, 15)), { start, end });
      // Across the fall-back change (Nov 1, 2026): 25 hours that day
      const fall = siteDayBounds(new Date(2026, 10, 1), new Date(2026, 10, 1));
      assert.equal(fall.start, "2026-11-01T04:00:00.000Z");
      assert.equal(fall.end, "2026-11-02T04:59:59.999Z");
      assert.equal(dayStamp(new Date(2026, 10, 9)), "20261109");
    });
  });

  test(`today is Toronto's date with the browser in ${tz}`, () => {
    inZone(tz, () => {
      // 02:30 UTC on Nov 11 is still Nov 10 in Toronto (21:30), whatever the local date is
      const now = Date.UTC(2026, 10, 11, 2, 30);
      const today = siteDay(0, 0, now);
      assert.deepEqual([today.getFullYear(), today.getMonth(), today.getDate()], [2026, 10, 10]);
      assert.equal(today.getHours(), 0);
      const yesterday = siteDay(-1, 0, now);
      assert.deepEqual([yesterday.getMonth(), yesterday.getDate()], [10, 9]);
      const twoMonthsAgo = siteDay(0, -2, now);
      assert.deepEqual([twoMonthsAgo.getMonth(), twoMonthsAgo.getDate()], [8, 10]);
      // 05:30 UTC is just past midnight in Toronto: Nov 11
      assert.equal(siteDay(0, 0, Date.UTC(2026, 10, 11, 5, 30)).getDate(), 11);
    });
  });
}
