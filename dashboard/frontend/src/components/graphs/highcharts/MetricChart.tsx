// This file defines the MetricChart component for rendering time series sensor data using Highcharts.
// It supports multiple Y-axes for different units, dynamic series, and custom styling.
// Includes dynamic data aggregation for performance optimization with large datasets.

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Highcharts from 'highcharts/highstock';
import HighchartsReact from 'highcharts-react-official';
import MouseWheelZoom from 'highcharts/modules/mouse-wheel-zoom';
import {
  smartAggregateData,
  reaggregateOnZoom,
  getAggregationStats,
  AggregationConfig,
} from '../../../utils/dataAggregation';
import useViewportCache from '../../../hooks/useViewportCache';

if (typeof MouseWheelZoom === 'function') {
  MouseWheelZoom(Highcharts);
}

interface SensorData {
  measurement_type: string;
  unit: string;
  recorded_at: string | Date;
  value: number;
}

interface MetricChartProps {
  activeGroup: 'gauges' | 'weather' | 'quality';
  subFilters: string[];
  height?: number;
  startDate: Date | null;
  endDate: Date | null;
  data: SensorData[];
  loading: boolean;
  error: Error | null;
  modalOpen?: boolean;
  showLegend?: boolean;
}

const graphColors = ['#0866AB', '#50B748', '#F79425', '#E90D8B', '#88D1D9', '#7F488D', '#F1C232', '#CB2027'];
const MIN_VISIBLE_WINDOW_MS = 60 * 60 * 1000;

