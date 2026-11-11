// This file defines the LoggerGraph component for rendering time series charts for selected water loggers.
// It displays a MetricChart for each selected logger (its station's series, from the page via useChartView), with
// one error message and one resolution badge for all of them.

// ADD RATING CURVE FOR OTHER METRIC THAT JUST TAKES FROM WSE WHEN AVAILABLE


import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { SENSOR_FILTER_CONFIG } from '@/components/config/filters';
import { useChartView } from '@/hooks/useChartSeries';
import { resolutionBadge } from '@/utils/chartWindow';

const MetricChart = dynamic(() => import('./highcharts/MetricChart'), {
  ssr: false,
});

interface Props {
  subFilters: string[];
  modalOpen?: boolean; // set by the modal (cloneElement), not by the page
}

const LoggerGraph = ({
  subFilters,
  modalOpen = false,
}: Props) => {
  const { error, loading, shownBucketS, shownAggregated } = useChartView();
  const badge = resolutionBadge(shownBucketS, shownAggregated, false);
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

  // Helper function to determine the grid layout based on the number of items.
  const getGridClass = (count: number) => {
    switch (count) {
      case 1:
        return 'grid-cols-1'; // 1 logger: full width
      case 2:
        return 'grid-cols-1'; // 2 loggers: stacked vertically
      case 3:
        return 'grid-cols-1 lg:grid-cols-3';
      case 4:
        return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4';
      case 5:
        return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-5';
      default:
        return 'grid-cols-1 md:grid-cols-2'; // Default fallback
    }
  };

  return (
    <div className="p-4 bg-white rounded shadow">
      <h3 className="mb-2 flex flex-wrap items-baseline gap-x-3 text-lg font-bold">
        Water Loggers
        {badge && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-normal text-gray-600">{badge}</span>}
      </h3>

      {/* One message for all the logger charts (inside each narrow chart it ran far past the card); screen readers
          hear it once, from the window bar's live region */}
      {error && !loading && (
        <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700" aria-hidden="true">
          {error.message}
        </div>
      )}
      
      {/* The grid class is now dynamically set based on the number of selected loggers */}
      <div className={`grid ${getGridClass(selectedLoggers.length)} gap-4`}>
        {selectedLoggers.sort().map((stationId, index) => {
          const siteConfig = SENSOR_FILTER_CONFIG.gauges.sites;
          const loggerName = siteConfig[stationId as keyof typeof siteConfig] || `Logger ${stationId}`;
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
                title={`${loggerName} Data`}
                groupType="Logger"
                stationId={stationId}
                measurements={metrics}
                height={300}
                showErrorBanner={false}
                showBadge={false}
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