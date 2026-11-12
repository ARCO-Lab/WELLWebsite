// Latest water quality sensor readings for the metrics selected under Filters (Latest Data panel and its modal).

import React from "react";
import { Beaker, Eye, Waves, Zap, Droplets, FlaskConical, Activity, Thermometer } from "lucide-react";
import MetricGroup, { type MetricRow } from "./MetricList";
import type { Metric } from "@/hooks/useLatestMetrics";

// fullLabel = the filter's name for the metric; label = the shorter name shown in the panel;
// key = measurement_type in the API
const metricMap = [
  { fullLabel: "Total Dissolved Solids (TDS)", label: "Dissolved solids", key: "TDS", icon: Beaker, color: "text-mcmaster-maroon" },
  { fullLabel: "Dissolved Oxygen (ODO)", label: "Dissolved oxygen", key: "ODO", icon: Waves, color: "text-mcmaster-gold" },
  { fullLabel: "Dissolved Oxygen Saturation (ODOSat)", label: "Oxygen saturation", key: "ODOSat", icon: Eye, color: "text-mcmaster-grey" },
  { fullLabel: "Total Suspended Solids (TSS)", label: "Suspended solids", key: "TSS", icon: Zap, color: "text-primary" },
  { fullLabel: "Turbidity", label: "Turbidity", key: "Turbidity", icon: Droplets, color: "text-mcmaster-maroon" },
  { fullLabel: "Salinity", label: "Salinity", key: "Salinity", icon: FlaskConical, color: "text-mcmaster-gold" },
  { fullLabel: "Conductivity", label: "Conductivity", key: "Conductivity", icon: Activity, color: "text-mcmaster-grey" },
  { fullLabel: "Water Temperature", label: "Water temperature", key: "Water Temperature", icon: Thermometer, color: "text-primary" },
];

const QualityMetrics = ({
  activeKeys,
  metrics: qualityData = [],
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
    .filter(({ fullLabel }) => activeKeys.includes(fullLabel))
    .map((metric) => ({
      ...metric,
      reading: qualityData.find((d) => d.group_type === "Quality" && d.measurement_type === metric.key),
    }));

  return <MetricGroup title="Water Quality Metrics" sections={[{ key: "quality", rows }]} loading={loading} layout={inModal ? "wrap" : "ticker"} />;
};

export default QualityMetrics;
