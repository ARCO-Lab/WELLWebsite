// Known-suspect data periods, shown as a subtle shaded band (and a small caption) on the charts they concern.
// THIS IS DISPLAY ONLY: nothing here changes, filters, flags or removes stored data, and no export (the sensor
// Download CSV, the sampling export, the Borealis/SharePoint files) looks at it. It is purely a note on the chart so a
// reader knows a stretch of readings is unlikely to reflect the creek.
//
// THE LAB EDITS WINDOWS HERE, in SUSPECT_DATA_WINDOWS below: add an entry, change a date, or drop one. Each entry:
//   - stationId    a logger/station id (the keys of SENSOR_FILTER_CONFIG.gauges.sites, e.g. "2577531" for Logger 1, or
//                  SENSOR_STATIONS.quality for the water quality probe). Omit to match the measurement on any station.
//   - measurements the measurement types it concerns, spelled as the charts name them ("Water Surface Elevation",
//                  "Water Temperature", "ODO", "TSS", …). Omit to match any measurement of the station.
//   - startDate    Toronto wall-clock date "YYYY-MM-DD" (or an ISO instant). null = from the first day with data.
//   - endDate      the same; null = ongoing (the band runs to the right edge of whatever range is shown).
//   - label        the short note shown on the band and in the caption.
//   - detail       (optional) a longer explanation, shown as the caption's tooltip.
//   - kind         "out-of-water" (amber) or "sensor-error" (red), which only picks the band's colour.
//
// A band is drawn only on a chart that actually draws a matching series (by station and measurement), so e.g. Logger 1's
// out-of-water band never appears on the weather or quality chart. An unparseable or back-to-front date is skipped
// rather than allowed to break the chart.

import { dataStart, parseIsoParam } from "@/utils/chartWindow";
import type { SeriesSpec } from "@/utils/cardSeries";

export type SuspectKind = "out-of-water" | "sensor-error";

export interface SuspectWindow {
  stationId?: string;
  measurements?: string[];
  startDate: string | null;
  endDate: string | null;
  label: string;
  detail?: string;
  kind: SuspectKind;
}

// Seeded with the periods the lab has flagged so far. Edit freely.
export const SUSPECT_DATA_WINDOWS: SuspectWindow[] = [
  // Logger 1 came out of the creek over the winter: about 0 m depth, air-like 22–24 °C.
  {
    stationId: "2577531",
    measurements: ["Water Surface Elevation", "Water Temperature"],
    startDate: "2025-12-19",
    endDate: "2026-05-22",
    label: "Possible out-of-water period",
    detail:
      "Logger 1 appears to have been out of the creek (about 0 m depth, air-like 22–24 °C). Readings here may not reflect the creek.",
    kind: "out-of-water",
  },
  // Logger 1 is again reading about 0 m depth (late 2026); it may be out of the creek once more. Adjust the start as the
  // lab pins it down, and set an endDate once it is back in the water.
  {
    stationId: "2577531",
    measurements: ["Water Surface Elevation", "Water Temperature"],
    startDate: "2026-10-01",
    endDate: null,
    label: "Possible out-of-water period",
    detail:
      "Logger 1 is again reading about 0 m depth and may be out of the creek. Readings here may not reflect the creek.",
    kind: "out-of-water",
  },
  // The TSS (total suspended solids) sensor has read about 0 for its whole life.
  {
    measurements: ["TSS"],
    startDate: null,
    endDate: null,
    label: "Possible sensor error (values near zero)",
    detail:
      "The TSS (total suspended solids) sensor has read about 0 continuously; these values are unlikely to be real.",
    kind: "sensor-error",
  },
  // Dissolved oxygen has read about 0 mg/L since roughly June 2026.
  {
    measurements: ["ODO"],
    startDate: "2026-06-01",
    endDate: null,
    label: "Possible sensor error (values near zero)",
    detail:
      "Dissolved oxygen (ODO) has read about 0 mg/L since around June 2026; these values are unlikely to be real.",
    kind: "sensor-error",
  },
];

// A matched window, with its band's instants worked out (epoch ms, the chart's x-axis units).
export interface SuspectBand {
  window: SuspectWindow;
  from: number;
  to: number;
}

// Far enough ahead to mean "ongoing": Highcharts clips the band to whatever range is shown.
const ONGOING_TO = Date.UTC(2999, 0, 1);

const stationOf = (spec: SeriesSpec): string => spec.key.split("|")[1] ?? "";

/** Whether a window concerns any series this chart draws (by station and measurement). */
export function windowMatchesSpecs(w: SuspectWindow, specs: SeriesSpec[]): boolean {
  return specs.some(
    (s) =>
      (w.stationId == null || stationOf(s) === w.stationId) &&
      (w.measurements == null || w.measurements.includes(s.measurement)),
  );
}

/** The bands to draw on a chart with these series: the matching windows, each with its instants resolved. A window
 *  whose dates don't parse, or whose end isn't after its start, is skipped (a typo never breaks the chart). */
export function suspectBandsFor(specs: SeriesSpec[]): SuspectBand[] {
  const bands: SuspectBand[] = [];
  for (const w of SUSPECT_DATA_WINDOWS) {
    if (!windowMatchesSpecs(w, specs)) continue;
    const from = w.startDate == null ? dataStart() : parseIsoParam(w.startDate);
    const to = w.endDate == null ? ONGOING_TO : parseIsoParam(w.endDate);
    if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) continue;
    bands.push({ window: w, from, to });
  }
  return bands;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const prettyDate = (d: string): string => {
  const [y, mo, day] = d.split("T")[0].split("-").map(Number);
  return Number.isFinite(y) && Number.isFinite(mo) && Number.isFinite(day) ? `${MONTHS[mo - 1]} ${day}, ${y}` : d;
};

/** A plain-language span for the caption: "Dec 19, 2025 – May 22, 2026", "since Jun 1, 2026", "ongoing". */
export function windowRangeLabel(w: SuspectWindow): string {
  if (!w.startDate && !w.endDate) return "ongoing";
  if (!w.startDate) return `until ${prettyDate(w.endDate as string)}`;
  if (!w.endDate) return `since ${prettyDate(w.startDate)}`;
  return `${prettyDate(w.startDate)} – ${prettyDate(w.endDate)}`;
}
