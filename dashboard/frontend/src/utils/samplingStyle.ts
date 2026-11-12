// How the creek sampling charts draw each measurement: its own colour, line style and marker, the same in every chart
// and in the card's legend. The colours are Paul Tol's "muted" palette (chosen to stay distinct for colour-blind
// viewers) plus black and grey; measurements that are related (the two bacteria counts, the phosphorus and the
// nitrogen forms) also differ in line style and marker, so they can be told apart even where two colours look alike.

export type SamplingDash = "Solid" | "ShortDash" | "Dash";

export interface SamplingStyle {
  color: string;
  dash: SamplingDash;
  marker: "circle" | "square" | "diamond" | "triangle" | "triangle-down";
}

const STYLES: Record<string, SamplingStyle> = {
  "E. coli": { color: "#882255", dash: "Solid", marker: "circle" },
  "Total coliform": { color: "#CC6677", dash: "ShortDash", marker: "square" },
  "Turbidity": { color: "#999933", dash: "Solid", marker: "diamond" },
  "pH": { color: "#332288", dash: "Solid", marker: "triangle" },
  "Conductivity": { color: "#44AA99", dash: "Solid", marker: "triangle-down" },
  "Chloride": { color: "#117733", dash: "Solid", marker: "circle" },
  "Total phosphorus": { color: "#AA4499", dash: "Solid", marker: "square" },
  "Soluble reactive phosphorus": { color: "#88CCEE", dash: "ShortDash", marker: "diamond" },
  "Total nitrogen": { color: "#000000", dash: "Solid", marker: "triangle" },
  "Nitrate nitrogen": { color: "#DDCC77", dash: "ShortDash", marker: "triangle-down" },
  "Ammonia nitrogen": { color: "#777777", dash: "Dash", marker: "circle" },
};

const FALLBACK: SamplingStyle = { color: "#4B5563", dash: "Solid", marker: "circle" };

export const samplingStyle = (measurement: string): SamplingStyle => STYLES[measurement] ?? FALLBACK;

// The same dashes as an SVG stroke-dasharray, for the legend's swatches (Highcharts scales its dash patterns by the
// line width, 2 px here).
export const SVG_DASH: Record<SamplingDash, string | undefined> = { Solid: undefined, ShortDash: "6 2", Dash: "8 6" };
