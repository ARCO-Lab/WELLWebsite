import dynamic from 'next/dynamic';

const MetricChart = dynamic(() => import("@/components/graphs/highcharts/MetricChart"), { ssr: false });
const WindRose = dynamic(() => import("@/components/graphs/highcharts/WindRose"), { ssr: false });

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
  weatherTab: "graph" | "windrose";
  setWeatherTab: (tab: "graph" | "windrose") => void;
  inModal?: boolean; // <-- add this prop
}

// Helper to pair direction and speed by timestamp
function getWindRoseData(data: any[], speedType: "Wind Speed" | "Gust Speed") {
  if (!Array.isArray(data)) return [];
  // Group by recorded_at
  const byTime: Record<string, { direction?: number; speed?: number }> = {};
  data.forEach((d: any) => {
    if (!d.recorded_at) return;
    if (!byTime[d.recorded_at]) byTime[d.recorded_at] = {};
    if (d.measurement_type === "Wind Direction") byTime[d.recorded_at].direction = d.value;
    if (d.measurement_type === speedType) byTime[d.recorded_at].speed = d.value;
  });
  // Only keep entries with both direction and speed
  return Object.values(byTime).filter(d => d.direction !== undefined && d.speed !== undefined) as { direction: number, speed: number }[];
}

const WeatherGraph = ({
  activeGroups,
  subFilters,
  startDate,
  endDate,
  modalOpen,
  data,
  loading = false,
  error = null,
  weatherTab,
  setWeatherTab,
  inModal = false,
}: Props) => {
  const mappedWeather = subFilters.weather.map(m => m === "Rainfall" ? "Rain" : m);

  const hasWindSpeed = mappedWeather.includes("Wind Speed");
  const hasGustSpeed = mappedWeather.includes("Gust Speed");
  const hasWindDirection = mappedWeather.includes("Wind Direction");
  const canShowWindrose = hasWindDirection && (hasWindSpeed || hasGustSpeed);

  // Only show tab switcher in modal
  const showTabSwitcher = inModal && canShowWindrose;
  const windSpeedRoseData = getWindRoseData(data, "Wind Speed");
  const gustSpeedRoseData = getWindRoseData(data, "Gust Speed");
  console.log(windSpeedRoseData);

  return (
    <div className="p-4 bg-white rounded shadow">
      {/* Tab Switcher only in modal */}
      {showTabSwitcher && (
        <div className="flex mb-4">
          <button
            className={`px-4 py-2 rounded-l cursor-pointer ${weatherTab === "graph" ? "bg-blue-600 text-white" : "bg-gray-200 text-black"}`}
            onClick={() => setWeatherTab("graph")}
          >
            Weather Graph
          </button>
          <button
            className={`px-4 py-2 rounded-r cursor-pointer ${weatherTab === "windrose" ? "bg-blue-600 text-white" : "bg-gray-200 text-black"}`}
            onClick={() => setWeatherTab("windrose")}
          >
            Windrose
          </button>
        </div>
      )}
      {/* Show windrose if selected, otherwise always show graph */}
      {weatherTab === "windrose" && canShowWindrose
        ? (
          <div className={`flex w-full ${hasWindSpeed && hasGustSpeed ? "flex-row gap-4" : "flex-col"}`}>
            {hasWindSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-1/2" : "w-full"}>
                <WindRose data={windSpeedRoseData} title = "Wind Speed" />
              </div>
            )}
            {hasGustSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-1/2" : "w-full"}>
                <WindRose data={gustSpeedRoseData} title = "Gust Speed"/>
              </div>
            )}
          </div>
        )
        : (
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
        )
      }
    </div>
  );
};

export default WeatherGraph;