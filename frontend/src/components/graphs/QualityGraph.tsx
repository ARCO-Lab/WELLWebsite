import dynamic from 'next/dynamic';
import useFilteredData from "@/hooks/useFilteredData";

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
}


const QualityGraph = ({ activeGroups, subFilters, startDate, endDate, modalOpen }: Props) => {
  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);

  const mappedSubFilters = subFilters.quality.map(
    label => QUALITY_METRIC_MAP[label] || label
  );

  return (
    <div className="p-4 bg-white rounded shadow">
      <MetricChart
        activeGroup="quality"
        subFilters={mappedSubFilters}
        height={500}
        startDate={startDate}
        endDate={endDate}
        data={data}
        loading={loading}
        error={error}
        modalOpen={modalOpen}
      />
    </div>
  );
};

export default QualityGraph;
