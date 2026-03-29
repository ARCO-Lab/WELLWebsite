// This file defines the MetricChart component for rendering time series sensor data using Highcharts.
// It supports multiple Y-axes for different units, dynamic series, and custom styling.
// Includes dynamic data aggregation for performance optimization with large datasets.

import React, { useEffect, useRef, useState } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import MouseWheelZoom from 'highcharts/modules/mouse-wheel-zoom';
import {
  smartAggregateData,
  reaggregateOnZoom,
  getAggregationStats,
  AggregationConfig,
} from '../../../utils/dataAggregation';

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

    setChartOptions({
      boost: {
        useGPUTranslations: true,
      },
      chart: {
        zoomType: 'x',
        panning: {
          enabled: true,
          type: 'x',
        },
        zooming: {
          type: 'x',
          pinchType: 'x',
          mouseWheel: {
            enabled: true,
            type: 'x',
            sensitivity: 1.05,
          },
        },
        height: resolvedHeight,
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
  }, [data, loading, activeGroup, subFilters, showLegend, resolvedHeight, modalOpen]);

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

  return (
    <div className="relative">
      {/* Show error or loading state if needed */}
      {error && <div className="text-red-500">Error: {error.message}</div>}
      {loading && <div className="text-center"></div>}
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
        ref={chartRef}
        containerProps={{ style: { height: `${resolvedHeight}px`, touchAction: 'none' } }}
      />
    </div>
  );
};

export default MetricChart;
