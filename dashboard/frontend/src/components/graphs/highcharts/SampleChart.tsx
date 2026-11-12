// This file defines the SampleChart component: one Ancaster Watershed sampling site's readings over time, drawn
// from raw rows with Highcharts. It supports multiple Y-axes for different units. Each measurement has its own colour,
// line style and marker (utils/samplingStyle); the legend is the card's (CreekGraph), shared by its charts, so it
// takes no room from the plots and can show or hide a measurement in all of them at once. (The West Campus sensor charts
// use MetricChart, which draws aggregated series from /api/series and zooms.)

import React, { useEffect, useRef, useState } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
// Screen-reader descriptions and keyboard navigation for every chart (Highcharts warns without it).
import 'highcharts/modules/accessibility';
import { displayUnit } from '@/utils/chartStyle';
import { samplingStyle } from '@/utils/samplingStyle';

interface SensorData {
  measurement_type: string;
  unit: string;
  recorded_at: string | Date;
  value: number;
}

interface SampleChartProps {
  siteName: string; // the chart's title: "<site> Data"
  subFilters: string[];
  hiddenMetrics?: string[]; // measurements switched off in the card's legend
  height?: number;
  startDate: Date | null;
  endDate: Date | null;
  data: SensorData[];
  loading: boolean;
  error: Error | null;
  modalOpen?: boolean;
  // Small multiples (the logger charts) show one error message for the group instead of one each.
  showErrorBanner?: boolean;
}

const NONE: string[] = [];

const SampleChart: React.FC<SampleChartProps> = ({
  siteName,
  subFilters,
  hiddenMetrics = NONE,
  height = 500,
  startDate,
  endDate,
  data,
  loading,
  error,
  modalOpen= false,
  showErrorBanner = true,
}) => {
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  // Until the first data arrives: no Highcharts placeholder title ("Chart title") or credits link.
  const [chartOptions, setChartOptions] = useState<Highcharts.Options>({ title: { text: undefined }, credits: { enabled: false } });
  const [resolvedHeight, setResolvedHeight] = useState(height);

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
    const seriesMap: Map<string, { measurement: string; name: string; unit: string; data: [number, number][] }> = new Map();
    const unitMap: Map<string, number> = new Map(); // To track the index of each unique unit

    data.forEach((item) => {
      if (subFilters.includes(item.measurement_type)) {
        const key = `${item.measurement_type}_${item.unit}`;
        if (!seriesMap.has(key)) {
          const unit = displayUnit(item.unit);
          seriesMap.set(key, {
            measurement: item.measurement_type,
            name: unit ? `${item.measurement_type} (${unit})` : item.measurement_type,
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

    const series = Array.from(seriesMap.values()).map((s) => {
      const style = samplingStyle(s.measurement);
      return {
        type: 'line' as const,
        name: s.name,
        data: s.data.sort((a, b) => a[0] - b[0]),
        color: style.color,
        dashStyle: style.dash,
        lineWidth: 2,
        marker: { enabled: true, radius: 3.5, symbol: style.marker },
        visible: !hiddenMetrics.includes(s.measurement),
        yAxis: unitMap.get(s.unit), // Associate each series with its corresponding Y-axis
      };
    });

    const yAxes = Array.from(unitMap.keys()).map((unit, index) => ({
      // No axis title: Highcharts only draws one when the text is non-empty (its types don't allow null here)
      title: {
        text: '',
      },
      labels: {
        format: displayUnit(unit) ? `{value} ${displayUnit(unit)}` : '{value}', // Append the unit to the label
      },
      opposite: index % 2 === 1,
      visible: modalOpen, // make visible on modal open
    }));

    setChartOptions({
      chart: {
        zooming: { type: 'x' }, // what the deprecated zoomType: 'x' maps to
        height: resolvedHeight,
        style: { fontFamily: "Poppins, Arial, sans-serif" }, // <-- Add this
      },
      title: {
        text: `${siteName} Data`,
        style: { fontFamily: "Poppins, Arial, sans-serif", fontSize: "16px", color: "#333" }, // <-- Add this
      },
      credits: {
        enabled: false,
      },
      // The card shows one legend for all its charts (CreekGraph), so no plot is squeezed by its own
      legend: { enabled: false },
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
  }, [data, loading, siteName, subFilters, hiddenMetrics, resolvedHeight, modalOpen]);

  const isEmpty = !loading && !error && Array.isArray(chartOptions.series)
    && chartOptions.series.every((s) => !('data' in s && Array.isArray(s.data) && s.data.length));

  return (
    <div className="relative">
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
        ref={chartRef}
        containerProps={{ style: { height: `${resolvedHeight}px` } }}
      />
      {/* While a new range loads, the previous chart stays visible under a spinner. Screen readers hear it once per
          card (CreekGraph), not once per chart. */}
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded bg-white/70" aria-hidden="true">
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <span className="h-4 w-4 motion-safe:animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" aria-hidden="true" />
            Loading data…
          </div>
        </div>
      )}
      {/* A chart with nothing to draw says so instead of showing empty axes (e.g. Logger 5, whose water sensor is dead) */}
      {isEmpty && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="rounded-md bg-white/90 px-3 py-1.5 text-sm text-muted">No readings in this period</p>
        </div>
      )}
      {/* e.g. "This range has 1,451,713 readings, more than …": the API explains what to do instead */}
      {error && !loading && showErrorBanner && (
        <div className="absolute inset-x-4 top-12 z-10 mx-auto max-w-xl rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700 shadow-sm" role="alert">
          {error.message}
        </div>
      )}
    </div>
  );
};

export default SampleChart;
