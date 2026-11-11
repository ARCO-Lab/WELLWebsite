// This file defines the QualityGraph component for rendering water quality time series data using MetricChart.
// It maps frontend metric labels to backend keys; the series come from the page (useChartView).

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { useChartView } from '@/hooks/useChartSeries';
import ChartsEmpty from '@/components/graphs/ChartsEmpty';
// Dynamically import MetricChart with SSR disabled
const MetricChart = dynamic(() => import("@/components/graphs/highcharts/MetricChart"), { ssr: false });

const QUALITY_METRIC_MAP: Record<string, string> = {
  "Total Dissolved Solids (TDS)": "TDS",
  "Dissolved Oxygen (ODO)": "ODO",
  "Dissolved Oxygen Saturation (ODOSat)": "ODOSat",
  "Total Suspended Solids (TSS)": "TSS",
  // Add more if needed
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
  // Map frontend metric labels to backend keys if needed. Memoized so the chart doesn't rebuild its series
  // on every page re-render.
  const mappedSubFilters = useMemo(
    () => subFilters.quality.map(label => QUALITY_METRIC_MAP[label] || label),
    [subFilters.quality]
  );

  // Nothing at all to draw for the picked days: one short message instead of a tall, empty chart
  const view = useChartView();
  const nothing = !view.loading && !view.error && view.overview !== null && !view.overview.series.some(
    (s) => s.group_type === "Quality" && mappedSubFilters.includes(s.measurement_type) && s.t.length > 0);

  if (nothing) {
    return (
      <div className="p-4 bg-white rounded shadow">
        <h3 className="mb-2 text-lg font-bold">Quality Data</h3>
        <ChartsEmpty />
      </div>
    );
  }
  return (
    <div className="p-4 bg-white rounded shadow">
      <MetricChart
        title="Quality Data"
        groupType="Quality"
        measurements={mappedSubFilters}
        height={500}
        modalOpen={modalOpen}
      />
    </div>
  );
};

export default QualityGraph;