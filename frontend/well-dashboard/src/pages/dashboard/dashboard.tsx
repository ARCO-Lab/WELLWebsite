import { useState } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";
import Header from "@/components/Header";
import FilterPanel from "@/components/filters/FilterPanel";
import WeatherChart from "@/components/graphs/WeatherGraph";
import LoggerGraph from "@/components/graphs/LoggerGraph";
import QualityGraph from "@/components/graphs/QualityGraph";
import WeatherMetrics from "@/components/metrics/WeatherMetrics";
import QualityMetrics from "@/components/metrics/QualityMetrics";
import LoggerMetrics from "@/components/metrics/LoggerMetrics";
import Calendar from "@/components/filters/Calendar";


const Map = dynamic(() => import("@/components/map/Map"), { ssr: false });

export default function Dashboard() {
  const [activeGroups, setActiveGroups] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });
  const [subFilters, setSubFilters] = useState({
    weather: [] as string[],
    quality: [] as string[],
  });
  const [startDate, setStartDate] = useState<Date | null>(() => {
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    return oneWeekAgo;
  });
  const [endDate, setEndDate] = useState<Date | null>(() => {
    const today = new Date();
    return today;
  });



  
  const graphComponents = [];
    if (activeGroups.weather) graphComponents.push(<WeatherChart key="weather" />);
    if (activeGroups.quality) graphComponents.push(<QualityGraph key="quality" />);
    if (activeGroups.gauges) graphComponents.push(<LoggerGraph key="gauges" />);

    const graphCols = graphComponents.length === 1 ? "grid-cols-1" :
                    graphComponents.length === 2 ? "grid-cols-2" :
                    graphComponents.length === 3 ? "grid-cols-3" : "";
  const metricComponents = [];
    if (activeGroups.weather) metricComponents.push(<WeatherMetrics key="weather" activeKeys={subFilters.weather} />);
    if (activeGroups.quality) metricComponents.push(<QualityMetrics key="quality" />);
    if (activeGroups.gauges) metricComponents.push(<LoggerMetrics key="gauges" />);

    const metricRows = metricComponents.length === 1 ? "grid-rows-1" :
                   metricComponents.length === 2 ? "grid-rows-2" :
                   metricComponents.length === 3 ? "grid-rows-3" : "";

  return (
    <>
      <Head>
        <title>WELL Sensor Dashboard</title>
      </Head>
      <Header />
      <main className="min-h-screen p-6 text-black bg-white">
        {/* Title */}
        <h1 className="mb-6 text-3xl font-bold">WELL Sensor Dashboard</h1>

        {/* Top-level grid: 4 columns */}
        <div className="grid h-full grid-cols-4 gap-4">
          {/* Filters – full height */}
          <div className="flex flex-col justify-between col-span-1 p-4 bg-white rounded shadow">
            <div>
              <h2 className="mb-4 text-xl font-semibold">Filters</h2>
              <div className="space-y-2">
                <FilterPanel
                  activeGroups={activeGroups}
                  setActiveGroups={setActiveGroups}
                  subFilters={subFilters}
                  setSubFilters={setSubFilters}
                />
                <Calendar
                  startDate={startDate}
                  endDate={endDate}
                  onStartChange={setStartDate}
                  onEndChange={setEndDate}
                />
                <div className="mt-6 space-y-2">
                    <button className="w-full py-2 text-white bg-yellow-500 rounded hover:bg-green-600">Download</button>
                </div>
              </div>
            </div>
          </div>

          {/* Right 3/4: sensor + map + graphs */}
          <div className="flex flex-col h-full col-span-3 gap-12">
            {/* Top Row: Sensor + Map */}
            <div className="grid grid-cols-3 gap-4 flex-grow-[2] h-1/2">
                {/* Sensor Data */}
                <div className="flex flex-col h-full col-span-1 p-4 bg-white rounded shadow">
                    <h2 className="mb-2 text-xl font-semibold">Sensor Data</h2>
                    <div className="flex flex-col flex-grow gap-4">
                        {metricComponents}
                    </div>
                </div>
              {/* Map */}
              <div className="col-span-2 p-4 bg-white rounded shadow">
                <h2 className="mb-2 text-xl font-semibold">Map</h2>
                <Map activeGroups={activeGroups} />
              </div>
            </div>

            {/* Bottom Row: Graphs */}
            <div className="flex-grow p-4 bg-white rounded shadow">
              <h2 className="mb-2 text-xl font-semibold">Graphs</h2>
              <div className={`grid gap-4 ${graphCols}`}>
                {graphComponents}
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
