// This file defines the WeatherGraph component: the weather station's readings as small charts, one per unit
// (°C, %, mbar, mm, m/s…), instead of one chart mixing them all on one axis, or (in the larger view) the wind
// rose. All the small charts follow the page's one zoom window. The series come from the page (useChartView), and
// the wind rose's counts from /api/windrose (useWindRose), only while it is shown.

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { Tabs, TabsList, TabsTrigger } from "@/components/animations/tabs";
import { useChartView } from "@/hooks/useChartSeries";
import { resolutionBadge } from "@/utils/chartWindow";
import { weatherPanels } from "@/utils/chartStyle";
import ChartsEmpty from "@/components/graphs/ChartsEmpty";

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
  // Map frontend "Rainfall" to backend "Rain". Memoized: a new array on every render made the charts
  // rebuild all their series whenever anything on the page re-rendered.
  const mappedWeather = useMemo(() => mapWeatherMetrics(subFilters.weather), [subFilters.weather]);
  const view = useChartView();
  const availableKey = (view.overview?.series ?? []).filter((s) => s.group_type === "Weather")
    .map((s) => s.measurement_type).sort().join("|");
  const panels = useMemo(
    () => weatherPanels(mappedWeather, new Set(availableKey.split("|"))),
    [mappedWeather, availableKey]
  );
  const { wind } = view;

  const hasWindSpeed = mappedWeather.includes("Wind Speed");
  const hasGustSpeed = mappedWeather.includes("Gust Speed");
  const canShowWindrose = canShowWindRose(subFilters.weather);
  // Only show tab switcher in modal
  const showTabSwitcher = inModal && canShowWindrose;
  const showWindrose = weatherTab === "windrose" && canShowWindrose;

  const badge = resolutionBadge(view.shownBucketS, view.shownAggregated, mappedWeather.includes("Rain"));
  // Nothing at all to draw for the picked days: one short message instead of a stack of empty charts
  const nothing = !view.loading && !view.error && view.overview !== null && !view.overview.series.some(
    (s) => s.group_type === "Weather" && mappedWeather.includes(s.measurement_type) && s.t.length > 0);
  const roseLegend = Object.values(activeGroups).filter(Boolean).length < 2;

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

      {showWindrose
        ? (
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
                <WindRose data={wind.data} speed="Wind Speed" title="Wind Speed" showLegend={roseLegend} />
              </div>
            )}
            {hasGustSpeed && (
              <div className={hasWindSpeed && hasGustSpeed ? "w-full lg:w-1/2" : "w-full"}>
                <WindRose data={wind.data} speed="Gust Speed" title="Gust Speed" showLegend={roseLegend} />
              </div>
            )}
          </div>
        )
        : (
          <div className="@container">
            <h3 className="mb-2 flex flex-wrap items-baseline gap-x-3 text-lg font-bold">
              Weather Data
              {badge && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-normal text-gray-600">{badge}</span>}
            </h3>
            {/* One message for all the small charts; screen readers hear it once, from the window bar's live region */}
            {view.error && !view.loading && (
              <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700" aria-hidden="true">
                {view.error.message}
              </div>
            )}
            {nothing
              ? <ChartsEmpty />
              : (
                // One column on a phone or in a narrow card, two or three where there is room (the card's width,
                // not the window's, decides: three cards side by side are each narrow)
                <div className="grid grid-cols-1 gap-3 @xl:grid-cols-2 @5xl:grid-cols-3">
                  {panels.map((p) => (
                    <MetricChart
                      key={p.title}
                      title={p.title}
                      groupType="Weather"
                      measurements={p.measurements}
                      height={modalOpen ? 300 : 240}
                      modalOpen={modalOpen}
                      showYAxis
                      showErrorBanner={false}
                      showBadge={false}
                    />
                  ))}
                </div>
              )}
          </div>
        )
      }
    </div>
  );
};

export default WeatherGraph;
