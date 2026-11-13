// What one card's chart draws: a series for every measurement (and, for the water loggers, every logger) the
// sub-filters select, each with its colour, line style and unit, and one y-axis per unit. Pure data, tested with plain
// Node in scripts/seriesLoader.test.mjs.

import { LOGGER_PALETTE, QUALITY_PANELS, UNITS, WEATHER_PANELS, aggOf, displayUnit, measurementColor, seriesNote, type Agg } from "./chartStyle.ts";

export type Group = "Weather" | "Quality" | "Logger";

export interface SeriesSpec {
  key: string; // "<group>|<station>|<measurement>", as /api/series names it
  measurement: string;
  name: string; // legend and tooltip label, with the unit
  unit: string;
  agg: Agg;
  color: string;
  dash?: "ShortDash"; // the loggers' water temperature, so level and temperature of one logger share a colour
  note?: string; // a sensor known to be faulty (chartStyle SERIES_NOTES)
  hidden?: boolean; // starts hidden (still listed in the legend, to show)
  axis: number; // index into the chart's y-axes
}

export interface AxisSpec { unit: string; measurements: string[] }

// Measurements a card's chart doesn't draw. Wind direction (degrees, drawn as scattered dots between the lines) read
// as noise; it is shown on the wind rose instead, and stays in the data and exports.
const NOT_CHARTED = new Set(["Wind Direction"]);

// The order measurements are listed in: the per-unit panels' order, so related ones sit together in the legend
const ORDER: Record<Group, string[]> = {
  Weather: WEATHER_PANELS.flatMap((p) => p.measurements),
  Quality: QUALITY_PANELS.flatMap((p) => p.measurements),
  Logger: ["Water Surface Elevation", "Water Temperature"],
};

const withUnit = (label: string, unit: string) => (unit && unit !== "°" ? `${label} (${unit})` : label);

/** The series and y-axes of one card's chart. `stations` are the station ids to draw (one for the weather station and
 *  the water quality probe; the selected loggers), with their display names; `measurements` the selected measurement
 *  types. Measurements this group doesn't have (e.g. "All Weather") are ignored. */
export function cardSeries(
  group: Group,
  stations: { id: string; name: string }[],
  measurements: string[],
): { series: SeriesSpec[]; axes: AxisSpec[] } {
  const known = new Set(ORDER[group]);
  const picked = [
    ...ORDER[group].filter((m) => measurements.includes(m)),
    ...measurements.filter((m) => !known.has(m) && UNITS[m] !== undefined && group !== "Logger"),
  ].filter((m) => !NOT_CHARTED.has(m));
  const axes: AxisSpec[] = [];
  const axisOf = (unit: string, m: string) => {
    let i = axes.findIndex((a) => a.unit === unit);
    if (i < 0) i = axes.push({ unit, measurements: [] }) - 1;
    if (!axes[i].measurements.includes(m)) axes[i].measurements.push(m);
    return i;
  };
  const series: SeriesSpec[] = [];
  stations.forEach((st, n) => {
    for (const m of picked) {
      const unit = displayUnit(UNITS[m] ?? ""); // as the page shows it: µS/cm, ppt, none for pH
      const note = seriesNote(group, m);
      const logger = group === "Logger";
      series.push({
        key: `${group}|${st.id}|${m}`,
        measurement: m,
        name: withUnit(logger ? `${st.name} · ${m}` : m, unit),
        unit,
        agg: aggOf(m),
        color: logger
          ? LOGGER_PALETTE[n % LOGGER_PALETTE.length][m === "Water Temperature" ? "light" : "dark"]
          : measurementColor(m),
        ...(logger && m === "Water Temperature" ? { dash: "ShortDash" as const } : {}),
        ...(note ? { note: note.note, hidden: note.hidden } : {}),
        axis: axisOf(unit, m),
      });
    }
  });
  return { series, axes };
}
