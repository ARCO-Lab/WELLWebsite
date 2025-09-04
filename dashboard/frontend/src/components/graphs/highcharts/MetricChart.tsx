// This file defines the MetricChart component for rendering time series sensor data using Highcharts.
// It supports multiple Y-axes for different units, dynamic series, and custom styling.

import React, { useEffect, useRef, useState } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';

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

    const series = Array.from(seriesMap.values()).map((s) => ({
      type: 'line' as const,
      name: s.name,
      data: s.data.sort((a, b) => a[0] - b[0]),
      color: graphColors[unitMap.get(s.unit)! % graphColors.length],
      yAxis: unitMap.get(s.unit), // Associate each series with its corresponding Y-axis
    }));

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
      chart: {
        zoomType: 'x',
        height,
        style: { fontFamily: "Poppins, Arial, sans-serif" }, // <-- Add this
      },
      title: {
        text: `${activeGroup.charAt(0).toUpperCase() + activeGroup.slice(1)} Data`,
        style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "16px", color: "#333" }, // <-- Add this
      },
      credits: {
        enabled: false,
      },
      legend: {
        enabled: showLegend && series.length > 1,
        itemStyle: { fontFamily: "Poppins, Arial, sans-serif" }, // <-- Add this
      },
      tooltip: {
        shared: true,
        followPointer: true,
        valueDecimals: 2,
        style: { fontFamily: "Poppins, Arial, sans-serif" }, // <-- Add this
      },
      xAxis: {
        type: 'datetime',
        title: {
          text: null,
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "12px" }, // <-- Add this
        },
        labels: {
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "10px" }, // <-- Add this
        },
      },
      yAxis: yAxes.map((axis, index) => ({
        ...axis,
        title: {
          ...axis.title,
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "12px" }, // <-- Add this
        },
        labels: {
          ...axis.labels,
          style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "10px" }, // <-- Add this
        },
      })),
      series,
    });
  }, [data, loading, activeGroup, subFilters, showLegend, height, modalOpen]);

  return (
    <div className="relative">
      {/* Show error or loading state if needed */}
      {error && <div className="text-red-500">Error: {error.message}</div>}
      {loading && <div className="text-center"></div>}
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
        ref={chartRef}
        containerProps={{ style: { height: `${height}px` } }}
      />
    </div>
  );
};

export default MetricChart;
