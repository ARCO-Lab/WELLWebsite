// This file defines the MetricChart component: one West Campus sensor chart (a group, or one water logger),
// drawn with Highcharts from the series /api/series returns (see hooks/useChartSeries). It has one Y-axis per unit.
// Each measurement has a fixed colour and axis side (utils/chartStyle), the same on every logger and every load.
// Averaged lines get a light min–max band behind them; rain (a total per bucket) is drawn as bars and wind
// direction (an angle) as points on a 0–360° axis.
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
// arearange, for the min–max band
import 'highcharts/highcharts-more';
// Screen-reader descriptions and keyboard navigation for every chart (Highcharts warns without it).
import 'highcharts/modules/accessibility';
import { seriesKey, useChartView } from '@/hooks/useChartSeries';
import { MIN_RANGE_MS, TIME_ZONE, composeBand, composePoints, resolutionBadge, type Range } from '@/utils/chartWindow';
import { COMPASS, compassLabel, hasBand, seriesColor, seriesType } from '@/utils/chartStyle';

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
  showYAxis?: boolean; // default: only in the larger view (a card chart with two units has no room for both)
}

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
  showYAxis,
}) => {
  const yAxisVisible = showYAxis ?? modalOpen;
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
  const layoutRef = useRef({ yAxisVisible, showLegend });
  layoutRef.current = { yAxisVisible, showLegend };

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
      title: { text: title, style: { fontFamily: FONT, fontSize: height < 300 ? '14px' : '16px', color: '#333' } },
      subtitle: { text: undefined, style: { fontFamily: FONT, fontSize: '11px', color: '#4b5563' } },
      credits: { enabled: false },
      legend: { enabled: false, itemStyle: { fontFamily: FONT, fontSize: '11px' }, margin: 4, padding: 4 },
      tooltip: { shared: true, followPointer: true, valueDecimals: 2, style: { fontFamily: FONT } },
      plotOptions: {
        series: { animation: !reducedMotion, connectNulls: false },
        column: { pointPadding: 0, groupPadding: 0, borderWidth: 0, grouping: false },
        scatter: { marker: { radius: 2, symbol: 'circle' } },
        arearange: { lineWidth: 0, fillOpacity: 0.18, marker: { enabled: false } },
      },
      accessibility: {
        // One landmark per chart (not one per series)
        landmarkVerbosity: 'one',
      },
      xAxis: {
        type: 'datetime',
        minRange: MIN_RANGE_MS,
        title: { text: null },
        // Short labels that never wrap or get cut to "12:00…"; Highcharts spaces the ticks to fit them
        tickPixelInterval: 90,
        dateTimeLabelFormats: { hour: '%H:%M', day: '%b %e', week: '%b %e', month: "%b '%y" },
        labels: { style: { fontFamily: FONT, fontSize: '10px', textOverflow: 'none', whiteSpace: 'nowrap' } },
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

  // Data: this chart's series, overview outside the detail range and detail inside it. Sorted by the order of
  // `measurements` (the filter list), so colours, axes and the legend never depend on the order rows arrive in.
  const { series, yAxes, hasData, hasTotals } = useMemo(() => {
    const ov = view.overview;
    if (!ov) return { series: [], yAxes: [], hasData: false, hasTotals: false };
    const rank = (m: string) => measurements.indexOf(m);
    const picked = ov.series
      .filter((s) => s.group_type === groupType
        && (stationId === undefined || String(s.station_id) === stationId)
        && measurements.includes(s.measurement_type))
      .sort((a, b) => rank(a.measurement_type) - rank(b.measurement_type) || a.unit.localeCompare(b.unit));
    // One axis per unit, on the side its first measurement's place in the filter list gives it (so a logger whose
    // water level sensor is dead still shows temperature on the right, like the others)
    const units = new Map<string, { index: number; opposite: boolean; angle: boolean }>();
    for (const s of picked) {
      if (!units.has(s.unit)) {
        units.set(s.unit, { index: units.size, opposite: rank(s.measurement_type) % 2 === 1, angle: s.agg === 'vector_mean' });
      }
    }
    const detail = view.detail;
    const built: Highcharts.SeriesOptionsType[] = [];
    let hasPoints = false;
    for (const s of picked) {
      const key = seriesKey(s);
      const d = detail ? { values: detail.byKey.get(key), bucketS: detail.bucketS, range: detail.range } : undefined;
      const points = composePoints(s, ov.bucketS, d);
      hasPoints ||= points.some(([, v]) => v !== null);
      const color = seriesColor(s.measurement_type);
      const yAxis = units.get(s.unit)!.index;
      const type = seriesType(s.agg);
      const label = `${s.measurement_type} (${s.unit})`;
      if (hasBand(s.agg, ov.aggregated) && s.min && s.max) {
        built.push({
          id: `${key}|band`, linkedTo: key, type: 'arearange', name: `${s.measurement_type} min–max`,
          data: composeBand(s, ov.bucketS, d), color, yAxis, zIndex: 0,
          tooltip: { valueSuffix: ` ${s.unit}` },
        });
      }
      if (type === 'scatter') {
        built.push({
          id: key, type, name: label, data: points.filter(([, v]) => v !== null), color, yAxis, zIndex: 1,
          tooltip: {
            pointFormatter() {
              return `<span style="color:${this.color}">●</span> ${s.measurement_type}: <b>${compassLabel(this.y ?? 0)}</b><br/>`;
            },
          },
        });
      } else {
        built.push({ id: key, type, name: label, data: points, color, yAxis, zIndex: 1, tooltip: { valueSuffix: ` ${s.unit}` } });
      }
    }
    const axes: Highcharts.YAxisOptions[] = Array.from(units.entries()).map(([unit, a]) => ({
      // The unit goes in the axis title, so the labels stay short ("38.9", not "38.889 m asl", which wrapped); a
      // chart with one unit has it in its own title already
      title: { text: a.angle || units.size === 1 ? undefined : unit, style: { fontFamily: FONT, fontSize: '10px', color: '#4b5563' } },
      labels: {
        style: { fontFamily: FONT, fontSize: '10px' },
        ...(a.angle ? { formatter() { return COMPASS[Number(this.value)] ?? String(this.value); } } : {}),
      },
      opposite: a.opposite,
      ...(a.angle ? { min: 0, max: 360, tickPositions: [0, 90, 180, 270, 360] } : {}),
    }));
    return {
      series: built,
      yAxes: axes,
      hasData: hasPoints,
      hasTotals: picked.some((s) => s.agg === 'sum'),
    };
  }, [view.overview, view.detail, groupType, stationId, measurements]);

  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    const { yAxisVisible: axesShown, showLegend: legend } = layoutRef.current;
    const lines = series.filter((x) => x.type !== 'arearange').length;
    chart.update({
      yAxis: yAxes.map((a) => ({ ...a, visible: axesShown })),
      series,
      legend: { enabled: legend && lines > 1 },
    }, true, true, false); // one-to-one: series and axes that went away are removed; no animation on updates
  }, [series, yAxes]);

  // Layout: never touches the data.
  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    chart.update({
      chart: { height: resolvedHeight },
      title: { text: title },
      legend: { enabled: showLegend && chart.series.filter((x) => x.type !== 'arearange').length > 1 },
    }, false, false, false);
    chart.yAxis.forEach((axis) => axis.update({ visible: yAxisVisible }, false));
    chart.redraw(false);
  }, [resolvedHeight, title, showLegend, yAxisVisible]);

  // The window: the shared view, or the whole picked range.
  const win: Range | null = view.viewWindow ?? view.range;
  const winRef = useRef(win);
  winRef.current = win;
  useEffect(() => {
    const axis = chartRef.current?.chart?.xAxis[0];
    // Not while this chart is being pinched: new data arriving mid-pinch would snap it back to the old window.
    // The pinch ends by setting the window, which runs this again.
    if (!axis || !win || pinchRef.current) return;
    axis.setExtremes(win.start, win.end, true, false); // no trigger: afterSetExtremes ignores it
  }, [win, series]);

  const isEmpty = !view.loading && !view.error && view.overview !== null && !hasData;

  // The resolution badge ("12-hour averages") as the chart's subtitle, so it never covers the title.
  const badge = showBadge ? resolutionBadge(view.shownBucketS, view.shownAggregated, hasTotals) : null;
  useEffect(() => {
    chartRef.current?.chart?.setSubtitle({ text: badge ?? '' });
  }, [badge]);

  // A drag that zooms ends in a click; the card around the chart (ExpandableCard) ignores clicks that moved, so it
  // doesn't open the larger view. A pinch commits the shared window once the fingers lift.
  const onTouchEnd = (e: React.TouchEvent) => {
    if (pinchRef.current && e.touches.length < 2) {
      zoomRef.current(pinchRef.current);
      pinchRef.current = null;
      // If the window didn't change (e.g. pinched out past the picked days, which stays unzoomed), nothing re-runs
      // the window effect: put this chart back on the window once React has rendered.
      requestAnimationFrame(() => {
        const w = winRef.current;
        if (w) chartRef.current?.chart?.xAxis[0]?.setExtremes(w.start, w.end, true, false);
      });
    }
  };
  return (
    <div className="relative" onTouchEnd={onTouchEnd} onTouchCancel={onTouchEnd}>
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
