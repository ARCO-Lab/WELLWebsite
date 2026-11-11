// Calendar days at the site (America/Toronto), whatever time zone the viewer's browser is in.
//
// The date pickers hand over Dates whose own (local) calendar day is the day picked. Sending such a Date's local
// midnight with toISOString() made the range depend on the viewer: from Vancouver it started at 03:00 Toronto
// time, from Kolkata at 13:30 the day before. These helpers turn a picked day into Toronto days explicitly, with
// the same Toronto time maths as the charts (utils/chartWindow.ts), so there is one DST implementation.
// No React or browser APIs here, so scripts/siteTime.test.mjs can test it with plain Node under any TZ.
// (The ".ts" extension lets Node run this file directly in the tests; the bundler accepts it too.)

import { subMonths } from "date-fns";
import { pickedDaysRange, zoneOffsetMs } from "./chartWindow.ts";

/** The first day with data (sampling from 2025-05-01, sensors from 2025-05-08), as a picked day: the date
 *  pickers start their month dropdowns here, and the sampling tab shows everything from here by default.
 *  Copy it (new Date(DATA_START)) before changing it. */
export const DATA_START = new Date(2025, 4, 1);

/** Today's date in Toronto, shifted by whole days and months, as a Date at local midnight of that calendar day:
 *  the form the date pickers use. Months are calendar months, clamped at month ends (Apr 30 - 2 months = Feb 28). */
export function siteDay(offsetDays = 0, offsetMonths = 0, now: number = Date.now()): Date {
  const wall = new Date(now + zoneOffsetMs(now)); // Toronto's wall clock, read through the UTC fields
  const day = new Date(wall.getUTCFullYear(), wall.getUTCMonth(), wall.getUTCDate() + offsetDays);
  return offsetMonths ? subMonths(day, -offsetMonths) : day;
}

/** The picked days as ISO instants for the API: Toronto midnight of the first day to the last millisecond of the
 *  last day (the API's ranges include their end). */
export function siteDayBounds(startDay: Date, endDay: Date): { start: string; end: string } {
  const { start, end } = pickedDaysRange(startDay, endDay);
  return { start: new Date(start).toISOString(), end: new Date(end - 1).toISOString() };
}

/** YYYYMMDD of a picked day, for file names (its own calendar day, not the UTC one). */
export function dayStamp(day: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${day.getFullYear()}${pad(day.getMonth() + 1)}${pad(day.getDate())}`;
}
