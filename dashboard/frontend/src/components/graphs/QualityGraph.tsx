// This file defines the QualityGraph component: the water quality probe's selected readings, all in one chart (a
// y-axis per unit; see MetricChart). TSS starts hidden (the sensor has only ever read 0; its legend entry shows it) and
// ODO is marked as suspect since June 2026 (see utils/chartStyle SERIES_NOTES).

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { SENSOR_STATIONS } from '@/components/config/filters';
import { cardSeries } from '@/utils/cardSeries';
import ChartErrorBoundary from './ChartErrorBoundary';

const MetricChart = dynamic(() => import("@/components/graphs/highcharts/MetricChart"), { ssr: false });

const QUALITY_METRIC_MAP: Record<string, string> = {
  "Total Dissolved Solids (TDS)": "TDS",
  "Dissolved Oxygen (ODO)": "ODO",
  "Dissolved Oxygen Saturation (ODOSat)": "ODOSat",
  "Total Suspended Solids (TSS)": "TSS",
};

interface Props {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  subFilters: {
    gauges: string[];
    weather: string[];
    quality: string[];
  };
  modalOpen?: boolean;
}

const QualityGraph = ({ subFilters, modalOpen }: Props) => {
  const { series, axes } = useMemo(
    () => cardSeries("Quality", [{ id: SENSOR_STATIONS.quality, name: "Water quality" }],
      subFilters.quality.map((label) => QUALITY_METRIC_MAP[label] || label)),
    [subFilters.quality]
  );
  return (
    <div className="rounded bg-white p-4 shadow max-sm:p-0 max-sm:shadow-none">
      {series.length === 0 ? (
        <>
          <h3 className="mb-2 text-lg font-bold">Water Quality</h3>
          <p className="text-sm text-muted">Tick a measurement under Water Quality in Filters to see its readings.</p>
        </>
      ) : (
        <ChartErrorBoundary title="Water Quality">
          <MetricChart id="quality" title="Water Quality" series={series} axes={axes} modalOpen={modalOpen} />
        </ChartErrorBoundary>
      )}
    </div>
  );
};

export default QualityGraph;
