// This file defines the LoggerGraph component: one chart per selected water logger, each zooming and panning by
// itself, with the water level on top and the water temperature below (two panes on one time axis). One column on
// a phone or in a narrow card, two where the card is wide enough.

import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { SENSOR_FILTER_CONFIG } from '@/components/config/filters';
import ChartGroup from '@/components/graphs/ChartGroup';

const MetricChart = dynamic(() => import('./highcharts/MetricChart'), {
  ssr: false,
});

interface Props {
  subFilters: string[];
  modalOpen?: boolean; // set by the modal (cloneElement), not by the page
}

const LoggerGraph = ({ subFilters, modalOpen = false }: Props) => {
  const { panes, loggers } = useMemo(() => {
    const config = SENSOR_FILTER_CONFIG.gauges;
    const all = Object.keys(config.sites);
    const picked = !Array.isArray(subFilters) ? []
      : subFilters.includes('All Loggers') ? all : all.filter((id) => subFilters.includes(id));
    // Level on top, temperature below, as far as they are selected
    const order = ['Water Surface Elevation', 'Water Temperature'];
    const metrics = order.filter((m) => Array.isArray(subFilters) && subFilters.includes(m));
    return { panes: metrics.map((m) => [m]), loggers: picked.sort() };
  }, [subFilters]);

  const sites = SENSOR_FILTER_CONFIG.gauges.sites as Record<string, string>;
  return (
    <ChartGroup title="Water Loggers" chartCount={loggers.length}>
      {panes.length === 0 ? (
        <p className="text-sm text-muted">Tick Water Surface Elevation or Water Temperature under Filters to see the loggers&apos; readings.</p>
      ) : (
        <div className={`grid grid-cols-1 gap-x-6 gap-y-5 ${loggers.length > 1 ? '@3xl:grid-cols-2' : ''}`}>
          {loggers.map((stationId) => (
            <MetricChart
              key={stationId}
              id={`logger-${stationId}`}
              title={sites[stationId] ?? `Logger ${stationId}`}
              groupType="Logger"
              stationId={stationId}
              panes={panes}
              height={panes.length > 1 ? 300 : 220}
              modalOpen={modalOpen}
            />
          ))}
        </div>
      )}
    </ChartGroup>
  );
};

export default LoggerGraph;
