// Calendar days at the site (America/Toronto), whatever time zone the viewer's browser is in.
//
// The date pickers hand over Dates whose own (local) calendar day is the day picked. Sending such a Date's local
// midnight with toISOString() made the range depend on the viewer: from Vancouver it started at 03:00 Toronto
// time, from Kolkata at 13:30 the day before. These helpers turn a picked day into Toronto midnight explicitly.
// No React or browser APIs here, so scripts/siteTime.test.mjs can test it with plain Node under any TZ.

export const SITE_TIME_ZONE = "America/Toronto";

// One formatter, reused: creating Intl formatters is slow.
let partsFormatter: Intl.DateTimeFormat | null = null;

/** Toronto's wall-clock fields at an instant. */
function siteParts(utcMs: number) {
  partsFormatter ??= new Intl.DateTimeFormat("en-US", {
    timeZone: SITE_TIME_ZONE, hourCycle: "h23",
    year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric",
  });
  const p: Record<string, number> = {};
  for (const { type, value } of partsFormatter.formatToParts(new Date(utcMs))) p[type] = Number(value);
  return p;
}

/** How far Toronto's wall clock is ahead of UTC at an instant, in ms (-4 or -5 hours). */
function offsetMs(utcMs: number): number {
  const p = siteParts(utcMs);
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - Math.floor(utcMs / 1000) * 1000;
}

/** The instant (epoch ms) of 00:00 in Toronto on a calendar day (month 0-11; overflowing days roll over). */
export function siteMidnight(year: number, month: number, day: number): number {
  const wall = Date.UTC(year, month, day);
  return wall - offsetMs(wall - offsetMs(wall));
}

/** Today's date in Toronto, shifted by whole days and months, as a Date at local midnight of that calendar day:
 *  the form the date pickers use. */
export function siteDay(offsetDays = 0, offsetMonths = 0, now: number = Date.now()): Date {
  const p = siteParts(now);
  return new Date(p.year, p.month - 1 + offsetMonths, p.day + offsetDays);
}

/** A picker's calendar day (its local year, month and day) as a Date at local midnight. */
export function asDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** The picked days as ISO instants for the API: Toronto midnight of the first day to the last millisecond of the
 *  last day (the API's ranges include their end). */
export function siteDayBounds(startDay: Date, endDay: Date): { start: string; end: string } {
  const start = siteMidnight(startDay.getFullYear(), startDay.getMonth(), startDay.getDate());
  const end = siteMidnight(endDay.getFullYear(), endDay.getMonth(), endDay.getDate() + 1) - 1;
  return { start: new Date(start).toISOString(), end: new Date(end).toISOString() };
}

/** YYYYMMDD of a picked day, for file names (its own calendar day, not the UTC one). */
export function dayStamp(day: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${day.getFullYear()}${pad(day.getMonth() + 1)}${pad(day.getDate())}`;
}
