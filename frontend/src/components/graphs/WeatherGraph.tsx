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
    weather: string[];
    quality: string[];
    gauges: string[];
  };
  startDate: Date | null;
  endDate: Date | null;
  modalOpen?: boolean;
}

const WeatherGraph = ({ activeGroups, subFilters, startDate, endDate, modalOpen }: Props) => {
  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);

  return (
    <div className="p-4 bg-white rounded shadow">
      <MetricChart
        activeGroup="weather"
        subFilters={subFilters.weather}
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

export default WeatherGraph;
