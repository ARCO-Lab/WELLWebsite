// This file defines the main dashboard page for the WELL project, including sensor and sampling tabs, filters, graphs, metrics, map, and AI analysis.
// It manages all dashboard state, handles modal logic, and coordinates data fetching and UI layout.
// Each West Campus chart has its own zoom window and loads its own data (hooks/useChartWindow); the page gives them,
// through ChartPageContext, the window they start at (the picked days, or a shared link's window) and the data's extent.

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";
import type MapComponent from "@/components/map/Map";
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
import { LATEST_CARD_CLASS, LATEST_PANEL_CLASS, LatestDataError, latestGroupsClass } from "@/components/metrics/MetricList";
import Calendar from "@/components/filters/Calendar";
import Information from "@/components/Information";
import Download from "@/components/Download";
import Modal from "@/components/Modal";
import ExpandableCard from "@/components/ExpandableCard";
import EmptyState from "@/components/EmptyState";
import StickyPanel from "@/components/StickyPanel";
import { GraphFrame, LoadingOverlay } from "@/components/LoadingOverlay";
// AI ANALYSIS DISABLED: AI Analysis cards (uncomment here and in both cards below to restore)
// import AIAnalysis from "@/components/AIAnalysis";
import { ChartPageContext, type ChartPage } from "@/hooks/useChartWindow";
import {
  clampToNow, dataStart, daysCovering, hourStart, pickedDaysRange, searchWithWindow, windowFromSearch, type Range,
} from "@/utils/chartWindow";
import useLatestMetrics from "@/hooks/useLatestMetrics";
import useSampledData from "@/hooks/useSampledData";
import useRecentSamples from "@/hooks/useRecentSamples";
import { SAMPLING_FILTER_CONFIG } from "@/components/config/filters";
import { DATA_START, siteDay } from "@/utils/siteTime";
import { format, subMonths } from "date-fns";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/animations/tabs";

type ActiveFilters = { [key: string]: string[] };
type SensorGroup = "weather" | "quality" | "gauges";

// next/dynamic drops the map's generic props (sensor groups or creeks); keep them so both setters type-check.
// Until MapLibre's code has loaded, a box of the map's size says so (the map then shows its own note until it draws).
const Map = dynamic(() => import("@/components/map/Map"), {
  ssr: false,
  loading: () => (
    <div className="relative h-full min-h-[14rem] w-full rounded-lg border border-input-border bg-[#eef2f3]">
      <LoadingOverlay label="Loading map…" />
    </div>
  ),
}) as typeof MapComponent;

// The chart code, fetched as soon as a graph is wanted, so the graph cards can say "Loading graph…" in a box of a
// chart's height until it is there (instead of a bare title that later jumps open).
const loadMetricChart = () => import("@/components/graphs/highcharts/MetricChart");
const loadSampleChart = () => import("@/components/graphs/highcharts/SampleChart");

function useCodeReady(load: () => Promise<unknown>, wanted: boolean): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!wanted || ready) return;
    let live = true;
    // On failure too: the chart's own loader then shows what went wrong
    load().then(() => live && setReady(true), () => live && setReady(true));
    return () => { live = false; };
  }, [load, wanted, ready]);
  return ready;
}

