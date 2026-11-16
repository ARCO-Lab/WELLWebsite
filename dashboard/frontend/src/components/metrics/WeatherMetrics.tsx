// Latest weather station readings for the metrics selected under Filters (Latest Data panel and its modal).

import React from "react";
import { Thermometer, Droplets, Wind, CloudRain, Compass, Snowflake, Gauge, Sun, Waves, TreePine, Navigation } from "lucide-react";
import MetricGroup, { compassPoint, type MetricRow } from "./MetricList";
import type { Metric } from "@/hooks/useLatestMetrics";

// label = the filter's name for the metric; key = measurement_type in the API
const metricMap = [
  { label: "Air Temperature", key: "Air Temperature", icon: Thermometer, color: "text-mcmaster-maroon" },
  { label: "Relative Humidity", key: "Relative Humidity", icon: Droplets, color: "text-mcmaster-gold" },
  { label: "Wind Speed", key: "Wind Speed", icon: Wind, color: "text-mcmaster-grey" },
  { label: "Gust Speed", key: "Gust Speed", icon: Navigation, color: "text-primary" },
  { label: "Wind Direction", key: "Wind Direction", icon: Compass, color: "text-mcmaster-maroon" },
  { label: "Dew Point", key: "Dew Point", icon: Snowflake, color: "text-mcmaster-gold" },
  { label: "Rainfall", key: "Rain", icon: CloudRain, color: "text-mcmaster-grey" },
  { label: "Pressure", key: "Pressure", icon: Gauge, color: "text-primary" },
  { label: "Solar Radiation", key: "Solar Radiation", icon: Sun, color: "text-mcmaster-maroon" },
  { label: "Water Content", key: "Water Content", icon: Waves, color: "text-mcmaster-gold" },
  { label: "Soil Temperature", key: "Soil Temperature", icon: TreePine, color: "text-mcmaster-grey" },
];

// "152° SSE" reads better than "151.62 °"
const windDirection = (value: number) => ({ value: `${Math.round(value)}°`, unit: compassPoint(value) });

const WeatherMetrics = ({
  activeKeys,
  metrics: weatherData = [],
  loading = false,
  inModal = false,
}: {
  activeKeys: string[];
  activeGroups?: { weather: boolean; quality: boolean; gauges: boolean };
  metrics?: Metric[];
  loading?: boolean;
  inModal?: boolean; // set by the modal: show every tile at once instead of the scrolling strip
}) => {
  const rows: MetricRow[] = metricMap
    .filter(({ label }) => activeKeys.includes(label))
    .map((metric) => ({
      ...metric,
      reading: weatherData.find((d) => d.group_type === "Weather" && d.measurement_type === metric.key),
      format: metric.key === "Wind Direction" ? windDirection : undefined,
    }));

  return <MetricGroup title="Weather Metrics" sections={[{ key: "weather", rows }]} loading={loading} layout={inModal ? "wrap" : "ticker"} />;
};

export default WeatherMetrics;
