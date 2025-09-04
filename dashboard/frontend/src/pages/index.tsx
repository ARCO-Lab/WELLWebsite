// This file defines the main dashboard page for the WELL project, including sensor and sampling tabs, filters, graphs, metrics, map, and AI analysis.
// It manages all dashboard state, handles modal logic, and coordinates data fetching and UI layout.

import React, { useState, useEffect } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import FilterPanel from "@/components/filters/FilterPanel";
import WeatherGraph from "@/components/graphs/WeatherGraph";
import LoggerGraph from "@/components/graphs/LoggerGraph";
import QualityGraph from "@/components/graphs/QualityGraph";
import CreekGraph from "@/components/graphs/CreekGraph";
import WeatherMetrics from "@/components/metrics/WeatherMetrics";
import QualityMetrics from "@/components/metrics/QualityMetrics";
import LoggerMetrics from "@/components/metrics/LoggerMetrics";
import CreekMetrics from "@/components/metrics/CreekMetrics";
import Calendar from "@/components/filters/Calendar";
import Information from "@/components/Information";
import Download from "@/components/Download";
import Modal from "@/components/Modal";
import AIAnalysis from "@/components/AIAnalysis";
import useFilteredData from "@/hooks/useFilteredData";
import useLatestMetrics from "@/hooks/useLatestMetrics";
import useSampledData from "@/hooks/useSampledData";
import useRecentSamples from "@/hooks/useRecentSamples";
import { SENSOR_FILTER_CONFIG } from "@/components/config/filters";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/animations/tabs";

type ActiveFilters = { [key: string]: string[] };

const Map = dynamic(() => import("@/components/map/Map"), { ssr: false });

