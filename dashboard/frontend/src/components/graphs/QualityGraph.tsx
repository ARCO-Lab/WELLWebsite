// This file defines the QualityGraph component for rendering water quality time series data using MetricChart.
// It maps frontend metric labels to backend keys and filters data for the "Quality" group.

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
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
  startDate: Date | null;
  endDate: Date | null;
  modalOpen?: boolean;
  data: any;
  loading?: boolean;
  error?: any;
}

const QualityGraph = ({ activeGroups, subFilters, startDate, endDate, modalOpen, data, loading = false, error = null, }: Props) => {
  // Map frontend metric labels to backend keys if needed
  const mappedSubFilters = subFilters.quality.map(
    label => QUALITY_METRIC_MAP[label] || label
  );

  // Filter data for the "Quality" group
  const qualityData = useMemo(() => {
    if (!data || !Array.isArray(data)) return [];
    return data.filter(item => item.group_type === 'Quality');
  }, [data]);

  return (
    <div className="p-4 bg-white rounded shadow">
      <MetricChart
        activeGroup="quality"
        subFilters={mappedSubFilters}
        height={500}
        startDate={startDate}
        endDate={endDate}
        data={qualityData}
        loading={loading}
        error={error}
        modalOpen={modalOpen}
      />
    </div>
  );
};

export default QualityGraph;