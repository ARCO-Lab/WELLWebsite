// How the sensor charts present each measurement: one colour per measurement (the same wherever it is drawn), its
// unit, how it is drawn (rain as bars of totals, wind direction as points, everything else as a line), which
// measurements share a chart, and notes about sensors whose readings can't be trusted. Pure data and functions.

export type Agg = "mean" | "sum" | "vector_mean";

// One colour per measurement, the same in every chart, so air temperature, dew point and soil temperature (all °C,
// on one axis) can be told apart. A measurement not listed gets one from the fallback palette, by its name.
const MEASUREMENT_COLORS: Record<string, string> = {
  "Air Temperature": "#D62728", "Dew Point": "#0866AB", "Soil Temperature": "#8C564B",
  "Relative Humidity": "#50B748", "Pressure": "#7F488D", "Rain": "#17BECF", "Solar Radiation": "#E0A800",
  "Water Content": "#6B8E23", "Wind Speed": "#4B5563", "Gust Speed": "#E90D8B", "Wind Direction": "#F79425",
  "Water Temperature": "#D62728", "Water Surface Elevation": "#0866AB",
  "Conductivity": "#0866AB", "Salinity": "#17BECF", "TDS": "#7F488D", "ODO": "#50B748", "ODOSat": "#2E7D32",
  "Turbidity": "#8C564B", "TSS": "#F79425",
};
const FALLBACK_COLORS = ["#0866AB", "#50B748", "#F79425", "#E90D8B", "#7F488D", "#CB2027", "#17BECF", "#8C564B"];

export function measurementColor(name: string): string {
  if (MEASUREMENT_COLORS[name]) return MEASUREMENT_COLORS[name];
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return FALLBACK_COLORS[h % FALLBACK_COLORS.length];
}

// The unit each measurement is stored in, for axis titles and series names before the first data arrives (the data
// then names its own unit).
export const UNITS: Record<string, string> = {
  "Water Surface Elevation": "m asl", "Water Temperature": "°C",
  "Air Temperature": "°C", "Dew Point": "°C", "Soil Temperature": "°C", "Relative Humidity": "%", "Pressure": "mbar",
  "Rain": "mm", "Wind Speed": "m/s", "Gust Speed": "m/s", "Wind Direction": "°", "Solar Radiation": "W/m²",
  "Water Content": "m³/m³",
  "Conductivity": "uS/cm", "ODO": "mg/L", "ODOSat": "%", "Salinity": "PPT", "TDS": "g/L", "TSS": "mg/L", "Turbidity": "NTU",
};

/** How /api/series aggregates a measurement (what `avg` holds). */
export const aggOf = (measurement: string): Agg =>
  measurement === "Rain" ? "sum" : measurement === "Wind Direction" ? "vector_mean" : "mean";

/** Rain totals as a stepped area (each bucket's total flat across its span; one shape, where bars would be hundreds of
 *  rectangles to redraw); wind direction (an angle: a line from 350° to 10° would cross the whole chart) as points. */
export function seriesType(agg: Agg): "line" | "area" | "scatter" {
  return agg === "sum" ? "area" : agg === "vector_mean" ? "scatter" : "line";
}

/** "225° (SW)": a direction with its 16-point compass name. */
export function compassLabel(deg: number): string {
  const names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const d = ((deg % 360) + 360) % 360;
  return `${Math.round(d)}° (${names[Math.floor((d + 11.25) / 22.5) % 16]})`;
}

// Sensors known to be faulty, as found in the data: shown with a note (or hidden until asked for) rather than as if
// they were fine. Keyed by "<group>|<measurement>".
export const SERIES_NOTES: Record<string, { note: string; hidden?: boolean }> = {
  "Quality|ODO": { note: "suspect since Jun 2026" }, // reads about 0 since June 2026
  "Quality|TSS": { note: "sensor reads 0", hidden: true }, // has read 0 since it was installed
};
export const seriesNote = (group: string, measurement: string) => SERIES_NOTES[`${group}|${measurement}`];

export interface ChartPanel { id: string; title: string; measurements: string[] }

// The weather station's charts, one per kind of reading, in this order. `id` is stable (tests find a chart by
// data-testid="chart-weather-<id>"); titles may change.
export const WEATHER_PANELS: ChartPanel[] = [
  { id: "temperature", title: "Temperature", measurements: ["Air Temperature", "Dew Point", "Soil Temperature"] },
  { id: "humidity", title: "Relative humidity", measurements: ["Relative Humidity"] },
  { id: "pressure", title: "Pressure", measurements: ["Pressure"] },
  { id: "rain", title: "Rain", measurements: ["Rain"] },
  { id: "wind-speed", title: "Wind speed", measurements: ["Wind Speed", "Gust Speed"] },
  { id: "wind-direction", title: "Wind direction", measurements: ["Wind Direction"] },
  { id: "solar-radiation", title: "Solar radiation", measurements: ["Solar Radiation"] },
  { id: "soil-water", title: "Soil water content", measurements: ["Water Content"] },
];

// The water quality probe's charts: one per unit.
export const QUALITY_PANELS: ChartPanel[] = [
  { id: "conductivity", title: "Conductivity", measurements: ["Conductivity"] },
  { id: "temperature", title: "Water temperature", measurements: ["Water Temperature"] },
  { id: "oxygen", title: "Dissolved oxygen and suspended solids", measurements: ["ODO", "TSS"] },
  { id: "oxygen-saturation", title: "Dissolved oxygen saturation", measurements: ["ODOSat"] },
  { id: "turbidity", title: "Turbidity", measurements: ["Turbidity"] },
  { id: "salinity", title: "Salinity", measurements: ["Salinity"] },
  { id: "tds", title: "Total dissolved solids", measurements: ["TDS"] },
];

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** The charts for the selected measurements: each panel with what is selected of it, in the panels' order. A
 *  selected measurement no panel knows gets a chart of its own if it is a measurement this group has (`known`), so
 *  filter labels that aren't measurements ("All Weather") never do. */
export function panelsFor(panels: ChartPanel[], selected: string[], known: ReadonlySet<string> = new Set(Object.keys(UNITS))): ChartPanel[] {
  const inPanels = new Set(panels.flatMap((p) => p.measurements));
  const out = panels
    .map((p) => ({ ...p, measurements: p.measurements.filter((m) => selected.includes(m)) }))
    .filter((p) => p.measurements.length > 0);
  const ids = new Set(out.map((p) => p.id));
  for (const m of selected) {
    if (inPanels.has(m) || !known.has(m)) continue;
    let id = `extra-${slug(m)}`;
    for (let n = 2; ids.has(id); n++) id = `extra-${slug(m)}-${n}`;
    ids.add(id);
    out.push({ id, title: m, measurements: [m] });
  }
  return out;
}