export default function Dashboard() {

  const [inIframe, setInIframe] = useState(false);

  const [activeTab, setActiveTab] = useState<"sensor" | "sampling">("sensor");
  
  const [activeGroups, setActiveGroups] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });

  const [subFilters, setSubFilters] = useState<{ [key: string]: string[] }>({
    gauges: [],
    weather: [],
    quality: [],
  });

  // State for Sampling Tab
  const [activeCreeks, setActiveCreeks] = useState({
    ancaster: false,
    tiffany: false,
    sulphur: false,
    coldwater: false,
    spencer: false,
  });

  const [samplingSubFilters, setSamplingSubFilters] = useState<{ [key: string]: string[] }>({
    ancaster: [],
    tiffany: [],
    sulphur: [],
    coldwater: [],
    spencer: [],
  });

  // UI State for Collapsibles
  const [open, setOpen] = useState({
    gauges: false,
    weather: false,
    quality: false,
    ancaster: false,
    tiffany: false,
    sulphur: false,
    coldwater: false,
    spencer: false,
  });

  const [weatherTab, setWeatherTab] = useState<"graph" | "windrose">("graph");

  const isAnyGroupActive = activeGroups.gauges || activeGroups.weather || activeGroups.quality;
  const allSubFilters = [...subFilters.weather, ...subFilters.quality, ...subFilters.gauges];
  const [chevronState, setChevronState] = useState<{ [key: string]: boolean }>({});
  
  // Create the activeFilters object for the SENSOR tab
  const sensorActiveFilters = Object.entries(activeGroups)
    .filter(([, isActive]) => isActive)
    .reduce((acc, [groupKey]) => {
      acc[groupKey] = subFilters[groupKey];
      return acc;
    }, {} as ActiveFilters);

  // Create the activeFilters object for the SAMPLING tab
  const samplingActiveFilters = Object.entries(activeCreeks)
    .filter(([, isActive]) => isActive)
    .reduce((acc, [creekKey]) => {
      acc[creekKey] = samplingSubFilters[creekKey];
      return acc;
    }, {} as ActiveFilters);


  // Dates for the SENSOR Tab
  const [startDate, setStartDate] = useState<Date | null>(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return new Date(yesterday.toLocaleString("en-US", { timeZone: "America/Toronto" }));
  });
  const [endDate, setEndDate] = useState<Date | null>(() => {
    const today = new Date();
    return new Date(today.toLocaleString("en-US", { timeZone: "America/Toronto" }));
  });

  // Dates for the SAMPLING Tab
  const [samplingStartDate, setSamplingStartDate] = useState<Date | null>(() => {
    const twoMonthsAgo = new Date();
    twoMonthsAgo.setMonth(twoMonthsAgo.getMonth() - 2);
    return new Date(twoMonthsAgo.toLocaleString("en-US", { timeZone: "America/Toronto" }));
  });
  const [samplingEndDate, setSamplingEndDate] = useState<Date | null>(() => {
    const today = new Date();
    return new Date(today.toLocaleString("en-US", { timeZone: "America/Toronto" }));
  });

  const [analysisType, setAnalysisType] = useState<"recent" | "alltime">("alltime");
  const [previousActiveCount, setPreviousActiveCount] = useState(0);
  const [previousActiveCreekCount, setPreviousActiveCreekCount] = useState(0);

  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);
  const { metrics: latestMetrics, loading: latestLoading } = useLatestMetrics();

  const { data: samplingData, loading: isSamplingLoading, error: samplingError } = useSampledData(
    activeCreeks,
    samplingStartDate,
    samplingEndDate
  );
  
  const { samples: recentSamples, loading: recentSamplesLoading } = useRecentSamples();

  const isAnyCreekActive = Object.values(activeCreeks).some(v => v);
    
  const cachedSamplingMetrics = {
    creeks: <CreekMetrics key="creeks" subFilters={samplingSubFilters} /* Error necessary */ metrics={recentSamples} loading={recentSamplesLoading} />
  };
  

  const samplingMetricComponents = Object.entries(activeCreeks)
    .filter(([, isActive]) => isActive)
    .map(([creekKey]) => (
      <CreekMetrics
        key={creekKey}
        creekKey={creekKey as keyof typeof activeCreeks}
        subFilters={samplingSubFilters[creekKey] || []}
        metrics={recentSamples}
        loading={recentSamplesLoading}
      />
    ));

    // --- SAMPLING COMPONENT LOGIC ---
  const samplingGraphComponents = Object.entries(activeCreeks)
    .filter(([key, isActive]) => isActive)
    .map(([key]) => (
      <CreekGraph
        key={key}
        creekKey={key as keyof typeof activeCreeks}
        subFilters={samplingSubFilters[key] || []}
        startDate={samplingStartDate}
        endDate={samplingEndDate}
        data={samplingData}
        loading={isSamplingLoading}
        error={samplingError}
      />
    ));


  // Track active group count for animations
  const activeCount = Object.values(activeGroups).filter(Boolean).length;
  const activeCreekCount = Object.values(activeCreeks).filter(Boolean).length;


  useEffect(() => {
    setPreviousActiveCount(activeCount);
  }, [activeCount]);

  useEffect(() => {
    setPreviousActiveCreekCount(activeCreekCount);
  }, [activeCreekCount]);

  useEffect(() => {
    try {
      setInIframe(window.self !== window.top);
    } catch {
      setInIframe(true);
    }
  }, []);



  const cachedMetrics = {
    weather: <WeatherMetrics key="weather" activeKeys={subFilters.weather} activeGroups={activeGroups} metrics={latestMetrics} loading={latestLoading} />,
    quality: <QualityMetrics key="quality" activeKeys={subFilters.quality} activeGroups={activeGroups} metrics={latestMetrics} loading={latestLoading} />,
    gauges: <LoggerMetrics key="gauges" activeKeys={subFilters.gauges} activeGroups={activeGroups} metrics={latestMetrics} loading={latestLoading} />,
  };

  const normalizedSubFilters = {
    weather: subFilters.weather || [],
    quality: subFilters.quality || [],
    gauges: subFilters.gauges || [],
  };
  
  const [isModalOpen, setIsModalOpen] = useState(false);

  const cachedGraphs = {
    weather: <WeatherGraph key="weather" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={normalizedSubFilters} data={data} weatherTab={weatherTab} setWeatherTab={setWeatherTab} />,
    quality: <QualityGraph key="quality" activeGroups={activeGroups} startDate={startDate} endDate={endDate} subFilters={normalizedSubFilters} data={data}/>,
    gauges: <LoggerGraph key="gauges" startDate={startDate} endDate={endDate} subFilters={subFilters.gauges} data={data} modalOpen={isModalOpen} />,
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
    if (count === 1) {
      return "grid-cols-1";
    }
    if (count === 2) {
      return "grid-cols-1 lg:grid-cols-2";
    }
    // For 3 or more items, use a 3-column grid and let it wrap.
    if (count >= 3) {
      return "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
    }
    // Default for 0 items.
    return "grid-cols-1";
  };

  const [modalContent, setModalContent] = useState<React.ReactNode | null>(null);
  const [modalData, setModalData] = useState<any>(null);
  const [modalType, setModalType] = useState<"weather" | "logger" | "quality" | "sampling">("weather");
  const [modalSubtypes, setModalSubtypes] = useState<string[]>([]);



  const openModal = (
    content: React.ReactNode, 
    analysisType: "recent" | "alltime",
    type: "weather" | "logger" | "quality" | "sampling",
    subtypes: string[] = []
  ) => {
    setModalContent(content);
    setAnalysisType(analysisType);
    setModalType(type);
    setModalSubtypes(subtypes);
    
    // Set the correct data source based on the type
    if (type === 'sampling') {
      setModalData(analysisType === 'recent' ? recentSamples : samplingData);
    } else {
      setModalData(analysisType === 'recent' ? latestMetrics : data);
    }

    setIsModalOpen(true);
  };

  const closeModal = () => {
    setModalContent(null);
    setIsModalOpen(false);
  };

  return (
    <>

      {/* Header is hidden in iframe mode */}
      {!inIframe && <Header />}
      <main className="min-h-screen bg-background text-foreground">
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'sensor' | 'sampling')} className="p-6">
          
          {/* Title, tab triggers, and warning for sampling tab */}
          <div className="col-span-full mb-6 flex justify-between items-center">
            <h1 className="text-3xl lg:text-4xl font-poppins font-bold text-primary">
              WELL Dashboard
            </h1>
          {/* REMOVE ONCE REAL DATA IS AVAILABLE */}
            {activeTab === "sampling" && (
              <div className="flex-1 flex justify-center">
                <div className="bg-yellow-100 border border-yellow-400 text-yellow-800 px-4 py-2 rounded text-center font-semibold mx-4">
                  NOTE: This is mock data at the moment, will be updated in the future with real data.
                </div>
              </div>
            )}
            <TabsList>
              <TabsTrigger value="sensor">West Campus</TabsTrigger>
              <TabsTrigger value="sampling">Ancaster Watershed</TabsTrigger>
            </TabsList>
          </div>

          {/* Sensor Tab Content (Your existing dashboard) */}
          <TabsContent value="sensor" className="mt-0">
            <div className="grid-mcmaster-mobile grid-mcmaster-tablet grid-mcmaster-desktop">
              <div className="col-span-full grid grid-cols-1 lg:grid-cols-4 gap-6 lg:gap-8">
                
                {/* Filters Sidebar */}
                <div className="lg:col-span-1">
                  <div className="mcmaster-card p-6 h-fit sticky top-6">
                    <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                      Filters 
                      <Information id={1} />
                    </h2>
                    <div className="space-y-4">
                       {/* Errors necessary */}
                      <FilterPanel
                        activeTab={activeTab}
                        activeGroups={activeGroups}
                        setActiveGroups={setActiveGroups}
                        subFilters={{
                          weather: subFilters.weather || [],
                          quality: subFilters.quality || [],
                          gauges: subFilters.gauges || [],
                        }}
                        setSubFilters={setSubFilters}
                        activeCreeks={activeCreeks}
                        setActiveCreeks={setActiveCreeks}
                        samplingSubFilters={samplingSubFilters}
                        setSamplingSubFilters={setSamplingSubFilters}
                        open={open}
                        setOpen={setOpen}
                        chevronState={chevronState}
                        setChevronState={setChevronState}
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
                          subFilters={{
                            weather: subFilters.weather || [],
                            quality: subFilters.quality || [],
                            gauges: subFilters.gauges || [],
                          }}
                          startDate={startDate}
                          endDate={endDate}
                          data={data}
                          isSampling={false}
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
                      <div className="mcmaster-card p-6 lg:min-h-[30rem] flex flex-col">
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
                                "recent",
                                comp.key as any, // 'weather', 'quality', or 'gauges'
                                subFilters[comp.key as string] || []
                              )}
                              className={`
                                transition-all duration-500 ease-out cursor-pointer 
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
                      <div className="mcmaster-card p-6 h-96 lg:h-[30rem] flex flex-col">
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
                            chevronState={chevronState}
                            setChevronState={setChevronState}
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
                    
                    {(() => {
                      // --- START: NEW DYNAMIC LAYOUT LOGIC ---

                      // 1. Calculate how many loggers are actually selected
                      const loggerConfig = SENSOR_FILTER_CONFIG.gauges;
                      const allLoggerIds = Object.keys(loggerConfig.sites);
                      let selectedLoggerCount = 0;
                      if (subFilters.gauges?.includes('All Loggers')) {
                        selectedLoggerCount = allLoggerIds.length;
                      } else {
                        selectedLoggerCount = subFilters.gauges?.filter(id => allLoggerIds.includes(id)).length || 0;
                      }

                      // 2. Get the graph components that are currently active
                      const loggerGraph = activeGroups.gauges ? cachedGraphs.gauges : null;
                      const weatherGraph = activeGroups.weather ? cachedGraphs.weather : null;
                      const qualityGraph = activeGroups.quality ? cachedGraphs.quality : null;

                      // 3. RENDER SPECIAL LAYOUT: If more than 2 loggers are selected
                      if (selectedLoggerCount > 2) {
                        const otherGraphs = [weatherGraph, qualityGraph].filter(Boolean);
                        return (
                          <div className="space-y-6">
                            {/* Row 1: Logger Graph takes the full width */}
                            {loggerGraph && (
                              <div
                                onClick={() => openModal(loggerGraph, "alltime", "logger", subFilters.gauges || [])}
                                className="transition-all duration-500 ease-out cursor-pointer hover:shadow-lg mcmaster-card p-4 animate-fade-in-up"
                              >
                                {loggerGraph}
                              </div>
                            )}
                            {/* Row 2: Weather and Quality graphs in a responsive grid below */}
                            <div className={`grid gap-6 ${getGraphGridClass(otherGraphs.length)}`}>
                              {otherGraphs.map((comp) =>
                                comp && (
                                  <div
                                    key={comp.key}
                                    onClick={() => openModal(comp, "alltime", comp.key as any, subFilters[comp.key as string] || [])}
                                    className="transition-all duration-500 ease-out cursor-pointer hover:shadow-lg mcmaster-card p-4 animate-fade-in-up"
                                  >
                                    {comp}
                                  </div>
                                )
                              )}
                            </div>
                          </div>
                        );
                      }

                      // 4. RENDER NORMAL LAYOUT: If 2 or fewer loggers are selected
                      const allGraphs = [loggerGraph, weatherGraph, qualityGraph].filter(Boolean);
                      return (
                        <div className={`grid gap-6 ${getGraphGridClass(allGraphs.length)}`}>
                          {allGraphs.map((comp, index) => (
                            comp ? (
                              <div
                                key={comp.key}
                                onClick={() => openModal(comp, "alltime", comp.key as any, subFilters[comp.key as string] || [])}
                                className={`
                                  transition-all duration-500 ease-out cursor-pointer hover:shadow-lg 
                                  mcmaster-card p-4 animate-fade-in-up
                                  ${activeCount !== previousActiveCount ? 'animate-scale-in' : ''}
                                `}
                                style={{ animationDelay: `${index * 150}ms` }}
                              >
                                {comp}
                              </div>
                            ) : null
                          ))}
                        </div>
                      );
                      // --- END: NEW DYNAMIC LAYOUT LOGIC ---
                    })()}
                  </div>

                  {/* AI Analysis Section */}
                  <div className="mcmaster-card p-6">
                      <h2 className="flex items-center justify-between mb-6 text-xl font-poppins font-bold text-primary">
                        AI Analysis
                        <Information id={5} />
                      </h2>
                      <div className="space-y-6">
                        <AIAnalysis
                          key="sensor-analysis"
                          activeFilters={sensorActiveFilters}
                          dashboardTab="sensors"
                          analysisType={analysisType}
                          disabled={!isAnyGroupActive}
                        />
                      </div>
                    </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Sampling Tab Content (New) */}


          <TabsContent value="sampling">
            <div className="grid-mcmaster-mobile grid-mcmaster-tablet grid-mcmaster-desktop">
              <div className="col-span-full grid grid-cols-1 lg:grid-cols-4 gap-6 lg:gap-8">
                
                {/* Filters Sidebar */}
                <div className="lg:col-span-1">
                  <div className="mcmaster-card p-6 h-fit sticky top-6">
                    <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                      Filters 
                      <Information id={6} />
                    </h2>
                    <div className="space-y-4">
                       {/* Errors necessary */}
                      <FilterPanel
                        activeTab={activeTab}
                        activeGroups={{}}  // Empty object for sampling mode
                        setActiveGroups={() => {}}  // Empty function for sampling mode
                        subFilters={{}}  // Empty object for sampling mode
                        setSubFilters={() => {}}  // Empty function for sampling mode
                        activeCreeks={activeCreeks}  // ✅ Correct
                        setActiveCreeks={setActiveCreeks}  // ✅ Correct
                        samplingSubFilters={samplingSubFilters}  // ✅ Correct
                        setSamplingSubFilters={setSamplingSubFilters}  // ✅ Correct
                        open={open}
                        setOpen={setOpen}
                        chevronState={chevronState}
                        setChevronState={setChevronState}
                      />
                      <Calendar
                        startDate={samplingStartDate}
                        endDate={samplingEndDate}
                        onStartChange={setSamplingStartDate}
                        onEndChange={setSamplingEndDate}
                      />
                      <div className="mt-6 space-y-2">
                      <Download
                        activeGroups={{ gauges: false, weather: false, quality: false }}  // All false for sampling mode
                        subFilters={{ weather: [], quality: [], gauges: [] }}  // Empty for sampling mode
                        activeCreeks={activeCreeks}  // ✅ Correct prop name
                        samplingSubFilters={samplingSubFilters}  // ✅ Correct prop name
                        startDate={samplingStartDate}
                        endDate={samplingEndDate}
                        data={samplingData}
                        isSampling={true}
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
                      <div className="mcmaster-card p-6 lg:min-h-[30rem] flex flex-col">
                        <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                          Latest Data 
                          <Information id={8} />
                        </h2>
                        <div className="flex-1 flex flex-col min-h-0 space-y-2">
                          {samplingMetricComponents.map((comp, index) => (
                            <div
                              key={index}
                              onClick={() => openModal(
                                React.cloneElement(comp, { metrics: recentSamples, loading: recentSamplesLoading }),
                                "recent",
                                "sampling",
                                comp.props.subFilters
                              )}
                              className={`
                                transition-all duration-500 ease-out cursor-pointer 
                                hover:shadow-lg rounded-lg p-3 min-h-0 mcmaster-card
                                ${activeCreekCount !== previousActiveCreekCount ? 'animate-scale-in' : ''}
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
                      <div className="mcmaster-card p-6 lg:min-h-[30rem] flex flex-col h-full">
                        <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                          Map 
                          <Information id={7} />
                        </h2>
                        <div className="flex-1">
                          <Map
                            activeGroups={activeCreeks}
                            setActiveGroups={() => {}} // No-op to satisfy type, since Map expects sensor groups setter
                            subFilters={samplingSubFilters}
                            setSubFilters={setSamplingSubFilters}
                            open={open}
                            setOpen={setOpen}
                            isSampling={true}
                            chevronState={chevronState}
                            setChevronState={setChevronState}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                  {/* Graphs */}
                  <div className="mcmaster-card p-6">
                    <h2 className="flex items-center justify-between mb-6 text-xl font-poppins font-bold text-primary">
                      Graphs 
                      <Information id={9} />
                    </h2>
                    
                    {(() => {
                      const count = samplingGraphComponents.length;
                      // If 3 or fewer graphs, render them in a single row with the existing logic.
                      if (count <= 3) {
                        return (
                          <div className={`grid gap-6 ${getGraphGridClass(count)}`}>
                            {samplingGraphComponents.map((comp, index) => (
                              <div
                                key={index}
                                onClick={() => openModal(
                                  comp, 
                                  "alltime", 
                                  "sampling", 
                                  comp.props.subFilters
                                )}
                                className="transition-all duration-500 ease-out cursor-pointer hover:shadow-lg mcmaster-card p-4 animate-fade-in-up"
                              >
                                {comp}
                              </div>
                            ))}
                          </div>
                        );
                      } 
                      // If more than 3 graphs, split them into two distinct rows.
                      else {
                        const topRow = samplingGraphComponents.slice(0, 3);
                        const bottomRow = samplingGraphComponents.slice(3);
                        return (
                          <div className="space-y-6">
                            {/* Top Row is always 3 columns */}
                            <div className="grid gap-6 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                            {topRow.map((comp, index) => (
                                <div
                                  key={index}
                                  onClick={() => openModal(
                                    comp, 
                                    "alltime", 
                                    "sampling", 
                                    comp.props.subFilters
                                  )}
                                  className="transition-all duration-500 ease-out cursor-pointer hover:shadow-lg mcmaster-card p-4 animate-fade-in-up"
                                >
                                  {comp}
                                </div>
                              ))}
                            </div>
                            {/* Bottom Row's columns are based on how many items are left */}
                            <div className={`grid gap-6 ${getGraphGridClass(bottomRow.length)}`}>
                              {bottomRow.map((comp, index) => (
                                <div
                                  key={index + 3} // Use an offset key
                                  onClick={() => openModal(
                                    comp, 
                                    "alltime", 
                                    "sampling", 
                                    comp.props.subFilters
                                  )}
                                  className="transition-all duration-500 ease-out cursor-pointer hover:shadow-lg mcmaster-card p-4 animate-fade-in-up"
                                >
                                  {comp}
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      }
                    })()}
                  </div>
                  {/* AI Analysis Section */}
                  <div className="mcmaster-card p-6">
                      <h2 className="flex items-center justify-between mb-6 text-xl font-poppins font-bold text-primary">
                        AI Analysis
                        <Information id={10} />
                      </h2>
                      <div className="space-y-6">
                        <AIAnalysis
                          key="sampling-analysis"
                          activeFilters={samplingActiveFilters}
                          dashboardTab="sampling"
                          analysisType={analysisType}
                          disabled={!isAnyCreekActive}
                        />
                      </div>
                    </div>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>



        {/* Modal for metrics/graphs */}
        <Modal
          isOpen={isModalOpen}
          onClose={closeModal}
          analysisType={analysisType}
          type={modalType}
          subtypes={modalSubtypes}
          data={modalData}
          weatherTab={weatherTab}
          setWeatherTab={setWeatherTab}
        >
           {modalContent}
        </Modal>
      </main>
      {!inIframe && <Footer />}
    </>
  );
}