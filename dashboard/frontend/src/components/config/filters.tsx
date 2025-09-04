// This file defines configuration objects and constants for sensor and sampling filters, site/creek mappings, and coordinates.
// Used throughout the frontend for filter UIs, map displays, and data lookups.

export const SENSOR_FILTER_CONFIG = {
  gauges: {
    label: "Water Loggers",
    metrics: [
      "Water Surface Elevation", 
      "Water Temperature",
    ],
    itemsLabel: "All Loggers",
    sites: {
      "2577531": "Logger 1",
      "2577532": "Logger 2",
      "2577533": "Logger 3",
      "2577534": "Logger 4",
      "2577535": "Logger 5",
    },
  },
  weather: {
    label: "Weather Station",
    metrics: [
      "Air Temperature",
      "Pressure",
      "Dew Point",
      "Gust Speed",
      "Wind Direction",
      "Wind Speed",
      "Rainfall",
      "Relative Humidity",
      "Solar Radiation",
      "Soil Temperature",
      "Water Content",

    ],
    itemsLabel: "All Weather",
    items: [], 
  },
  quality: {
    label: "Water Quality",
    metrics: [
      "Total Dissolved Solids (TDS)",
      "Dissolved Oxygen (ODO)",
      "Dissolved Oxygen Saturation (ODOSat)",
      "Total Suspended Solids (TSS)",
      "Turbidity",
      "Salinity",
      "Conductivity",
      "Water Temperature",
    ],
    itemsLabel: "All Quality",
    items: [], 
  },
};

export const SAMPLING_METRICS = [ "E. coli", "Total coliform", "Turbidity", "pH", "Conductivity", "Chloride", "Total phosphorus", "Soluble reactive phosphorus", "Total nitrogen", "Nitrate nitrogen", "Ammonia nitrogen" ];

export const SAMPLING_FILTER_CONFIG = {
  ancaster: { label: "Ancaster Creek", sites: { "2": "Maple Lane Pk", "5": "Sherman Falls" } },
  tiffany: { label: "Tiffany Creek", sites: { "1": "Falkirk Forest", "6": "Tiffany Falls" } },
  sulphur: { label: "Sulphur Creek", sites: { "3": "Jerseyville Rd", "4": "Sulphur Springs" } },
  coldwater: { label: "Coldwater Creek", sites: { "8": "Osler Dr", "9": "McMaster Lot P" } },
  spencer: { label: "Spencer's Creek", sites: { "10": "Cootes Dr" } },
};

export const CREEK_ID_MAP = {
  "ancaster": "19431905",
  "tiffany": "20962187",
  "sulphur": "3212839",
  "coldwater": "336415129",
  "spencer": "19755185"
};

// And the reverse for lookup by numeric ID:
export const CREEK_ID_MAP_REVERSE = Object.fromEntries(
  Object.entries(CREEK_ID_MAP).map(([k, v]) => [v, k])
);

export const SENSOR_STATION_COORDINATES = [
  { id: "2577531", lat: 43.267100, lng: -79.928830, label: "Water Logger 1", group: "gauges" },
  { id: "2577532", lat: 43.266390, lng: -79.929400, label: "Water Logger 2", group: "gauges" },
  { id: "2577533", lat: 43.264720, lng: -79.928440, label: "Water Logger 3", group: "gauges" },
  { id: "2577534", lat: 43.264140, lng: -79.928310, label: "Water Logger 4", group: "gauges" },
  { id: "2577535", lat: 43.263850, lng: -79.929850, label: "Water Logger 5", group: "gauges" },
  { id: "Water Quality Station", lat: 43.264700, lng: -79.928400, label: "Water Quality Sensor", group: "quality" },
  { id: "Weather Station", lat: 43.266110, lng: -79.928660, label: "Weather Station", group: "weather" },
];

export const SAMPLING_SITE_COORDINATES = [
  { id: "1", lat: 43.2137431, lng: -79.9233981, label: "Site 1: Falkirk Forest", group: "tiffany" },
  { id: "2", lat: 43.2055590, lng: -79.9741699, label: "Site 2: Maple Lane Pk", group: "ancaster" },
  { id: "3", lat: 43.2193754, lng: -80.0000820, label: "Site 3: Jerseyville Rd", group: "sulphur" },
  { id: "4", lat: 43.2416900, lng: -80.0005500, label: "Site 4: Sulphur Springs", group: "sulphur" },
  { id: "5", lat: 43.2389100, lng: -79.9732900, label: "Site 5: Sherman Falls", group: "ancaster" },
  { id: "6", lat: 43.2400000, lng: -79.9600500, label: "Site 6: Tiffany Falls", group: "tiffany" },
  { id: "8", lat: 43.2581980, lng: -79.9383952, label: "Site 8: Osler Dr", group: "coldwater" },
  { id: "9", lat: 43.2651150, lng: -79.9429224, label: "Site 9: McMaster Lot P", group: "coldwater" },
  { id: "10", lat: 43.2664186, lng: -79.9293879, label: "Site 10: Cootes Dr", group: "spencer" },
];