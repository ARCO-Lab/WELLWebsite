// This file defines the WeatherGraph component for rendering weather data as time series or wind rose charts.
// It supports tab switching between graph and wind rose views, and handles wind data pairing for visualization.
// The chart's series and the wind rose's raw readings both come from the page (useChartView).

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { Tabs, TabsList, TabsTrigger } from "@/components/animations/tabs";
import { useChartView } from "@/hooks/useChartSeries";

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
  modalOpen?: boolean;
  weatherTab: "graph" | "windrose";
  setWeatherTab: (tab: "graph" | "windrose") => void;
  inModal?: boolean;
}

// Frontend weather labels to backend measurement types.
export const mapWeatherMetrics = (labels: string[]) => labels.map(m => m === "Rainfall" ? "Rain" : m);

// The wind rose needs Wind Direction and a speed.
export function canShowWindRose(weatherLabels: string[]): boolean {
  const m = mapWeatherMetrics(weatherLabels);
  return m.includes("Wind Direction") && (m.includes("Wind Speed") || m.includes("Gust Speed"));
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
  modalOpen,
  weatherTab,
  setWeatherTab,
  inModal = false,
}: Props) => {
  // Map frontend "Rainfall" to backend "Rain". Memoized: a new array on every render made the chart
  // rebuild all its series whenever anything on the page re-rendered.
  const mappedWeather = useMemo(() => mapWeatherMetrics(subFilters.weather), [subFilters.weather]);
  const { wind } = useChartView();

  // Determine if windrose can be shown
  const hasWindSpeed = mappedWeather.includes("Wind Speed");
  const hasGustSpeed = mappedWeather.includes("Gust Speed");
  const canShowWindrose = canShowWindRose(subFilters.weather);

  // Only show tab switcher in modal
  const showTabSwitcher = inModal && canShowWindrose;
  // Only build the wind rose (two passes over every row) when it's actually shown
  const showWindrose = weatherTab === "windrose" && canShowWindrose;
  const windSpeedRoseData = useMemo(() => (showWindrose && hasWindSpeed ? getWindRoseData(wind.data, "Wind Speed") : []), [showWindrose, hasWindSpeed, wind.data]);
  const gustSpeedRoseData = useMemo(() => (showWindrose && hasGustSpeed ? getWindRoseData(wind.data, "Gust Speed") : []), [showWindrose, hasGustSpeed, wind.data]);

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
      {showWindrose
        ? (
          <div className={`relative flex w-full ${hasWindSpeed && hasGustSpeed ? "flex-col gap-4 lg:flex-row" : "flex-col"}`}>
            {/* The raw readings load only when this tab opens: the same overlay and message as the charts */}
            {wind.loading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center rounded bg-white/70">
                <p className="flex items-center gap-2 text-sm text-gray-700" role="status">
                  <span aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" />
                  Loading data…
                </p>
              </div>
            )}
            {wind.error && !wind.loading && (
              <div className="absolute inset-x-4 top-12 z-10 mx-auto max-w-xl rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700 shadow-sm" role="alert">
                {wind.error.message}
              </div>
            )}
            {hasWindSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-full lg:w-1/2" : "w-full"}>
                <WindRose data={windSpeedRoseData} title="Wind Speed" showLegend={Object.values(activeGroups).filter(Boolean).length < 2} />
              </div>
            )}
            {hasGustSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-full lg:w-1/2" : "w-full"}>
                <WindRose data={gustSpeedRoseData} title="Gust Speed" showLegend={Object.values(activeGroups).filter(Boolean).length < 2} />
              </div>
            )}
          </div>
        )
        : (
          <MetricChart
            title="Weather Data"
            groupType="Weather"
            measurements={mappedWeather}
            height={500}
            modalOpen={modalOpen}
          />
        )
      }
    </div>
  );
};

export default WeatherGraph;
