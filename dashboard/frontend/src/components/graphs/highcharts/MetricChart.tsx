// This file defines the MetricChart component: one West Campus sensor chart (a group, or one water logger),
// drawn with Highcharts from the series /api/series returns (see hooks/useChartSeries). It has one Y-axis per unit.
//
// Zoom is shared: every chart shows the page's one view window (ChartView.viewWindow). Dragging across a chart
// (or pinching on a touch screen) asks for a new window instead of zooming this chart alone, and the window bar
// above the charts moves, widens or resets it. The mouse wheel and one-finger touch still scroll the page.
//
// Options are applied to the chart in three separate steps, so each change redraws only what it touches: data
// (series and axes), layout (height, legend, title) and the window (x-axis extremes).

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
// Screen-reader descriptions and keyboard navigation for every chart (Highcharts warns without it).
import 'highcharts/modules/accessibility';
import { seriesKey, useChartView } from '@/hooks/useChartSeries';
import { MIN_RANGE_MS, TIME_ZONE, composePoints, resolutionBadge, type Range } from '@/utils/chartWindow';

interface MetricChartProps {
  title: string;
  groupType: 'Weather' | 'Quality' | 'Logger';
  stationId?: string; // only this station's series (the water loggers)
  measurements: string[]; // measurement_type values to show
  height?: number;
  modalOpen?: boolean;
  showLegend?: boolean;
  // Small multiples (the logger charts) show one error message and one resolution badge for the group instead.
  showErrorBanner?: boolean;
  showBadge?: boolean;
}

const graphColors = ['#0866AB', '#50B748', '#F79425', '#E90D8B', '#88D1D9', '#7F488D', '#F1C232', '#CB2027'];
const FONT = 'Poppins, Arial, sans-serif';

