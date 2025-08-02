import React, { useState, useEffect } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";
import Header from "@/components/Header";
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
import { SAMPLING_METRICS } from "@/components/config/filters";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/animations/tabs";

const Map = dynamic(() => import("@/components/map/Map"), { ssr: false });

export default function Dashboard() {

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
  const [previousActiveCreekCount, setPreviousActiveCreekCount] = useState(0);


  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);
  const { metrics: latestMetrics, loading: latestLoading } = useLatestMetrics();

  const { data: samplingData, loading: isSamplingLoading, error: samplingError } = useSampledData(
    activeCreeks,
    startDate,
    endDate
  );
  
  const { samples: recentSamples, loading: recentSamplesLoading } = useRecentSamples();

  const isAnyCreekActive = Object.values(activeCreeks).some(v => v);
    
  const cachedSamplingMetrics = {
    creeks: <CreekMetrics key="creeks" subFilters={samplingSubFilters} metrics={recentSamples} loading={recentSamplesLoading} />
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
        startDate={startDate}
        endDate={endDate}
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
  const [isModalOpen, setIsModalOpen] = useState(false);
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
      <Header />
      <main className="min-h-screen bg-background text-foreground">
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'sensor' | 'sampling')} className="p-6">
          
          {/* Title and Tab Triggers */}
          <div className="col-span-full mb-6 flex justify-between items-center">
            <h1 className="text-3xl lg:text-4xl font-poppins font-bold text-primary">
              WELL Dashboard
            </h1>
            <TabsList>
              <TabsTrigger value="sensor">Sensor</TabsTrigger>
              <TabsTrigger value="sampling">Sampling</TabsTrigger>
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
                      <FilterPanel
                        activeTab={activeTab}
                        activeGroups={activeGroups}
                        setActiveGroups={setActiveGroups}
                        subFilters={subFilters}
                        setSubFilters={setSubFilters}
                        activeCreeks={activeCreeks}
                        setActiveCreeks={setActiveCreeks}
                        samplingSubFilters={samplingSubFilters}
                        setSamplingSubFilters={setSamplingSubFilters}
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
                            "alltime",
                            comp.key as any, // 'weather', 'quality', or 'gauges'
                            subFilters[comp.key as string] || []
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
                      <FilterPanel
                        activeTab={activeTab}
                        activeGroups={activeCreeks}
                        setActiveGroups={setActiveCreeks}
                        subFilters={samplingSubFilters}
                        setSubFilters={setSamplingSubFilters}
                        activeCreeks={activeCreeks}
                        setActiveCreeks={setActiveCreeks}
                        samplingSubFilters={samplingSubFilters}
                        setSamplingSubFilters={setSamplingSubFilters}
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
                          activeGroups={activeCreeks}
                          subFilters={samplingSubFilters}
                          startDate={startDate}
                          endDate={endDate}
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
                            setActiveGroups={setActiveCreeks}
                            subFilters={samplingSubFilters}
                            setSubFilters={setSamplingSubFilters}
                            open={open}
                            setOpen={setOpen}
                            isSampling={true}
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
    </>
  );
}