export const SENSOR_FILTER_CONFIG = {
  gauges: {
    label: "Water Loggers",
    metrics: ["Water Level", "Water Temperature"],
    itemsLabel: "All Loggers",
    items: ["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"],
  },
  weather: {
    label: "Weather Data",
    metrics: [ "Air Temperature", "Pressure", "Wind Speed", "Gust Speed", "Wind Direction", "Relative Humidity", "Dew Point", "Rainfall", "Water Content", "Solar Radiation", "Soil Temperature" ],
    itemsLabel: "All Stations",
    items: ["Weather Station"],
  },
  quality: {
    label: "Water Quality",
    metrics: [ "Water Temperature", "Conductivity", "Salinity", "Total Dissolved Solids (TDS)", "Dissolved Oxygen (ODO)", "Dissolved Oxygen Saturation (ODOSat)", "Turbidity", "Total Suspended Solids (TSS)" ],
    itemsLabel: "All Stations",
    items: ["Water Quality Station"],
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