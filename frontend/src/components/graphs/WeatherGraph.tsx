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
  data: any;
  loading?: boolean;
  error?: any;
}

const WeatherGraph = ({ activeGroups, subFilters, startDate, endDate, modalOpen, data, loading = false, error = null }: Props) => {
  const mappedWeather = subFilters.weather.map(m => m === "Rainfall" ? "Rain" : m);

  return (
    <div className="p-4 bg-white rounded shadow">
      <MetricChart
        activeGroup="weather"
        subFilters={mappedWeather}
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