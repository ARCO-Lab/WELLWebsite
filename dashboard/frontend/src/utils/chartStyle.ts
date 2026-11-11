// How the sensor charts present each measurement: a fixed colour per measurement (the same on every logger, every
// load and every chart, since small card charts have no legend to look it up in), how its values are drawn
// (line, rain as bars, wind direction as points), and which weather measurements share a small chart (one per
// unit). Pure functions, tested with plain Node in scripts/chartWindow.test.mjs.

export type Agg = "mean" | "sum" | "vector_mean";

const COLORS: Record<string, string> = {
  // Water loggers (and the quality probe's temperature)
  "Water Surface Elevation": "#0866AB",
  "Water Temperature": "#E07B00",
  // Weather
  "Air Temperature": "#CB2027",
  "Dew Point": "#0866AB",
  "Soil Temperature": "#7F488D",
  "Relative Humidity": "#0866AB",
  "Pressure": "#7F488D",
  "Rain": "#0866AB",
  "Wind Speed": "#2E8B3A",
  "Gust Speed": "#E07B00",
  "Wind Direction": "#0866AB",
  "Solar Radiation": "#E07B00",
  "Water Content": "#2E8B3A",
  // Water quality
  "TDS": "#0866AB",
  "ODO": "#2E8B3A",
  "ODOSat": "#7F488D",
  "TSS": "#8A5A1E",
  "Turbidity": "#CB2027",
  "Salinity": "#1B7F86",
  "Conductivity": "#E90D8B",
};
const FALLBACK = ["#0866AB", "#2E8B3A", "#E07B00", "#E90D8B", "#1B7F86", "#7F488D", "#8A5A1E", "#CB2027"];

/** The colour of a measurement, the same wherever it is drawn. */
export function seriesColor(measurement: string): string {
  if (COLORS[measurement]) return COLORS[measurement];
  let h = 0;
  for (const c of measurement) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return FALLBACK[h % FALLBACK.length];
}

/** How a series is drawn: rain totals as bars, wind direction (an angle: a line from 350° to 10° would cross the
 *  whole chart) as points, everything else as a line. */
export function seriesType(agg: Agg): "line" | "column" | "scatter" {
  return agg === "sum" ? "column" : agg === "vector_mean" ? "scatter" : "line";
}

/** Whether a series gets a min–max band behind its line: only averaged lines (a rain bar is already a total, and
 *  the min/max of angles means nothing). */
export function hasBand(agg: Agg, aggregated: boolean): boolean {
  return aggregated && agg === "mean";
}

export const COMPASS: Record<number, string> = { 0: "N", 90: "E", 180: "S", 270: "W", 360: "N" };

/** "225° (SW)": a direction with its 16-point compass name. */
export function compassLabel(deg: number): string {
  const names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const d = ((deg % 360) + 360) % 360;
  return `${Math.round(d)}° (${names[Math.floor((d + 11.25) / 22.5) % 16]})`;
}

// The weather station's small charts, one per unit, in this order. Each lists the measurements it can show.
// `id` is stable (tests find a chart by data-testid="chart-weather-<id>"); titles may change.
export const WEATHER_PANELS: { id: string; title: string; measurements: string[] }[] = [
  { id: "temperature", title: "Temperature (°C)", measurements: ["Air Temperature", "Dew Point", "Soil Temperature"] },
  { id: "humidity", title: "Relative humidity (%)", measurements: ["Relative Humidity"] },
  { id: "pressure", title: "Pressure (mbar)", measurements: ["Pressure"] },
  { id: "rain", title: "Rain (mm)", measurements: ["Rain"] },
  { id: "wind-speed", title: "Wind speed (m/s)", measurements: ["Wind Speed", "Gust Speed"] },
  { id: "wind-direction", title: "Wind direction", measurements: ["Wind Direction"] },
  { id: "solar-radiation", title: "Solar radiation (W/m²)", measurements: ["Solar Radiation"] },
  { id: "soil-water", title: "Soil water content (m³/m³)", measurements: ["Water Content"] },
];

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** The small charts for the selected weather measurements: each panel with what is selected of it, in the panels'
 *  order. A selected measurement no panel knows gets a chart of its own once the data has it (`available`: the
 *  weather measurements in the data), so filter labels that aren't measurements ("All Weather") never do. */
export function weatherPanels(
  selected: string[], available: ReadonlySet<string> = new Set(),
): { id: string; title: string; measurements: string[] }[] {
  const known = new Set(WEATHER_PANELS.flatMap((p) => p.measurements));
  const panels = WEATHER_PANELS
    .map((p) => ({ id: p.id, title: p.title, measurements: p.measurements.filter((m) => selected.includes(m)) }))
    .filter((p) => p.measurements.length > 0);
  // Ids for these are prefixed, so they can't collide with the fixed ones ("Humidity" -> extra-humidity), and
  // numbered if two slug the same
  const ids = new Set<string>();
  for (const m of selected) {
    if (known.has(m) || !available.has(m)) continue;
    let id = `extra-${slug(m)}`;
    for (let n = 2; ids.has(id); n++) id = `extra-${slug(m)}-${n}`;
    ids.add(id);
    panels.push({ id, title: m, measurements: [m] });
  }
  return panels;
}