// Graph cards side by side while each can be at least this wide, else stacked: rem-based, so large text stacks them.
const GRAPH_GRID: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-[repeat(auto-fit,minmax(min(100%,18rem),1fr))]",
};
const getGraphGridClass = (count: number) => GRAPH_GRID[count] ?? "grid-cols-[repeat(auto-fit,minmax(min(100%,16rem),1fr))]";

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


  // Dates are calendar days at the site (Toronto), whatever the viewer's time zone (utils/siteTime).
  // Dates for the SENSOR Tab: yesterday and today
  const [startDate, setStartDate] = useState<Date | null>(() => siteDay(-1));
  const [endDate, setEndDate] = useState<Date | null>(() => siteDay());

  // Dates for the SAMPLING Tab: all of it, from the first samples (May 1, 2025) to today
  const [samplingStartDate, setSamplingStartDate] = useState<Date | null>(() => new Date(DATA_START));
  const [samplingEndDate, setSamplingEndDate] = useState<Date | null>(() => siteDay());

  const [analysisType, setAnalysisType] = useState<"recent" | "alltime">("alltime");
  const [previousActiveCount, setPreviousActiveCount] = useState(0);
  const [previousActiveCreekCount, setPreviousActiveCreekCount] = useState(0);

  // The clock the charts go by: the start of the current hour, kept in state so rendering never reads the time. The
  // data's extent ends at the next whole hour, and so do today's picked days (clampToNow), so a page left open moves
  // on with the hours.
  const [clock, setClock] = useState(() => hourStart(Date.now()));
  useEffect(() => {
    const id = window.setInterval(() => setClock(hourStart(Date.now())), 60_000);
    return () => window.clearInterval(id);
  }, []);

  // A shared link's window (?from=&to=, read once on load): it is where every chart starts and goes back to on
  // Reset, and the date pickers show the days it covers. Picking other days drops it.
  const [linkWindow, setLinkWindow] = useState<Range | null>(null);
  const changeStartDate = useCallback((d: Date | null) => { setStartDate(d); setLinkWindow(null); }, []);
  const changeEndDate = useCallback((d: Date | null) => { setEndDate(d); setLinkWindow(null); }, []);
  const [urlRead, setUrlRead] = useState(false);
  useEffect(() => {
    const w = windowFromSearch(window.location.search, Date.now());
    if (w) {
      const { startDay, endDay } = daysCovering(w);
      setStartDate(startDay);
      setEndDate(endDay);
      setLinkWindow(w);
    }
    setUrlRead(true);
  }, []);

  const extentEnd = clock + 3_600_000;
  const picked = startDate && endDate ? clampToNow(pickedDaysRange(startDate, endDate), clock + 1) : null;
  const defaultStart = linkWindow?.start ?? picked?.start ?? extentEnd - 2 * 86_400_000;
  const defaultEnd = linkWindow?.end ?? picked?.end ?? extentEnd;
  const chartPage = useMemo<ChartPage>(() => ({
    defaultWindow: { start: defaultStart, end: Math.max(defaultEnd, defaultStart + 3_600_000) },
    extent: { start: dataStart(), end: extentEnd },
  }), [defaultStart, defaultEnd, extentEnd]);

  // The link keeps the charts' starting window: the picked days (when they aren't the default ones) or the link's
  // window. replaceState, so it adds no history entries.
  const defaultDays = useRef({ start: startDate?.toDateString(), end: endDate?.toDateString() });
  useEffect(() => {
    if (!urlRead) return;
    const isDefault = !linkWindow && startDate?.toDateString() === defaultDays.current.start
      && endDate?.toDateString() === defaultDays.current.end;
    const search = searchWithWindow(window.location.search, isDefault ? null : { start: defaultStart, end: defaultEnd });
    if (search !== window.location.search) {
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${search}${window.location.hash}`);
    }
  }, [urlRead, linkWindow, startDate, endDate, defaultStart, defaultEnd]);
  const { metrics: latestMetrics, loading: latestLoading, error: latestError, retrying: retryingLatest, retry: retryLatest } = useLatestMetrics();

  const { data: samplingData, loading: isSamplingLoading, error: samplingError } = useSampledData(
    activeCreeks,
    samplingStartDate,
    samplingEndDate
  );
  
  const { samples: recentSamples, loading: recentSamplesLoading, error: recentSamplesError, retrying: retryingRecentSamples, retry: retryRecentSamples } = useRecentSamples();

  const isAnyCreekActive = Object.values(activeCreeks).some(v => v);

  // Sampling is done in campaigns, so a picked range can hold no samples at all. Then the graphs say so, with the
  // date of the most recent samples and a button for the two months up to it, rather than moving the picked dates
  // on their own (which would hide that the data isn't recent).
  const latestSampleDay = useMemo(() => {
    let latest = "";
    for (const sample of recentSamples) if (sample.recorded_at > latest) latest = sample.recorded_at;
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(latest); // site wall-clock time; its date is the sampling day
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  }, [recentSamples]);
  const samplingRangeEmpty = isAnyCreekActive && !isSamplingLoading && !samplingError && samplingData.length === 0
    && !!samplingStartDate && !!samplingEndDate;
    

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

  // Graph cards wait for the chart code (a placeholder of a chart's height) and are aria-busy while data loads
  const sensorChartsReady = useCodeReady(loadMetricChart, activeCount > 0);
  const samplingChartsReady = useCodeReady(loadSampleChart, activeCreekCount > 0);
  const sensorGraph = (graph: React.ReactNode) => (
    <GraphFrame busy={!sensorChartsReady} waiting={!sensorChartsReady}>{graph}</GraphFrame>
  );


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
    weather: <WeatherGraph key="weather" activeGroups={activeGroups} subFilters={normalizedSubFilters} weatherTab={weatherTab} setWeatherTab={setWeatherTab} />,
    quality: <QualityGraph key="quality" activeGroups={activeGroups} subFilters={normalizedSubFilters} />,
    // modalOpen is only for the copy the modal renders (it injects it); passing it here redrew every
    // on-page logger chart whenever any modal opened
    gauges: <LoggerGraph key="gauges" subFilters={subFilters.gauges} />,
  };
  
  const graphComponents = [];
  if (activeGroups.gauges) graphComponents.push(cachedGraphs.gauges);
  if (activeGroups.weather) graphComponents.push(cachedGraphs.weather);
  if (activeGroups.quality) graphComponents.push(cachedGraphs.quality);
  
  const metricComponents = [];
  if (activeGroups.gauges) metricComponents.push(cachedMetrics.gauges);
  if (activeGroups.weather) metricComponents.push(cachedMetrics.weather);
  if (activeGroups.quality) metricComponents.push(cachedMetrics.quality);


  // The modal remembers only what it shows (a group or creek, and metrics or graphs). Its content is built from the
  // live components on every render, so it follows loading, new data, errors and the zoom window. (Storing the
  // element itself froze its props when it was opened: a chart opened while loading stayed on "Loading data…".)
  const [modalSpec, setModalSpec] = useState<{
    key: string; // weather / quality / gauges, or a creek
    type: "weather" | "logger" | "gauges" | "quality" | "sampling";
  } | null>(null);

  const openModal = (
    key: string,
    analysisType: "recent" | "alltime",
    type: "weather" | "logger" | "gauges" | "quality" | "sampling",
  ) => {
    setAnalysisType(analysisType);
    setModalSpec({ key, type });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setModalSpec(null);
    setIsModalOpen(false);
  };

  const modalIsSampling = modalSpec?.type === "sampling";
  const modalContent = !modalSpec ? null
    : modalIsSampling
      ? (analysisType === "recent" ? samplingMetricComponents : samplingGraphComponents).find((c) => c.key === modalSpec.key) ?? null
      : (analysisType === "recent" ? cachedMetrics : cachedGraphs)[modalSpec.key as SensorGroup] ?? null;
  const modalSubtypes = !modalSpec ? [] : (modalIsSampling ? samplingSubFilters : subFilters)[modalSpec.key] || [];
  const modalData = modalIsSampling
    ? (analysisType === "recent" ? recentSamples : samplingData)
    : (analysisType === "recent" ? latestMetrics : null);
  const modalType = modalSpec?.type ?? "weather";

  // Names for the "open in a larger view" buttons.
  const groupNames: Record<string, string> = { gauges: "water logger", weather: "weather", quality: "water quality" };

  return (
    <>
      <Head>
        <title>Dashboard | Watershed and Ecosystems Living Lab</title>
      </Head>

      {/* Header is hidden in iframe mode */}
      {!inIframe && <Header />}
      <ChartPageContext.Provider value={chartPage}>
      <main id="main-content" tabIndex={-1} className="min-h-screen bg-background text-foreground focus:outline-none">
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'sensor' | 'sampling')} className="p-6">
          
          {/* Title and tab triggers */}
          <div className="col-span-full mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <h1 className="text-3xl lg:text-4xl font-poppins font-bold text-primary">
              Dashboard
            </h1>
            <TabsList className="grid w-full grid-cols-2 sm:inline-flex sm:w-auto sm:grid-cols-none">
              <TabsTrigger value="sensor" className="w-full sm:w-auto">West Campus</TabsTrigger>
              <TabsTrigger value="sampling" className="w-full sm:w-auto">Ancaster Watershed</TabsTrigger>
            </TabsList>
          </div>

          {/* Sensor Tab Content (Your existing dashboard) */}
          <TabsContent value="sensor" className="mt-0" tabIndex={-1}>
            <div className="grid-mcmaster-mobile grid-mcmaster-tablet grid-mcmaster-desktop">
              {/* Filters beside the rest while both fit (rem-based widths: with large text they stack instead of clipping) */}
              <div className="col-span-full flex flex-wrap gap-6 lg:gap-8">
                
                {/* Filters Sidebar: always shown in full, and kept in view on large screens (StickyPanel) */}
                <div className="min-w-0 grow basis-[13rem]">
                  <StickyPanel className="mcmaster-card h-fit p-6">
                    <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                      Filters
                      <Information id={1} />
                    </h2>
                    <div className="space-y-4">
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
                        onStartChange={changeStartDate}
                        onEndChange={changeEndDate}
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
                          isSampling={false}
                        />
                      </div>
                    </div>
                  </StickyPanel>
                </div>

                {/* Main Content Area */}
                <div className="min-w-0 grow-[3] basis-[40rem] space-y-6">
                  
                  {/* Top Row: Latest Data + Map */}
                  <div className="flex flex-wrap gap-6">
                    
                    {/* Latest Data: one scrolling strip per group; the groups share the panel (whole, halves, thirds). Beside the map it is as tall as the map (the row stretches it); stacked, as tall as its groups. */}
                    <div className="min-w-0 grow basis-[14rem]">
                      <div className={`mcmaster-card flex h-full flex-col p-6 ${LATEST_PANEL_CLASS}`}>
                        <h2 tabIndex={-1} className="flex flex-wrap items-center justify-between gap-x-2 mb-4 text-xl font-poppins font-bold text-primary focus:outline-none">
                          Latest Data
                          <Information id={3} />
                        </h2>
                        {latestError && metricComponents.length > 0 && (
                          <LatestDataError hasValues={latestMetrics.length > 0} retrying={retryingLatest} onRetry={retryLatest} />
                        )}
                        {metricComponents.length === 0 ? (
                          <EmptyState>Tick a group under Filters, or click a sensor on the map, to see its latest readings.</EmptyState>
                        ) : (
                          <div className={latestGroupsClass(metricComponents.length)}>
                            {metricComponents.map((comp, index) => (
                              <ExpandableCard
                                key={comp.key as string}
                                label={`the latest ${groupNames[comp.key as string] ?? ""} readings`}
                                onOpen={() => openModal(comp.key as string, "recent", comp.key as "weather" | "quality" | "gauges")}
                                placement="corner" // the group's title line keeps the corner free (a float)
                                className={`${LATEST_CARD_CLASS} ${activeCount !== previousActiveCount ? 'animate-scale-in' : ''}`}
                                style={{ animationDelay: `${index * 100}ms` }}
                              >
                                {comp}
                              </ExpandableCard>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Map (taller on phones, where it's full width; beside Latest Data, as tall as it) */}
                    <div className="min-w-0 grow-[2] basis-[24rem]">
                      <div className="mcmaster-card flex h-[26rem] flex-col p-6 sm:h-full sm:min-h-[24rem] lg:min-h-[30rem]">
                        <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                          Map
                          <Information id={2} />
                        </h2>
                        <div className="min-h-0 flex-1">
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
                      const graphs = [
                        activeGroups.gauges ? cachedGraphs.gauges : null,
                        activeGroups.weather ? cachedGraphs.weather : null,
                        activeGroups.quality ? cachedGraphs.quality : null,
                      ].filter((g): g is React.ReactElement => g !== null);
                      if (graphs.length === 0) {
                        return <EmptyState>Tick a group under Filters, or click a sensor on the map, to see its graphs.</EmptyState>;
                      }
                      // One card per group, full width, one under the other: each card lays out its own charts in
                      // one to three columns, by its width
                      return (
                        <div className="space-y-6">
                          {graphs.map((comp, index) => (
                            <ExpandableCard
                              key={comp.key}
                              label={`the ${groupNames[comp.key as string] ?? ""} graphs`}
                              onOpen={() => openModal(comp.key as string, "alltime", comp.key as "weather" | "quality" | "gauges")}
                              openOnClick={false} // a tap on a chart shows its tooltip; only the button opens the larger view
                              className={`p-4 animate-fade-in-up ${activeCount !== previousActiveCount ? 'animate-scale-in' : ''}`}
                              style={{ animationDelay: `${index * 150}ms` }}
                            >
                              {sensorGraph(comp)}
                            </ExpandableCard>
                          ))}
                        </div>
                      );
                    })()}
                  </div>

                  {/* AI ANALYSIS DISABLED: sensor-tab AI Analysis card. Uncomment to restore.
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
                  */}
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Sampling Tab Content (New) */}


          <TabsContent value="sampling" tabIndex={-1}>
            <div className="grid-mcmaster-mobile grid-mcmaster-tablet grid-mcmaster-desktop">
              {/* Filters beside the rest while both fit (rem-based widths: with large text they stack instead of clipping) */}
              <div className="col-span-full flex flex-wrap gap-6 lg:gap-8">
                
                {/* Filters Sidebar: always shown in full, and kept in view on large screens (StickyPanel) */}
                <div className="min-w-0 grow basis-[13rem]">
                  <StickyPanel className="mcmaster-card h-fit p-6">
                    <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                      Filters
                      <Information id={6} />
                    </h2>
                    <div className="space-y-4">
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
                        isSampling={true}
                      />
                      {/* For researchers adding sampling files: the standard format, with example rows */}
                      <p className="pt-1 text-center text-sm text-muted">
                        Adding sampling data?{" "}
                        <a href="/api/sampling-template" download className="whitespace-nowrap font-medium text-primary underline underline-offset-2 hover:opacity-80">
                          CSV template
                        </a>
                      </p>
                      </div>
                    </div>
                  </StickyPanel>
                </div>


                {/* Main Content Area */}
                <div className="min-w-0 grow-[3] basis-[40rem] space-y-6">
                  
                  {/* Top Row: Latest Data + Map */}
                  <div className="flex flex-wrap gap-6">
                    
                    {/* Latest Data: one scrolling strip per group; the groups share the panel (whole, halves, thirds). Beside the map it is as tall as the map (the row stretches it); stacked, as tall as its groups. */}
                    <div className="min-w-0 grow basis-[14rem]">
                      <div className={`mcmaster-card flex h-full flex-col p-6 ${LATEST_PANEL_CLASS}`}>
                        <h2 tabIndex={-1} className="flex flex-wrap items-center justify-between gap-x-2 mb-4 text-xl font-poppins font-bold text-primary focus:outline-none">
                          Latest Data
                          <Information id={8} />
                        </h2>
                        {recentSamplesError && samplingMetricComponents.length > 0 && (
                          <LatestDataError hasValues={recentSamples.length > 0} retrying={retryingRecentSamples} onRetry={retryRecentSamples} />
                        )}
                        {samplingMetricComponents.length === 0 ? (
                          <EmptyState>Tick a creek under Filters, or click a site on the map, to see its latest samples.</EmptyState>
                        ) : (
                          <div className={latestGroupsClass(samplingMetricComponents.length)}>
                            {samplingMetricComponents.map((comp, index) => (
                              <ExpandableCard
                                key={comp.key as string}
                                label="the latest samples"
                                onOpen={() => openModal(comp.key as string, "recent", "sampling")}
                                placement="corner" // the group's title line keeps the corner free (a float)
                                className={`${LATEST_CARD_CLASS} ${activeCreekCount !== previousActiveCreekCount ? 'animate-scale-in' : ''}`}
                                style={{ animationDelay: `${index * 100}ms` }}
                              >
                                {comp}
                              </ExpandableCard>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Map (taller on phones, where it's full width; beside Latest Data, as tall as it) */}
                    <div className="min-w-0 grow-[2] basis-[24rem]">
                      <div className="mcmaster-card flex h-[26rem] flex-col p-6 sm:h-full sm:min-h-[24rem] lg:min-h-[30rem]">
                        <h2 className="flex items-center justify-between mb-4 text-xl font-poppins font-bold text-primary">
                          Map
                          <Information id={7} />
                        </h2>
                        <div className="min-h-0 flex-1">
                          <Map
                            activeGroups={activeCreeks}
                            setActiveGroups={setActiveCreeks}
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
                      const creekGraphCard = (comp: React.ReactElement<React.ComponentProps<typeof CreekGraph>>, key: React.Key) => (
                        <ExpandableCard
                          key={key}
                          label={`the ${SAMPLING_FILTER_CONFIG[comp.props.creekKey as keyof typeof SAMPLING_FILTER_CONFIG]?.label ?? "creek"} graphs`}
                          onOpen={() => openModal(String(comp.key), "alltime", "sampling")}
                          className="p-4 animate-fade-in-up"
                        >
                          <GraphFrame busy={!samplingChartsReady || isSamplingLoading} waiting={!samplingChartsReady}>{comp}</GraphFrame>
                        </ExpandableCard>
                      );
                      if (count === 0) {
                        return <EmptyState>Tick a creek under Filters, or click a site on the map, to see its graphs.</EmptyState>;
                      }
                      if (samplingRangeEmpty) {
                        const day = (d: Date) => format(d, "MMM d, yyyy");
                        const before = latestSampleDay && samplingStartDate && latestSampleDay < samplingStartDate;
                        const suggestedStart = latestSampleDay ? subMonths(latestSampleDay, 2) : null;
                        return (
                          <div className="rounded-lg border border-input-border bg-gray-50 p-4 text-sm text-foreground">
                            <p className="font-medium">
                              No samples from {day(samplingStartDate!)} to {day(samplingEndDate!)} for the ticked {count === 1 ? "creek" : "creeks"}.
                            </p>
                            {latestSampleDay && (
                              <p className="mt-1 text-muted">The most recent samples (from any creek) were taken on {day(latestSampleDay)}.</p>
                            )}
                            {before && suggestedStart && latestSampleDay && (
                              <button
                                type="button"
                                onClick={() => { setSamplingStartDate(suggestedStart); setSamplingEndDate(latestSampleDay); }}
                                className="btn-mcmaster-primary mt-3 min-h-10 rounded-md px-4 py-2 text-sm font-medium"
                              >
                                Show {format(suggestedStart, suggestedStart.getFullYear() === latestSampleDay.getFullYear() ? "MMM d" : "MMM d, yyyy")} – {day(latestSampleDay)}
                              </button>
                            )}
                          </div>
                        );
                      }
                      // If 3 or fewer graphs, render them in a single row with the existing logic.
                      if (count <= 3) {
                        return (
                          <div className={`grid gap-6 ${getGraphGridClass(count)}`}>
                            {samplingGraphComponents.map((comp, index) => creekGraphCard(comp, index))}
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
                            <div className={`grid gap-6 ${getGraphGridClass(3)}`}>
                              {topRow.map((comp, index) => creekGraphCard(comp, index))}
                            </div>
                            {/* Bottom Row's columns are based on how many items are left */}
                            <div className={`grid gap-6 ${getGraphGridClass(bottomRow.length)}`}>
                              {bottomRow.map((comp, index) => creekGraphCard(comp, index + 3))}
                            </div>
                          </div>
                        );
                      }
                    })()}
                  </div>
                  {/* AI ANALYSIS DISABLED: sampling-tab AI Analysis card. Uncomment to restore.
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
                  */}
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
      </ChartPageContext.Provider>
      {!inIframe && <Footer />}
    </>
  );
}