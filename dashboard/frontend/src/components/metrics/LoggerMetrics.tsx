// Latest water logger readings, grouped by logger, for the loggers and metrics selected under Filters
// (Latest Data panel and its modal).

import React, { useMemo } from "react";
import { Waves, Thermometer } from "lucide-react";
import { SENSOR_FILTER_CONFIG } from "@/components/config/filters";
import MetricGroup, { type MetricSection } from "./MetricList";

// key = the filter's name for the metric, which is also measurement_type in the API
const metricDisplayMap: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  "Water Surface Elevation": { label: "Water surface", icon: Waves, color: "text-mcmaster-maroon" },
  "Water Temperature": { label: "Water temperature", icon: Thermometer, color: "text-mcmaster-gold" },
};

const LoggerMetrics = ({
  activeKeys,
  metrics: allData = [],
  loading = false,
  inModal = false,
}: {
  activeKeys: string[];
  activeGroups?: { weather: boolean; quality: boolean; gauges: boolean };
  metrics?: any[];
  loading?: boolean;
  inModal?: boolean; // set by the modal: show every tile at once instead of the scrolling strip
}) => {
  const loggerConfig = SENSOR_FILTER_CONFIG.gauges;

  const sections: MetricSection[] = useMemo(() => {
    const allLoggerIds = Object.keys(loggerConfig.sites);
    const loggerIds = activeKeys.includes("All Loggers")
      ? allLoggerIds
      : activeKeys.filter((key) => allLoggerIds.includes(key)).sort();
    const metrics = loggerConfig.metrics.filter((metric) => activeKeys.includes(metric) && metricDisplayMap[metric]);

    return loggerIds.map((loggerId) => ({
      key: loggerId,
      title: loggerConfig.sites[loggerId as keyof typeof loggerConfig.sites],
      rows: metrics.map((metric) => ({
        key: `${loggerId}-${metric}`,
        fullLabel: metric,
        ...metricDisplayMap[metric],
        reading: allData.find(
          (d) => String(d.station_id) === loggerId && d.measurement_type === metric && d.group_type === "Logger"
        ),
      })),
    }));
  }, [activeKeys, allData, loggerConfig]);

  return (
    <MetricGroup
      title="Water Logger Metrics"
      sections={sections}
      loading={loading}
      layout={inModal ? "wrap" : "ticker"}
      emptyHint="Pick loggers and metrics under Filters to see their latest values."
    />
  );
};

export default LoggerMetrics;
