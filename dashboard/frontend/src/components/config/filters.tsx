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