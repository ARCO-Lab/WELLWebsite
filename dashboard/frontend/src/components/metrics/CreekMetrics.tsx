// Latest sampling results for one creek, grouped by site, for the sites and metrics selected under Filters
// (Latest Data panel on the Ancaster Watershed tab and its modal).

import React from "react";
import { Bug, Biohazard, Cloudy, FlaskConical, Zap, Atom, Flame, Leaf } from "lucide-react";
import { SAMPLING_FILTER_CONFIG, SAMPLING_METRICS } from "@/components/config/filters";
import MetricGroup, { type MetricSection } from "./MetricList";

// label = the filter's name for the metric, which is also measurement_type in the API
const metricMap = [
  { label: "E. coli", key: "E. coli", icon: Bug, color: "text-mcmaster-maroon" },
  { label: "Total coliform", key: "Total coliform", icon: Biohazard, color: "text-mcmaster-gold" },
  { label: "Turbidity", key: "Turbidity", icon: Cloudy, color: "text-mcmaster-grey" },
  { label: "pH", key: "pH", icon: FlaskConical, color: "text-primary" },
  { label: "Conductivity", key: "Conductivity", icon: Zap, color: "text-mcmaster-maroon" },
  { label: "Chloride", key: "Chloride", icon: Atom, color: "text-mcmaster-gold" },
  { label: "Total phosphorus", key: "Total phosphorus", icon: Flame, color: "text-mcmaster-grey" },
  { label: "Soluble reactive phosphorus", key: "Soluble reactive phosphorus", icon: Flame, color: "text-primary" },
  { label: "Total nitrogen", key: "Total nitrogen", icon: Leaf, color: "text-mcmaster-maroon" },
  { label: "Nitrate nitrogen", key: "Nitrate nitrogen", icon: Leaf, color: "text-mcmaster-gold" },
  { label: "Ammonia nitrogen", key: "Ammonia nitrogen", icon: Leaf, color: "text-mcmaster-grey" },
];

interface CreekMetricsProps {
  creekKey: keyof typeof SAMPLING_FILTER_CONFIG;
  subFilters: string[];
  metrics?: any[];
  loading?: boolean;
  inModal?: boolean; // set by the modal: show every tile at once instead of the scrolling strip
}

const CreekMetrics: React.FC<CreekMetricsProps> = ({ creekKey, subFilters, metrics: allData = [], loading = false, inModal = false }) => {
  const creekConfig = SAMPLING_FILTER_CONFIG[creekKey];
  const metricsToDisplay = metricMap.filter((m) => subFilters.includes(m.label));

  // Every site of the creek unless specific sites are picked.
  const allSites = Object.entries(creekConfig.sites).map(([id, name]) => ({ id, name }));
  const siteFilters = subFilters.filter((f) => !SAMPLING_METRICS.includes(f));
  const sites = siteFilters.includes("All Sites") || siteFilters.length === 0
    ? allSites
    : allSites.filter((site) => siteFilters.includes(site.id));

  const sections: MetricSection[] = sites.map((site) => ({
    key: site.id,
    title: `Site ${site.id} · ${site.name}`,
    rows: metricsToDisplay.map((metric) => ({
      ...metric,
      key: `${site.id}-${metric.key}`,
      reading: allData.find((d) => d.measurement_type === metric.key && String(d.site_id) === site.id),
    })),
  }));

  return (
    <MetricGroup
      title={`${creekConfig.label} Metrics`}
      sections={sections}
      loading={loading}
      layout={inModal ? "wrap" : "ticker"}
      staleAfterHours={null}
      timeLabel="sampled"
      dateOnly
      emptyHint="Pick metrics under Filters to see the latest samples."
    />
  );
};

export default CreekMetrics;
