// This file defines the WeatherGraph component for rendering weather data as time series or wind rose charts.
// It supports tab switching between graph and wind rose views, and handles wind data pairing for visualization.

import dynamic from 'next/dynamic';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/animations/tabs";

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
  inModal?: boolean;
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
  // Map frontend "Rainfall" to backend "Rain"
  const mappedWeather = subFilters.weather.map(m => m === "Rainfall" ? "Rain" : m);

  // Determine if windrose can be shown
  const hasWindSpeed = mappedWeather.includes("Wind Speed");
  const hasGustSpeed = mappedWeather.includes("Gust Speed");
  const hasWindDirection = mappedWeather.includes("Wind Direction");
  const canShowWindrose = hasWindDirection && (hasWindSpeed || hasGustSpeed);

  // Only show tab switcher in modal
  const showTabSwitcher = inModal && canShowWindrose;
  const windSpeedRoseData = getWindRoseData(data, "Wind Speed");
  const gustSpeedRoseData = getWindRoseData(data, "Gust Speed");

  return (
    <div className="p-4 bg-white rounded shadow">
      {/* Tab Switcher only in modal */}
      {showTabSwitcher && (
        <Tabs value={weatherTab} onValueChange={(value) => setWeatherTab(value as "graph" | "windrose")} className="mb-10">
          <TabsList className="grid h-10 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground w-full grid-cols-2">
            <TabsTrigger value="graph" className="font-poppins cursor-pointer">
              Weather Graph
            </TabsTrigger>
            <TabsTrigger value="windrose" className="font-poppins cursor-pointer">
              Wind Rose
            </TabsTrigger>
          </TabsList>
        </Tabs>
      )}

      {/* Render wind rose or metric chart based on tab and filters */}
      {weatherTab === "windrose" && canShowWindrose
        ? (
          <div className={`flex w-full ${hasWindSpeed && hasGustSpeed ? "flex-row gap-4" : "flex-col"}`}>
            {hasWindSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-1/2" : "w-full"}>
                <WindRose data={windSpeedRoseData} title="Wind Speed" showLegend={Object.values(activeGroups).filter(Boolean).length < 2} />
              </div>
            )}
            {hasGustSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-1/2" : "w-full"}>
                <WindRose data={gustSpeedRoseData} title="Gust Speed" showLegend={Object.values(activeGroups).filter(Boolean).length < 2} />
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