const MetricChart: React.FC<MetricChartProps> = ({
  title,
  groupType,
  stationId,
  measurements,
  height = 500,
  modalOpen = false,
  showLegend = true,
  showErrorBanner = true,
  showBadge = true,
}) => {
  const view = useChartView();
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const [resolvedHeight, setResolvedHeight] = useState(height);

  useEffect(() => {
    const resolveHeight = () => {
      if (modalOpen) {
        setResolvedHeight(height);
        return;
      }
      const viewportWidth = window.innerWidth;
      if (viewportWidth < 480) setResolvedHeight(Math.min(height, 280));
      else if (viewportWidth < 768) setResolvedHeight(Math.min(height, 340));
      else if (viewportWidth < 1024) setResolvedHeight(Math.min(height, 420));
      else setResolvedHeight(height);
    };
    resolveHeight();
    window.addEventListener('resize', resolveHeight);
    return () => window.removeEventListener('resize', resolveHeight);
  }, [height, modalOpen]);

  // The chart's event handlers are bound once, so they reach the latest zoomTo through a ref.
  const zoomRef = useRef(view.zoomTo);
  zoomRef.current = view.zoomTo;
  // A pinch in progress: only this chart follows the fingers; the shared window is set once, when they lift.
  const pinchRef = useRef<Range | null>(null);
  const layoutRef = useRef({ modalOpen, showLegend });
  layoutRef.current = { modalOpen, showLegend };

  // Created once; everything that changes later goes through chart.update / setExtremes below.
  const [initialOptions] = useState<Highcharts.Options>(() => {
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    return {
      time: { timezone: TIME_ZONE },
      chart: {
        height: resolvedHeight,
        animation: !reducedMotion,
        style: { fontFamily: FONT },
        // Drag (mouse) and pinch (touch) pick a range; the selection handler turns it into the shared window.
        zooming: { type: 'x', pinchType: 'x', resetButton: { theme: { style: { display: 'none' } } } },
        events: {
          selection(e) {
            if (e.resetSelection) zoomRef.current(null);
            else if (e.xAxis?.[0]) zoomRef.current({ start: e.xAxis[0].min, end: e.xAxis[0].max });
            return false; // don't zoom this chart on its own: the window comes back as xAxis min/max
          },
        },
      },
      title: { text: title, style: { fontFamily: FONT, fontSize: '16px', color: '#333' } },
      subtitle: { text: undefined, style: { fontFamily: FONT, fontSize: '11px', color: '#4b5563' } },
      credits: { enabled: false },
      legend: { enabled: false, itemStyle: { fontFamily: FONT } },
      tooltip: { shared: true, followPointer: true, valueDecimals: 2, style: { fontFamily: FONT } },
      plotOptions: { series: { animation: !reducedMotion, connectNulls: false } },
      xAxis: {
        type: 'datetime',
        minRange: MIN_RANGE_MS,
        title: { text: null },
        labels: { style: { fontFamily: FONT, fontSize: '10px' } },
        events: {
          // A pinch sets this chart's extremes with a trigger ('touchmove', on every move: kept until the
          // fingers lift, so the other charts don't redraw each frame). Programmatic changes (the window, data
          // updates) have no trigger and are ignored, so charts never feed back into each other.
          afterSetExtremes(e) {
            if (e.trigger === 'touchmove') pinchRef.current = { start: e.min, end: e.max };
            else if (e.trigger) zoomRef.current({ start: e.min, end: e.max });
          },
        },
      },
      yAxis: [],
      series: [],
    };
  });

  // Data: this chart's series, overview outside the detail range and detail inside it.
  const { series, yAxes, hasData, hasTotals } = useMemo(() => {
    const ov = view.overview;
    if (!ov) return { series: [], yAxes: [], hasData: false, hasTotals: false };
    const unitIndex = new Map<string, number>();
    const picked = ov.series.filter((s) => s.group_type === groupType
      && (stationId === undefined || String(s.station_id) === stationId)
      && measurements.includes(s.measurement_type));
    const detail = view.detail;
    const built = picked.map((s) => {
      if (!unitIndex.has(s.unit)) unitIndex.set(s.unit, unitIndex.size);
      const key = seriesKey(s);
      const points = composePoints(s, ov.bucketS, detail
        ? { values: detail.byKey.get(key), bucketS: detail.bucketS, range: detail.range }
        : undefined);
      return {
        id: key,
        type: 'line' as const,
        name: `${s.measurement_type} (${s.unit})`,
        data: points,
        color: graphColors[unitIndex.get(s.unit)! % graphColors.length],
        yAxis: unitIndex.get(s.unit)!,
      };
    });
    const axes = Array.from(unitIndex.keys()).map((unit, index) => ({
      title: { text: undefined },
      labels: { format: `{value} ${unit}`, style: { fontFamily: FONT, fontSize: '10px' } },
      opposite: index % 2 === 1,
    }));
    return {
      series: built,
      yAxes: axes,
      hasData: built.some((s) => s.data.length > 0),
      hasTotals: picked.some((s) => s.agg === 'sum'),
    };
  }, [view.overview, view.detail, groupType, stationId, measurements]);

  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    const { modalOpen: open, showLegend: legend } = layoutRef.current;
    chart.update({
      yAxis: yAxes.map((a) => ({ ...a, visible: open })),
      series,
      legend: { enabled: legend && series.length > 1 },
    }, true, true, false); // one-to-one: series and axes that went away are removed; no animation on updates
  }, [series, yAxes]);

  // Layout: never touches the data.
  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    chart.update({
      chart: { height: resolvedHeight },
      title: { text: title },
      legend: { enabled: showLegend && chart.series.length > 1 },
    }, false, false, false);
    chart.yAxis.forEach((axis) => axis.update({ visible: modalOpen }, false));
    chart.redraw(false);
  }, [resolvedHeight, title, showLegend, modalOpen]);

  // The window: the shared view, or the whole picked range.
  const win: Range | null = view.viewWindow ?? view.range;
  useEffect(() => {
    const axis = chartRef.current?.chart?.xAxis[0];
    if (!axis || !win) return;
    axis.setExtremes(win.start, win.end, true, false); // no trigger: afterSetExtremes ignores it
  }, [win, series]);

  const isEmpty = !view.loading && !view.error && view.overview !== null && !hasData;

  // The resolution badge ("12-hour averages") as the chart's subtitle, so it never covers the title.
  const badge = showBadge ? resolutionBadge(view.shownBucketS, view.shownAggregated, hasTotals) : null;
  useEffect(() => {
    chartRef.current?.chart?.setSubtitle({ text: badge ?? '' });
  }, [badge]);

  // A drag that zooms ends in a click; keep it from reaching the card around the chart, which would open the
  // larger view. A plain click (or tap) still does.
  const pointerDown = useRef<{ x: number; y: number } | null>(null);
  const onPointerDown = (e: React.PointerEvent) => { pointerDown.current = { x: e.clientX, y: e.clientY }; };
  const onTouchEnd = (e: React.TouchEvent) => {
    if (pinchRef.current && e.touches.length < 2) {
      zoomRef.current(pinchRef.current);
      pinchRef.current = null;
    }
  };
  const onClickCapture = (e: React.MouseEvent) => {
    const d = pointerDown.current;
    if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 5) e.stopPropagation();
  };

  return (
    <div className="relative" onPointerDown={onPointerDown} onClickCapture={onClickCapture}
      onTouchEnd={onTouchEnd} onTouchCancel={onTouchEnd}>
      <HighchartsReact
        highcharts={Highcharts}
        options={initialOptions}
        allowChartUpdate={false}
        ref={chartRef}
        containerProps={{ style: { height: `${resolvedHeight}px` } }}
      />
      {/* While a new range loads, the previous chart stays visible under a spinner. It is announced once for all
          charts (ChartWindowBar), not by each chart. */}
      {view.loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded bg-white/70" aria-hidden="true">
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <span className="h-4 w-4 motion-safe:animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" />
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
      {/* Announced once for all charts by the window bar's live region, so hidden from screen readers here */}
      {view.error && !view.loading && showErrorBanner && (
        <div className="absolute inset-x-4 top-12 z-10 mx-auto max-w-xl rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700 shadow-sm" aria-hidden="true">
          {view.error.message}
        </div>
      )}
    </div>
  );
};

export default MetricChart;
