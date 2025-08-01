import React, { useState, useEffect } from "react";
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
import AIAnalysis from "@/components/AIAnalysis";
import useFilteredData from "@/hooks/useFilteredData";
import useLatestMetrics from "@/hooks/useLatestMetrics";

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

  const [weatherTab, setWeatherTab] = useState<"graph" | "windrose">("graph");

  const [open, setOpen] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });   

  const isAnyGroupActive = activeGroups.gauges || activeGroups.weather || activeGroups.quality;
  const allSubFilters = [...subFilters.weather, ...subFilters.quality, ...subFilters.gauges];


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

  const [analysisType, setAnalysisType] = useState<"recent" | "alltime">("alltime");
  const [previousActiveCount, setPreviousActiveCount] = useState(0);

  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);
  const { metrics: latestMetrics, loading: latestLoading } = useLatestMetrics();

  // Track active group count for animations
  const activeCount = Object.values(activeGroups).filter(Boolean).length;

  useEffect(() => {
    setPreviousActiveCount(activeCount);
  }, [activeCount]);

  const cachedMetrics = {
    weather: <WeatherMetrics key="weather" activeKeys={subFilters.weather} activeGroups={activeGroups} metrics={latestMetrics} loading={latestLoading} />,
    quality: <QualityMetrics key="quality" activeKeys={subFilters.quality} activeGroups={activeGroups} metrics={latestMetrics} loading={latestLoading} />,
    gauges: <LoggerMetrics key="gauges" activeKeys={subFilters.gauges} activeGroups={activeGroups} metrics={latestMetrics} loading={latestLoading} />,
  };

  const cachedGraphs = {
    weather: <WeatherGraph key="weather" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={subFilters} data={data} weatherTab={weatherTab} setWeatherTab={setWeatherTab} />,
    quality: <QualityGraph key="quality" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={subFilters} data={data}/>,
    gauges: <LoggerGraph key="gauges" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={subFilters}/>,
  };
  
  const graphComponents = [];
  if (activeGroups.gauges) graphComponents.push(cachedGraphs.gauges);
  if (activeGroups.weather) graphComponents.push(cachedGraphs.weather);
  if (activeGroups.quality) graphComponents.push(cachedGraphs.quality);
  
  const metricComponents = [];
  if (activeGroups.gauges) metricComponents.push(cachedMetrics.gauges);
  if (activeGroups.weather) metricComponents.push(cachedMetrics.weather);
  if (activeGroups.quality) metricComponents.push(cachedMetrics.quality);

  // Dynamic grid classes for responsive graphs
  const getGraphGridClass = (count: number) => {
    if (count === 1) return "grid-cols-1";
    if (count === 2) return "grid-cols-1 lg:grid-cols-2";
    if (count === 3) return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
    return "grid-cols-1";
  };

  const [modalContent, setModalContent] = useState<React.ReactNode | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalData, setModalData] = useState<any>(null);

  const openModal = (content: React.ReactNode, analysisType: "recent" | "alltime") => {
    setModalContent(content);
    setAnalysisType(analysisType)
    setModalData(data);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setModalContent(null);
    setIsModalOpen(false);
  };

  return (
    <>
      <Header />
      <main className="min-h-screen bg-background text-foreground"> 
        {/* ^change to bg-background if necessary Container with McMaster responsive grid */}
        <div className="grid-mcmaster-mobile grid-mcmaster-tablet grid-mcmaster-desktop p-6">
          
          {/* Title */}
          <div className="col-span-full mb-6">
            <h1 className="text-3xl lg:text-4xl font-poppins font-bold text-primary">
              WELL Sensor Dashboard
            </h1>
          </div>

          {/* Main Layout: Filters + Content */}
          <div className="col-span-full grid grid-cols-1 lg:grid-cols-4 gap-6 lg:gap-8">
            
            {/* Filters Sidebar */}
            <div className="lg:col-span-1">
              <div className="mcmaster-card p-6 h-fit sticky top-6">
                <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                  Filters 
                  <Information id={1} />
                </h2>
                <div className="space-y-4">
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

            {/* Main Content Area */}
            <div className="lg:col-span-3 space-y-6">
              
              {/* Top Row: Latest Data + Map */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Latest Data */}
                <div className="lg:col-span-1">
                  <div className="mcmaster-card p-6 lg:h-[30rem] flex flex-col">
                    <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                      Latest Data 
                      <Information id={3} />
                    </h2>
                    <div className="flex-1 flex flex-col min-h-0 space-y-2">
                      {metricComponents.map((comp, index) => (
                        <div
                          key={index}
                          onClick={() => openModal(
                            React.cloneElement(comp, { metrics: latestMetrics, loading: latestLoading }),
                            "recent"
                          )}
                          className={`
                            flex-1 overflow-y-auto transition-all duration-500 ease-out cursor-pointer 
                            hover:shadow-lg rounded-lg p-3 min-h-0 mcmaster-card
                            ${activeCount !== previousActiveCount ? 'animate-scale-in' : ''}
                          `}
                          style={{
                            animationDelay: `${index * 100}ms`
                          }}
                        >
                          {comp}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                
                {/* Map */}
                <div className="lg:col-span-2">
                  <div className="mcmaster-card p-6 h-96 lg:h-[30rem]">
                    <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                      Map 
                      <Information id={2} />
                    </h2>
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
              </div>
              
              {/* Graphs */}
              <div className="mcmaster-card p-6">
                <h2 className="flex items-center justify-between mb-6 text-xl font-poppins font-bold text-primary">
                  Graphs 
                  <Information id={4} />
                </h2>
                <div className={`grid gap-6 ${getGraphGridClass(graphComponents.length)}`}>
                  {graphComponents.map((comp, index) => (
                    <div
                      key={index}
                      onClick={() => openModal(
                        React.cloneElement(comp, { data, loading, error }),
                        "alltime"
                      )}
                      className={`
                        transition-all duration-500 ease-out cursor-pointer hover:shadow-lg 
                        mcmaster-card p-4 animate-fade-in-up
                        ${activeCount !== previousActiveCount ? 'animate-scale-in' : ''}
                      `}
                      style={{
                        animationDelay: `${index * 150}ms`
                      }}
                    >
                      {comp}
                    </div>
                  ))}
                </div>
              </div>

              {/* AI Analysis Section */}
              <div className="mcmaster-card p-6">
                  <h2 className="flex items-center justify-between mb-6 text-xl font-poppins font-bold text-primary">
                    AI Analysis
                    <Information id={5} />
                  </h2>
                  <div className="space-y-6">
                    <AIAnalysis
                      key="complete-analysis"
                      type="weather" // Type is a placeholder, not used by the 'complete' endpoint
                      analysisType="alltime" // Also a placeholder
                      subtypes={allSubFilters} // Pass all subfilters to trigger reset on any change
                      disabled={!isAnyGroupActive}
                    />
                  </div>
                </div>
            </div>
          </div>
        </div>

        {/* Modal for metrics/graphs */}
        <Modal
          isOpen={isModalOpen}
          onClose={closeModal}
          analysisType={analysisType}
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
          data={modalData}
          weatherTab={weatherTab}
          setWeatherTab={setWeatherTab}
        >
           {React.isValidElement(modalContent) && modalContent.props && typeof modalContent.props === "object" && "data" in modalContent.props
            ? React.cloneElement(modalContent as React.ReactElement<any>, { data: modalData, inModal: true, weatherTab, setWeatherTab })
            : modalContent}
        </Modal>
      </main>
    </>
  );
}