const MetricChart: React.FC<MetricChartProps> = ({
  activeGroup,
  subFilters,
  height = 500,
  startDate,
  endDate,
  data,
  loading,
  error,
  modalOpen= false,
  showLegend = true,
}) => {
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const [chartOptions, setChartOptions] = useState<any>({});
  const [resolvedHeight, setResolvedHeight] = useState(height);
  
  // Store original raw data for re-aggregation on zoom events
  const originalDataRef = useRef<Map<string, [number, number][]>>(new Map());
  // Store aggregation config
  const aggregationConfigRef = useRef<AggregationConfig>({ approximation: 'average', targetPixelWidth: 3 });
  // Track current zoom state
  const [zoomState, setZoomState] = useState<{ xMin: number; xMax: number } | null>(null);
  // Track full data extent for panning enabled/disabled logic
  const fullExtentRef = useRef<{ xMin: number; xMax: number } | null>(null);
  const pendingDateResetRef = useRef<string | null>(null);
  const rangeTrackRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    mode: 'left' | 'right' | 'center';
    startX: number;
    startMin: number;
    startMax: number;
  } | null>(null);
  const { getCachedDataForRange, clearCache: clearViewportCache, metadata: viewportCacheMetadata } = useViewportCache();

  const applyVisibleRange = useCallback((nextMin: number, nextMax: number) => {
    if (!chartRef.current?.chart) return;
    chartRef.current.chart.xAxis[0].setExtremes(nextMin, nextMax, true, false);
    setZoomState({ xMin: nextMin, xMax: nextMax });
  }, []);

  const startRangeDrag = useCallback((mode: 'left' | 'right' | 'center', clientX: number) => {
    if (!fullExtentRef.current) return;

    const current = zoomState || fullExtentRef.current;
    dragRef.current = {
      mode,
      startX: clientX,
      startMin: current.xMin,
      startMax: current.xMax,
    };

    const onMove = (e: MouseEvent) => {
      if (!dragRef.current || !fullExtentRef.current || !rangeTrackRef.current) return;

      const full = fullExtentRef.current;
      const total = full.xMax - full.xMin;
      if (total <= 0) return;

      const width = rangeTrackRef.current.clientWidth || 1;
      const deltaMs = ((e.clientX - dragRef.current.startX) / width) * total;

      let nextMin = dragRef.current.startMin;
      let nextMax = dragRef.current.startMax;
      const minWindow = Math.max(MIN_VISIBLE_WINDOW_MS, total * 0.02);

      if (dragRef.current.mode === 'center') {
        const span = dragRef.current.startMax - dragRef.current.startMin;
        nextMin = Math.max(full.xMin, dragRef.current.startMin + deltaMs);
        nextMax = nextMin + span;
        if (nextMax > full.xMax) {
          nextMax = full.xMax;
          nextMin = nextMax - span;
        }
      } else if (dragRef.current.mode === 'left') {
        nextMin = Math.min(dragRef.current.startMin + deltaMs, nextMax - minWindow);
        nextMin = Math.max(full.xMin, nextMin);
      } else {
        nextMax = Math.max(dragRef.current.startMax + deltaMs, nextMin + minWindow);
        nextMax = Math.min(full.xMax, nextMax);
      }

      applyVisibleRange(nextMin, nextMax);
    };

    const onUp = () => {
      dragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [applyVisibleRange, zoomState]);

  useEffect(() => {
    const resolveHeight = () => {
      if (typeof window === 'undefined') {
        setResolvedHeight(height);
        return;
      }

      if (modalOpen) {
        setResolvedHeight(height);
        return;
      }

      const viewportWidth = window.innerWidth;
      if (viewportWidth < 480) {
        setResolvedHeight(Math.min(height, 280));
      } else if (viewportWidth < 768) {
        setResolvedHeight(Math.min(height, 340));
      } else if (viewportWidth < 1024) {
        setResolvedHeight(Math.min(height, 420));
      } else {
        setResolvedHeight(height);
      }
    };

    resolveHeight();
    window.addEventListener('resize', resolveHeight);
    return () => window.removeEventListener('resize', resolveHeight);
  }, [height, modalOpen]);

  useEffect(() => {
    if (!data || loading) return;

    // Build chart options and series from data and subFilters
    const seriesMap: Map<string, { name: string; unit: string; data: [number, number][] }> = new Map();
    const unitMap: Map<string, number> = new Map(); // To track the index of each unique unit

    data.forEach((item) => {
      if (subFilters.includes(item.measurement_type)) {
        const key = `${item.measurement_type}_${item.unit}`;
        if (!seriesMap.has(key)) {
          seriesMap.set(key, {
            name: `${item.measurement_type} (${item.unit})`,
            unit: item.unit,
            data: [],
          });
        }
        const series = seriesMap.get(key)!;
        const timestamp = new Date(item.recorded_at).getTime() - (new Date(item.recorded_at).getTimezoneOffset() * 60 * 1000);
        series.data.push([timestamp, item.value]);

        // Check if the unit is already in the unitMap
        if (!unitMap.has(item.unit)) {
          unitMap.set(item.unit, unitMap.size); // Assign a unique index for this unit
        }
      }
    });

    // Store original raw data and determine aggregation based on chart width
    originalDataRef.current.clear();
    let chartPixelWidth = 800; // Default estimate
    
    // Try to get actual pixel width from existing chart
    if (chartRef.current?.chart?.plotWidth) {
      chartPixelWidth = chartRef.current.chart.plotWidth;
    }

    // Build series with aggregation applied
    const series = Array.from(seriesMap.values()).map((s) => {
      const rawData = s.data.sort((a, b) => a[0] - b[0]);
      
      // Store original data for re-aggregation on zoom
      const key = `${s.name}`;
      originalDataRef.current.set(key, rawData);

      // Apply aggregation
      const aggregationResult = smartAggregateData(rawData, chartPixelWidth, aggregationConfigRef.current);
      
      // Determine if we should render markers based on aggregation level
      // Disable markers for heavily aggregated data (large group size) to improve performance
      const shouldRenderMarkers = aggregationResult.groupSize <= 5;
      
      // Log aggregation stats in development
      if (process.env.NODE_ENV === 'development' && rawData.length > 100) {
        const stats = getAggregationStats(rawData.length, aggregationResult.aggregated.length);
        console.debug(`[Aggregation] ${s.name}: ${stats.reductionPercentage}% reduction, groupSize: ${stats.groupSize}, markers: ${shouldRenderMarkers}`);
      }

      return {
        type: 'line' as const,
        name: s.name,
        data: aggregationResult.aggregated,
        color: graphColors[unitMap.get(s.unit)! % graphColors.length],
        yAxis: unitMap.get(s.unit), // Associate each series with its corresponding Y-axis
        turboThreshold: 0, // Disable Highcharts' own turbo threshold to use our aggregation
        marker: {
          enabled: shouldRenderMarkers, // Only show markers when not heavily aggregated
          radius: 3,
        },
      };
    });

    // Extract and store full data extent for conditional panning
    if (originalDataRef.current.size > 0) {
      let minTs = Number.POSITIVE_INFINITY;
      let maxTs = Number.NEGATIVE_INFINITY;
      originalDataRef.current.forEach((seriesPoints) => {
        if (!seriesPoints.length) return;
        minTs = Math.min(minTs, seriesPoints[0][0]);
        maxTs = Math.max(maxTs, seriesPoints[seriesPoints.length - 1][0]);
      });

      if (Number.isFinite(minTs) && Number.isFinite(maxTs)) {
        fullExtentRef.current = {
          xMin: minTs,
          xMax: maxTs,
        };
      }
    }

    const yAxes = Array.from(unitMap.keys()).map((unit, index) => ({
      title: {
        text: null,
      },
      labels: {
        format: `{value} ${unit}`, // Append the unit to the label
      },
      opposite: index % 2 === 1,
      visible: modalOpen, // make visible on modal open
    }));

    // Compute whether currently zoomed to determine panning enablement
    const isZoomed = 
      zoomState && 
      fullExtentRef.current && 
      (Math.abs(zoomState.xMin - fullExtentRef.current.xMin) > 1 || 
       Math.abs(zoomState.xMax - fullExtentRef.current.xMax) > 1);

    setChartOptions({
      boost: {
        useGPUTranslations: true,
      },
      navigator: {
        enabled: false,
        scrollbar: {
          enabled: false,
        },
      },
      chart: {
        zoomType: 'x',
        panning: {
          enabled: isZoomed === true,
          type: 'x',
        },
        zooming: {
          type: 'x',
          pinchType: 'x',
          mouseWheel: {
            enabled: true,
            type: 'x',
            sensitivity: 2.1,
          },
        },
        height: resolvedHeight,
        spacingBottom: showLegend && series.length > 1 ? 96 : 56,
        style: { fontFamily: "Poppins, Arial, sans-serif" },
      },
      title: {
        text: `${activeGroup.charAt(0).toUpperCase() + activeGroup.slice(1)} Data`,
        style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "16px", color: "#333" },
      },
      credits: {
        enabled: false,
      },
      legend: {
        enabled: showLegend && series.length > 1,
        itemStyle: { fontFamily: "Poppins, Arial, sans-serif" },
      },
      tooltip: {
        shared: true,
        followPointer: true,
        valueDecimals: 2,
        style: { fontFamily: "Poppins, Arial, sans-serif" },
      },
      xAxis: {
        type: 'datetime',
        minRange: 60 * 60 * 1000,
        events: {
          // Handle zoom/pan events for dynamic re-aggregation
          afterSetExtremes: function (event: Highcharts.AxisSetExtremesEventObject) {
            if (event.min === undefined || event.max === undefined) return;
            setZoomState({ xMin: event.min, xMax: event.max });
          },
        },
        title: {
          text: null,
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "12px" },
        },
        labels: {
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "10px" },
        },
      },
      yAxis: yAxes.map((axis, index) => ({
        ...axis,
        title: {
          ...axis.title,
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "12px" },
        },
        labels: {
          ...axis.labels,
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "10px" },
        },
      })),
      series,
    });
  }, [data, loading, activeGroup, subFilters, showLegend, resolvedHeight, modalOpen, zoomState]);

  const legendEnabled = Boolean(chartOptions?.legend?.enabled);

  // Reset to the full visible timeline whenever the date range changes.
  useEffect(() => {
    pendingDateResetRef.current = `${startDate?.toISOString() || ''}|${endDate?.toISOString() || ''}`;
    setZoomState(null);
  }, [startDate, endDate]);

  // Apply pending date-range reset once fresh data has been processed.
  useEffect(() => {
    if (!pendingDateResetRef.current || !chartRef.current?.chart || !fullExtentRef.current) return;

    const full = fullExtentRef.current;
    chartRef.current.chart.xAxis[0].setExtremes(full.xMin, full.xMax, true, false);
    pendingDateResetRef.current = null;
  }, [data]);

  const mergeWindowPoints = (
    existing: [number, number][],
    incoming: [number, number][],
    xMin: number,
    xMax: number
  ): [number, number][] => {
    const outside = existing.filter(([ts]) => ts < xMin || ts > xMax);
    const merged = [...outside, ...incoming].sort((a, b) => a[0] - b[0]);

    // Deduplicate by timestamp, keeping the last occurrence (incoming window data should win).
    const deduped: [number, number][] = [];
    for (const point of merged) {
      if (deduped.length > 0 && deduped[deduped.length - 1][0] === point[0]) {
        deduped[deduped.length - 1] = point;
      } else {
        deduped.push(point);
      }
    }
    return deduped;
  };

  const fetchVisibleWindowData = useCallback(async (xMin: number, xMax: number) => {
    const isZoomed =
      fullExtentRef.current &&
      (Math.abs(xMin - fullExtentRef.current.xMin) > 1 ||
        Math.abs(xMax - fullExtentRef.current.xMax) > 1);

    if (!isZoomed || subFilters.length === 0) {
      return;
    }

    try {
      const rows = await getCachedDataForRange({
        minTs: xMin,
        maxTs: xMax,
        granularity: 'auto',
        prefetchAdjacent: true,
        activeGroups: {
          weather: activeGroup === 'weather',
          quality: activeGroup === 'quality',
          gauges: activeGroup === 'gauges',
        },
      });

      if (!rows.length || !chartRef.current?.chart) return;

      const incomingBySeries = new Map<string, [number, number][]>();
      rows.forEach((item) => {
        if (!subFilters.includes(item.measurement_type)) return;

        const seriesName = `${item.measurement_type} (${item.unit})`;
        const ts =
          new Date(item.recorded_at).getTime() -
          new Date(item.recorded_at).getTimezoneOffset() * 60 * 1000;
        if (!incomingBySeries.has(seriesName)) {
          incomingBySeries.set(seriesName, []);
        }
        incomingBySeries.get(seriesName)!.push([ts, item.value]);
      });

      incomingBySeries.forEach((incoming, seriesName) => {
        const sortedIncoming = incoming.sort((a, b) => a[0] - b[0]);
        const existing = originalDataRef.current.get(seriesName) || [];
        originalDataRef.current.set(
          seriesName,
          mergeWindowPoints(existing, sortedIncoming, xMin, xMax)
        );
      });

      const chart = chartRef.current.chart;
      const chartPixelWidth = chart.plotWidth || 800;
      chart.series.forEach((highchartsSeries) => {
        const originalData = originalDataRef.current.get(highchartsSeries.name);
        if (!originalData) return;

        const aggregationResult = reaggregateOnZoom(
          originalData,
          chartPixelWidth,
          xMin,
          xMax,
          aggregationConfigRef.current
        );
        highchartsSeries.setData(aggregationResult.aggregated, false);
      });
      chart.redraw();
    } catch (err: any) {
      if (process.env.NODE_ENV === 'development') {
        console.warn('[Window Fetch] Failed to fetch visible range data', err);
      }
    }
  }, [activeGroup, getCachedDataForRange, subFilters]);

  // While user scrolls/pans a zoomed view, fetch denser data for that visible window.
  useEffect(() => {
    if (!zoomState) return;

    const timeout = window.setTimeout(() => {
      fetchVisibleWindowData(zoomState.xMin, zoomState.xMax);
    }, 300);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [zoomState, fetchVisibleWindowData]);

  useEffect(() => {
    clearViewportCache();
  }, [data, activeGroup, subFilters, clearViewportCache]);

  // Handle zoom events for dynamic re-aggregation
  useEffect(() => {
    if (!zoomState || !chartRef.current?.chart) return;

    const chart = chartRef.current.chart;
    const chartPixelWidth = chart.plotWidth || 800;
    const { xMin, xMax } = zoomState;

    // Re-aggregate all series based on new zoom bounds
    chart.series.forEach((highchartsSeries, index) => {
      const seriesName = highchartsSeries.name;
      const originalData = originalDataRef.current.get(seriesName);

      if (!originalData) return;

      // Re-aggregate with new zoom bounds
      const aggregationResult = reaggregateOnZoom(
        originalData,
        chartPixelWidth,
        xMin,
        xMax,
        aggregationConfigRef.current
      );

      // Update series data with re-aggregated points
      highchartsSeries.setData(aggregationResult.aggregated, false);

      // Log re-aggregation stats in development
      if (process.env.NODE_ENV === 'development' && aggregationResult.aggregated.length > 0) {
        const stats = getAggregationStats(originalData.length, aggregationResult.aggregated.length);
        console.debug(`[Zoom Re-aggregation] ${seriesName}: ${stats.reductionPercentage}% reduction, groupSize: ${stats.groupSize}`);
      }
    });

    // Redraw chart after all series updates
    chart.redraw();
  }, [zoomState]);

  // Recalculate aggregation once chart is mounted and true pixel width is known
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!chartRef.current?.chart || !data || data.length === 0) return;

      const chart = chartRef.current.chart;
      const actualPixelWidth = chart.plotWidth || 800;
      
      // Only re-aggregate if we got a significantly different pixel width than our initial estimate
      // (This handles responsive resize on initial mount)
      const currentGroupSize = originalDataRef.current.size > 0 
        ? Math.ceil(Array.from(originalDataRef.current.values())[0].length / (chart.series[0]?.data.length || 1))
        : 1;
      
      // If pixel width might have changed significantly, recalculate aggregation for all series
      chart.series.forEach((highchartsSeries) => {
        const seriesName = highchartsSeries.name;
        const originalData = originalDataRef.current.get(seriesName);

        if (!originalData || originalData.length < 100) return; // Skip if small dataset

        const aggregationResult = smartAggregateData(originalData, actualPixelWidth, aggregationConfigRef.current);
        
        // Only update if aggregation result is significantly different (avoid unnecessary redraws)
        if (Math.abs(aggregationResult.aggregated.length - highchartsSeries.data.length) > 10) {
          highchartsSeries.setData(aggregationResult.aggregated, false);
        }
      });

      chart.redraw();
    }, 300); // Delay to let chart rendering settle

    return () => clearTimeout(timer);
  }, [data]);

  // Update panning enabled state when zoom state changes
  useEffect(() => {
    if (!chartRef.current?.chart) return;
    
    const isZoomed = 
      zoomState && 
      fullExtentRef.current && 
      (Math.abs(zoomState.xMin - fullExtentRef.current.xMin) > 1 || 
       Math.abs(zoomState.xMax - fullExtentRef.current.xMax) > 1);
    
    chartRef.current.chart.update({
      chart: {
        panning: {
          enabled: isZoomed === true,
        }
      }
    }, false);
  }, [zoomState]);

  return (
    <div className="relative">
      {/* Show error or loading state if needed */}
      {error && <div className="text-red-500">Error: {error.message}</div>}
      {loading && <div className="text-center"></div>}
      {viewportCacheMetadata.inFlightRequests > 0 && (
        <div className="absolute inset-0 z-10 animate-pulse rounded bg-gradient-to-r from-slate-200/30 via-slate-100/20 to-slate-200/30 pointer-events-none" />
      )}
      <div className="relative">
        <HighchartsReact
          highcharts={Highcharts}
          constructorType="stockChart"
          options={chartOptions}
          ref={chartRef}
          containerProps={{ style: { height: `${resolvedHeight}px`, touchAction: 'none' } }}
        />
        {fullExtentRef.current && (() => {
          const full = fullExtentRef.current;
          const activeRange = zoomState || full;
          const total = Math.max(1, full.xMax - full.xMin);
          const leftPct = ((activeRange.xMin - full.xMin) / total) * 100;
          const widthPct = ((activeRange.xMax - activeRange.xMin) / total) * 100;

          return (
            <div
              className="pointer-events-none absolute left-2 right-2"
              style={{ bottom: legendEnabled ? 52 : 12 }}
            >
              <div
                ref={rangeTrackRef}
                className="pointer-events-auto relative h-5 rounded-full border border-slate-400 bg-slate-200/95 shadow-sm"
              >
                <div
                  className="absolute top-0 h-5 rounded-full bg-slate-500/95"
                  style={{ left: `${leftPct}%`, width: `${Math.max(4, widthPct)}%` }}
                />
                <button
                  type="button"
                  aria-label="Adjust range start"
                  className="absolute top-1/2 h-8 w-6 -translate-y-1/2 cursor-ew-resize rounded-full border-2 border-slate-800 bg-white shadow-md"
                  style={{ left: `calc(${leftPct}% - 12px)` }}
                  onMouseDown={(e) => startRangeDrag('left', e.clientX)}
                >
                  <span className="mx-auto block h-4 w-[3px] rounded-full bg-slate-500" />
                </button>
                <button
                  type="button"
                  aria-label="Adjust range end"
                  className="absolute top-1/2 h-8 w-6 -translate-y-1/2 cursor-ew-resize rounded-full border-2 border-slate-800 bg-white shadow-md"
                  style={{ left: `calc(${leftPct + widthPct}% - 12px)` }}
                  onMouseDown={(e) => startRangeDrag('right', e.clientX)}
                >
                  <span className="mx-auto block h-4 w-[3px] rounded-full bg-slate-500" />
                </button>
                <button
                  type="button"
                  aria-label="Move visible range"
                  className="absolute top-0 h-5 cursor-grab active:cursor-grabbing bg-transparent"
                  style={{ left: `${leftPct}%`, width: `${Math.max(4, widthPct)}%` }}
                  onMouseDown={(e) => startRangeDrag('center', e.clientX)}
                />
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
};

export default MetricChart;
