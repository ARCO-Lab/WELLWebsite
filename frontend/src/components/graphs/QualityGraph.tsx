import dynamic from 'next/dynamic';
import useFilteredData from "@/hooks/useFilteredData";

// Dynamically import MetricChart with SSR disabled
const MetricChart = dynamic(() => import("@/components/graphs/highcharts/MetricChart"), { ssr: false });

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
}

const QualityGraph = ({ activeGroups, subFilters, startDate, endDate }: Props) => {
  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);

  return (
    <div className="p-4 bg-white rounded shadow">
      <MetricChart
        activeGroup="quality"
        subFilters={subFilters.quality}
        height={500}
        startDate={startDate}
        endDate={endDate}
        data={data}
        loading={loading}
        error={error}
      />
    </div>
  );
};

export default QualityGraph;
