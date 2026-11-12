// This file defines the QualityGraph component: the water quality probe's readings, one chart per unit, each
// zooming and panning by itself. TSS starts hidden (the sensor has only ever read 0; its legend entry shows it) and
// ODO is marked as suspect since June 2026 (see utils/chartStyle SERIES_NOTES).

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { SENSOR_STATIONS } from '@/components/config/filters';
import ChartGroup from '@/components/graphs/ChartGroup';
import { QUALITY_PANELS, panelsFor } from '@/utils/chartStyle';

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
  const panels = useMemo(
    () => panelsFor(QUALITY_PANELS, subFilters.quality.map((label) => QUALITY_METRIC_MAP[label] || label)),
    [subFilters.quality]
  );
  return (
    <ChartGroup title="Water Quality" chartCount={panels.length}>
      <div className="grid grid-cols-1 gap-x-6 gap-y-5 @xl:grid-cols-2 @5xl:grid-cols-3">
        {panels.map((p) => (
          <div key={p.id}>
            <MetricChart
              id={`quality-${p.id}`}
              title={p.title}
              groupType="Quality"
              stationId={SENSOR_STATIONS.quality}
              panes={[p.measurements]}
              height={200}
              modalOpen={modalOpen}
            />
          </div>
        ))}
      </div>
    </ChartGroup>
  );
};

export default QualityGraph;
