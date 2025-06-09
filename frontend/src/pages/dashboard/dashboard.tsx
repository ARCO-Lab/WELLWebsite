import React, { useState } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";
import Header from "@/components/Header";
import FilterPanel from "@/components/filters/FilterPanel";
import WeatherGraph from "@/components/graphs/WeatherGraph";
import LoggerGraph from "@/components/graphs/LoggerGraph";
import QualityGraph from "@/components/graphs/QualityGraph";
import WeatherMetrics from "@/components/metrics/WeatherMetrics";
import QualityMetrics from "@/components/metrics/QualityMetrics";
import LoggerMetrics from "@/components/metrics/LoggerMetrics";
import Calendar from "@/components/filters/Calendar";
import Information from "@/components/Information";
import Download from "@/components/Download";
import Modal from "@/components/Modal";
import useFilteredData from "@/hooks/useFilteredData";

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
    gauges: [] as string[],
  });

  const [open, setOpen] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });   

  const [startDate, setStartDate] = useState<Date | null>(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const estStart = new Date(yesterday.toLocaleString("en-US", { timeZone: "America/Toronto" }));
    return estStart;
  });

  const [endDate, setEndDate] = useState<Date | null>(() => {
    const today = new Date();
    const estEnd = new Date(today.toLocaleString("en-US", { timeZone: "America/Toronto" }));
    return estEnd;
  });


  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);

  const cachedMetrics = {
    weather: <WeatherMetrics key="weather" activeKeys={subFilters.weather} activeGroups={activeGroups}/>,
    quality: <QualityMetrics key="quality" activeKeys={subFilters.quality} activeGroups={activeGroups}/>,
    gauges: <LoggerMetrics key="gauges" activeKeys={subFilters.gauges} activeGroups={activeGroups}/>,
  };

  const cachedGraphs = {
    weather: <WeatherGraph key="weather" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={subFilters}/>,
    quality: <QualityGraph key="quality" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={subFilters}/>,
    gauges: <LoggerGraph key="gauges" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={subFilters}/>,
  };
  
  const graphComponents = [];
  if (activeGroups.gauges) graphComponents.push(cachedGraphs.gauges);
  if (activeGroups.weather) graphComponents.push(cachedGraphs.weather);
  if (activeGroups.quality) graphComponents.push(cachedGraphs.quality);
  const graphCols = graphComponents.length === 1 ? "grid-cols-1" :
                    graphComponents.length === 2 ? "grid-cols-2" :
                    graphComponents.length === 3 ? "grid-cols-3" : "";
                    
  const metricComponents = [];
  if (activeGroups.gauges) metricComponents.push(cachedMetrics.gauges);
  if (activeGroups.weather) metricComponents.push(cachedMetrics.weather);
  if (activeGroups.quality) metricComponents.push(cachedMetrics.quality);

  // Dynamic flex basis for metrics based on count
  const getMetricFlexBasis = (count: number) => {
    if (count === 1) return "flex-1"; // 100%
    if (count === 2) return "flex-1"; // 50% each with flex-1
    if (count === 3) return "flex-1"; // 33.33% each with flex-1
    return "flex-1";
  };
                   
  const [modalContent, setModalContent] = useState<React.ReactNode | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const openModal = (content: React.ReactNode) => {
    setModalContent(content);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setModalContent(null);
    setIsModalOpen(false);
  };

  return (
    <>
      <Header />
      <main className="min-h-screen p-6 text-black bg-white">
        {/* Title */}
        <h1 className="mb-6 text-3xl font-bold">WELL Sensor Dashboard</h1>

        {/* Top-level grid: 4 columns */}
        <div className="grid h-full grid-cols-4 gap-4">
          {/* Filters – full height */}
          <div className="flex flex-col justify-between col-span-1 p-4 bg-white rounded shadow">
            <div>
              <h2 className="flex items-center justify-between mb-4 text-xl font-semibold">Filters <Information id={1}/></h2>
              <div className="space-y-2">
                <FilterPanel
                  activeGroups={activeGroups}
                  setActiveGroups={setActiveGroups}
                  subFilters={subFilters}
                  setSubFilters={setSubFilters}
                  open={open}
                  setOpen={setOpen}
                />
                <Calendar
                  startDate={startDate}
                  endDate={endDate}
                  onStartChange={setStartDate}
                  onEndChange={setEndDate}
                />
                <div className="mt-6 space-y-2">
                  <Download
                    activeGroups={activeGroups}
                    subFilters={subFilters}
                    startDate={startDate}
                    endDate={endDate}
                    data={data}
                  />

                </div>
              </div>
            </div>
          </div>

          {/* Right 3/4: sensor + map + graphs */}
          <div className="flex flex-col h-full col-span-3 gap-12">
            {/* Top Row: Sensor + Map*/}
            <div className="grid grid-cols-3 gap-4 h-96">
              {/* Latest Data */}
              <div className="flex flex-col col-span-1 p-4 bg-white rounded shadow h-96">
                <h2 className="flex items-center justify-between mb-2 text-xl font-semibold">Latest Data <Information id={3}/></h2>
                <div className="flex flex-col flex-1 min-h-0">
                  {metricComponents.map((comp, index) => (
                    <div
                      key={index}
                      onClick={() => openModal(comp)}
                      className={`${getMetricFlexBasis(metricComponents.length)} overflow-y-auto transition cursor-pointer hover:shadow-lg rounded p-2 min-h-0`}
                    >
                      {comp}
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Map */}
              <div className="col-span-2 p-4 bg-white rounded shadow h-96">
                <h2 className="flex items-center justify-between mb-2 text-xl font-semibold">Map <Information id={2}/></h2>
                <div className="h-full">
                  <Map
                    activeGroups={activeGroups}
                    setActiveGroups={setActiveGroups}
                    subFilters={subFilters}
                    setSubFilters={setSubFilters}
                    open={open}
                    setOpen={setOpen}
                  />
                </div>
              </div>
            </div>
            
            {/* Bottom Row: Graphs */}
            <div className="flex-grow p-4 bg-white rounded shadow">
              <h2 className="flex items-center justify-between mb-2 text-xl font-semibold">Graphs <Information id={4}/></h2>
              <div className={`grid gap-4 ${graphCols}`}>
                {graphComponents.map((comp, index) => (
                  <div
                    key={index}
                    onClick={() => openModal(comp)}
                    className="transition cursor-pointer hover:shadow-lg"
                  >
                    {comp}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Modal for metrics/graphs */}
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        type={
          React.isValidElement(modalContent) && modalContent.key
            ? modalContent.key === "weather"
              ? "weather"
              : modalContent.key === "quality"
                ? "quality"
                : modalContent.key === "gauges"
                  ? "logger"
                  : "weather"
            : "weather"
        }
        subtypes={
          React.isValidElement(modalContent) && modalContent.key === "weather"
            ? subFilters.weather
            : React.isValidElement(modalContent) && modalContent.key === "quality"
              ? subFilters.quality
              : React.isValidElement(modalContent) && modalContent.key === "gauges"
                ? subFilters.gauges
                : []
        }
      >
        {modalContent}
      </Modal>

    </>
  );
}