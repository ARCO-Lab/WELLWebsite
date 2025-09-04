// This file defines the LoggerGraph component for rendering time series charts for selected water loggers.
// It groups logger data by station and displays a MetricChart for each selected logger.

import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { SENSOR_FILTER_CONFIG } from '@/components/config/filters';

const MetricChart = dynamic(() => import('./highcharts/MetricChart'), {
  ssr: false,
});

interface Props {
  subFilters: string[];
  startDate: Date | null;
  endDate: Date | null;
  modalOpen: boolean;
  data: any[];
  loading?: boolean;
  error?: Error | null;
}

const LoggerGraph = ({
  subFilters,
  startDate,
  endDate,
  modalOpen,
  data,
  loading = false,
  error = null,
}: Props) => {
  // 1. Determine which loggers and metrics are selected, adapted from CreekGraph.tsx
  const { metrics, selectedLoggers } = useMemo(() => {
    // Ensure subFilters is an array before proceeding
    if (!Array.isArray(subFilters)) {
      return { metrics: [], selectedLoggers: [] };
    }

    const selectedMetrics: string[] = [];
    const selectedLoggers: string[] = [];
    const loggerConfig = SENSOR_FILTER_CONFIG.gauges;
    const allLoggerIds = Object.keys(loggerConfig.sites);
    const allMetrics = loggerConfig.metrics;

    // Find selected loggers - MATCH CreekGraph logic exactly
    if (subFilters.includes('All Loggers')) {
      selectedLoggers.push(...allLoggerIds);
    } else {
      subFilters.forEach(filter => {
        if (allLoggerIds.includes(filter)) {
          selectedLoggers.push(filter);
        }
      });
    }
    // REMOVED: No fallback like CreekGraph
    
    // Find selected metrics - use the same logic as CreekGraph
    subFilters.forEach(filter => {
      if (allMetrics.includes(filter)) {
        selectedMetrics.push(filter);
      }
    });

    // REMOVED: No fallback for metrics like CreekGraph

    return { metrics: selectedMetrics, selectedLoggers: selectedLoggers };
  }, [subFilters]);

  // 2. Group the raw data by station_id for efficient filtering
  const dataByStation = useMemo(() => {
    if (!data || !data.length) return {};
    return data.reduce((acc, curr) => {
      const stationId = String(curr.station_id);
      if (!acc[stationId]) acc[stationId] = [];
      acc[stationId].push(curr);
      return acc;
    }, {} as Record<string, any[]>);
  }, [data]);

  // Helper function to determine the grid layout based on the number of items.
  const getGridClass = (count: number) => {
    switch (count) {
      case 1:
        return 'grid-cols-1'; // 1 logger: full width
      case 2:
        return 'grid-cols-1'; // 2 loggers: stacked vertically
      case 3:
        return 'md:grid-cols-3'; // 3 loggers: 3 columns on medium screens+
      case 4:
        return 'md:grid-cols-4'; // 4 loggers: 4 columns on medium screens+
      case 5:
        return 'md:grid-cols-5'; // 5 loggers: 5 columns on medium screens+
      default:
        return 'grid-cols-1 md:grid-cols-2'; // Default fallback
    }
  };

  return (
    <div className="p-4 bg-white rounded shadow">
      <h3 className="font-bold text-lg mb-2">Water Loggers</h3>
      
      {/* The grid class is now dynamically set based on the number of selected loggers */}
      <div className={`grid ${getGridClass(selectedLoggers.length)} gap-4`}>
        {selectedLoggers.sort().map((stationId, index) => {
          const siteConfig = SENSOR_FILTER_CONFIG.gauges.sites;
          const loggerName = siteConfig[stationId as keyof typeof siteConfig] || `Logger ${stationId}`;
          const loggerData = dataByStation[stationId] || [];
          const loggerCount = selectedLoggers.length;
          let legendIndex;

          if (loggerCount <= 2 ) {
            legendIndex = loggerCount - 1;
          } else {
            legendIndex = -1; // No legend for more than 2 loggers
          }


          return (
            <div key={stationId}>
              <MetricChart
                activeGroup={loggerName} // Error necessary
                subFilters={metrics}
                height={300}
                startDate={startDate}
                endDate={endDate}
                data={loggerData}
                loading={loading}
                error={error}
                modalOpen={modalOpen}
                showLegend={modalOpen ? true : index === legendIndex}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LoggerGraph;