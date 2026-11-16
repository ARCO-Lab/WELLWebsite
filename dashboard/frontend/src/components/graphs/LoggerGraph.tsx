// This file defines the LoggerGraph component: the selected water loggers' readings, all in one chart: water level
// and water temperature on their own y-axes, a colour per logger, the temperature dashed (see MetricChart).

import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { SENSOR_FILTER_CONFIG } from '@/components/config/filters';
import { cardSeries } from '@/utils/cardSeries';
import ChartErrorBoundary from './ChartErrorBoundary';

const MetricChart = dynamic(() => import('./highcharts/MetricChart'), {
  ssr: false,
});

interface Props {
  subFilters: string[];
  modalOpen?: boolean; // set by the modal (cloneElement), not by the page
}

const LoggerGraph = ({ subFilters, modalOpen = false }: Props) => {
  const { series, axes } = useMemo(() => {
    const sites = SENSOR_FILTER_CONFIG.gauges.sites as Record<string, string>;
    const all = Object.keys(sites);
    const picked = !Array.isArray(subFilters) ? []
      : subFilters.includes('All Loggers') ? all : all.filter((id) => subFilters.includes(id));
    return cardSeries('Logger', picked.sort().map((id) => ({ id, name: sites[id] ?? `Logger ${id}` })),
      Array.isArray(subFilters) ? subFilters : []);
  }, [subFilters]);

  return (
    <div className="rounded bg-white p-4 shadow max-sm:p-0 max-sm:shadow-none">
      {series.length === 0 ? (
        <>
          <h3 className="mb-2 text-lg font-bold">Water Loggers</h3>
          <p className="text-sm text-muted">Tick Water Surface Elevation or Water Temperature under Filters to see the loggers&apos; readings.</p>
        </>
      ) : (
        <ChartErrorBoundary title="Water Loggers">
          <MetricChart id="logger" title="Water Loggers" series={series} axes={axes} modalOpen={modalOpen} />
        </ChartErrorBoundary>
      )}
    </div>
  );
};

export default LoggerGraph;
