// This file defines the WeatherGraph component: the weather station's selected readings, all in one chart (a y-axis
// per unit: temperatures, humidity, pressure, rain as bars, wind speeds, wind direction as points, solar radiation,
// soil water; see MetricChart); or, in the larger view, the wind rose for the picked days, counted by the database
// (/api/windrose, see hooks/useWindRose) only while it is shown.

import dynamic from 'next/dynamic';
import { useContext, useMemo } from 'react';
import { Tabs, TabsList, TabsTrigger } from "@/components/animations/tabs";
import { SENSOR_STATIONS } from '@/components/config/filters';
import { ChartPageContext } from '@/hooks/useChartWindow';
import useWindRose from '@/hooks/useWindRose';
import { cardSeries } from '@/utils/cardSeries';
import { windowLabel } from '@/components/graphs/ChartToolbar';
import ChartErrorBoundary from './ChartErrorBoundary';

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

const WeatherGraph = ({
  activeGroups,
  subFilters,
  modalOpen,
  weatherTab,
  setWeatherTab,
  inModal = false,
}: Props) => {
  // Memoized: a new array on every render would rebuild the charts whenever anything on the page re-rendered
  const mappedWeather = useMemo(() => mapWeatherMetrics(subFilters.weather), [subFilters.weather]);
  const { series, axes } = useMemo(
    () => cardSeries('Weather', [{ id: SENSOR_STATIONS.weather, name: 'Weather station' }], mappedWeather),
    [mappedWeather]
  );
  const page = useContext(ChartPageContext);

  const hasWindSpeed = mappedWeather.includes("Wind Speed");
  const hasGustSpeed = mappedWeather.includes("Gust Speed");
  const canShowWindrose = canShowWindRose(subFilters.weather);
  const showTabSwitcher = inModal && canShowWindrose; // only in the larger view
  // The wind rose only in the larger view, where its tab is: the card on the page always shows the chart, whatever tab
  // the larger view was left on
  const showWindrose = inModal && weatherTab === "windrose" && canShowWindrose;
  const wind = useWindRose(page?.defaultWindow ?? null, showWindrose);
  const period = page ? windowLabel(page.defaultWindow, page.defaultWindow.end) : undefined;

  const tabs = showTabSwitcher ? (
    <Tabs value={weatherTab} onValueChange={(value) => setWeatherTab(value as "graph" | "windrose")} className="mb-6">
      <TabsList className="grid h-10 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground w-full grid-cols-2">
        <TabsTrigger value="graph" className="font-poppins cursor-pointer">Weather Graph</TabsTrigger>
        <TabsTrigger value="windrose" className="font-poppins cursor-pointer">Wind Rose</TabsTrigger>
      </TabsList>
    </Tabs>
  ) : null;

  if (showWindrose) {
    return (
      <div className="rounded bg-white p-4 shadow">
        {tabs}
        <div className={`relative flex w-full ${hasWindSpeed && hasGustSpeed ? "flex-col gap-4 lg:flex-row" : "flex-col"}`}>
          {/* The counts load only when this tab opens: the same overlay and message as the charts */}
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
              <WindRose data={wind.data} speed="Wind Speed" title="Wind Speed" period={period} />
            </div>
          )}
          {hasGustSpeed && (
            <div className={hasWindSpeed && hasGustSpeed ? "w-full lg:w-1/2" : "w-full"}>
              <WindRose data={wind.data} speed="Gust Speed" title="Gust Speed" period={period} />
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded bg-white p-4 shadow max-sm:p-0 max-sm:shadow-none">
      {tabs}
      {series.length === 0 ? (
        <>
          <h3 className="mb-2 text-lg font-bold">Weather Station</h3>
          <p className="text-sm text-muted">
            {mappedWeather.includes("Wind Direction")
              ? "Wind direction is shown on the wind rose (with Wind Speed or Gust Speed ticked, in the larger view). Tick another measurement under Weather Station in Filters to chart it."
              : "Tick a measurement under Weather Station in Filters to see its readings."}
          </p>
        </>
      ) : (
        <ChartErrorBoundary title="Weather Station">
          <MetricChart id="weather" title="Weather Station" series={series} axes={axes} modalOpen={modalOpen} />
        </ChartErrorBoundary>
      )}
    </div>
  );
};

export default WeatherGraph;
