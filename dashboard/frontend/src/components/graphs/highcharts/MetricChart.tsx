// This file defines the MetricChart component: one West Campus sensor chart (a group, or one water logger),
// drawn with Highcharts from the series /api/series returns (see hooks/useChartSeries). It has one Y-axis per unit,
// shown in the cards too (small labels there), and each axis scales on its own (alignTicks off), so one unit's
// outlier doesn't squash the others. Each measurement keeps its own colour wherever it appears.
//
// Averaged buckets are drawn at their middle; the tooltip names the span they cover and the resolution
// ("Oct 1, 2026 18:00–24:00 · 6-h mean"), with the smallest and largest reading in it. Points the line alone
// wouldn't show get a marker: a filled dot for a reading with no neighbour on either side (between two gaps), a
// hollow one for a bucket holding under half its usual readings (an outage starts or ends in it), whose average
// is less reliable.
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
import {
  MIN_RANGE_MS, TIME_ZONE, bucketSpanLabel, composePoints, resolutionBadge, shortBucket, valueDecimals,
  type PointInfo, type Range,
} from '@/utils/chartWindow';

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

// One colour per measurement, the same in every chart, so air temperature, dew point and soil temperature (all °C,
// on one axis) can be told apart. A measurement not listed gets one from the fallback palette, by its name.
const MEASUREMENT_COLORS: Record<string, string> = {
  'Air Temperature': '#D62728', 'Dew Point': '#0866AB', 'Soil Temperature': '#8C564B',
  'Relative Humidity': '#50B748', 'Pressure': '#7F488D', 'Rain': '#17BECF', 'Solar Radiation': '#E0A800',
  'Water Content': '#6B8E23', 'Wind Speed': '#4B5563', 'Gust Speed': '#E90D8B', 'Wind Direction': '#F79425',
  'Water Temperature': '#D62728', 'Water Surface Elevation': '#0866AB',
  'Conductivity': '#0866AB', 'Salinity': '#17BECF', 'TDS': '#7F488D', 'ODO': '#50B748', 'ODOSat': '#2E7D32',
  'Turbidity': '#8C564B', 'TSS': '#F79425',
};
const FALLBACK_COLORS = ['#0866AB', '#50B748', '#F79425', '#E90D8B', '#7F488D', '#CB2027', '#17BECF', '#8C564B'];
function measurementColor(name: string): string {
  if (MEASUREMENT_COLORS[name]) return MEASUREMENT_COLORS[name];
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return FALLBACK_COLORS[h % FALLBACK_COLORS.length];
}
const FONT = 'Poppins, Arial, sans-serif';

// What a series is, for the tooltip.
interface SeriesInfo { measurement: string; unit: string; agg: 'mean' | 'sum' | 'vector_mean' }

// A value at its unit's decimals; one that rounds to zero is shown as 0, not -0.00.
const fmt = (v: number, unit: string) => {
  const d = valueDecimals(unit);
  const rounded = Number(v.toFixed(d));
  return Highcharts.numberFormat(rounded === 0 ? 0 : rounded, d, '.', ',');
};
const muted = (text: string) => `<span style="color:#6b7280">${text}</span>`;

// The shared tooltip: the span and resolution once, then a line per series with its value, the range of readings in
// the bucket (averages only: rain's min/max are single readings, not totals, and wind direction has none) and, for a
// partial bucket, how many readings it holds.
function tooltipText(this: Highcharts.Point): string {
  const points = this.points ?? [this];
  const first = points[0]?.options.custom as PointInfo | undefined;
  if (!first) return '';
  const infos = points.map((p) => p.series.options.custom as SeriesInfo);
  const aggregated = first.bucketS > 600;
  const kind = !aggregated ? 'reading' : infos.every((i) => i.agg === 'sum') ? 'total' : 'mean';
  const lines = points.map((p, i) => {
    const info = infos[i];
    const c = p.options.custom as PointInfo | undefined;
    if (p.y === null || p.y === undefined || !c) return '';
    const dot = `<span style="color:${p.color}">●</span>`;
    let line = `${dot} ${info.measurement}: <b>${fmt(p.y, info.unit)} ${info.unit}</b>`;
    if (aggregated && info.agg === 'sum' && kind !== 'total') line += ' total';
    if (aggregated && info.agg === 'mean' && c.lo !== null && c.hi !== null && c.lo !== c.hi) {
      line += ` ${muted(`(${fmt(c.lo, info.unit)}–${fmt(c.hi, info.unit)})`)}`;
    }
    if (c.partial && c.n !== null) line += ` ${muted(`· only ${c.n} of ${c.bucketS / 600} readings`)}`;
    return line;
  }).filter(Boolean);
  const span = `${bucketSpanLabel(first.start, first.bucketS)} · ${shortBucket(first.bucketS)} ${kind}`;
  const header = `<span style="font-size:11px">${span}</span>`;
  return [header, ...lines].join('<br/>');
}

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
  const layoutRef = useRef({ showLegend });
  layoutRef.current = { showLegend };

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
        alignTicks: false, // each axis fits its own data, rather than all lining up their ticks with the widest one
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
      tooltip: { shared: true, followPointer: true, formatter: tooltipText, style: { fontFamily: FONT } },
      plotOptions: {
        series: {
          animation: !reducedMotion,
          connectNulls: false,
          turboThreshold: 0, // points are objects (they carry their bucket for the tooltip), so allow any number
          marker: { enabled: false, radius: 2.5, symbol: 'circle' }, // enabled per point where needed (see above)
        },
      },
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
    const unitColors = new Map<string, string[]>();
    const built = picked.map((s) => {
      if (!unitIndex.has(s.unit)) unitIndex.set(s.unit, unitIndex.size);
      const key = seriesKey(s);
      const color = measurementColor(s.measurement_type);
      unitColors.set(s.unit, [...(unitColors.get(s.unit) ?? []), color]);
      const points = composePoints(s, ov.bucketS, detail
        ? { values: detail.byKey.get(key), bucketS: detail.bucketS, range: detail.range }
        : undefined);
      const info: SeriesInfo = { measurement: s.measurement_type, unit: s.unit, agg: s.agg };
      return {
        id: key,
        type: 'line' as const,
        name: `${s.measurement_type} (${s.unit})`,
        custom: info,
        data: points.map((p) => {
          const c = p.custom;
          if (!c || p.y === null || !(c.partial || c.isolated)) return p;
          // hollow: a partial bucket; filled: a lone reading
          const marker = c.partial
            ? { enabled: true, fillColor: '#ffffff', lineColor: color, lineWidth: 1.5 }
            : { enabled: true };
          return { ...p, marker };
        }),
        color,
        yAxis: unitIndex.get(s.unit)!,
      };
    });
    // Each axis names its unit once, in a title along it, so the labels stay narrow; both are in the colour of the axis' only
    // series (grey when it has several) and small in the cards. Only the first axis draws grid lines: with ticks no
    // longer aligned, more would criss-cross.
    const axes = Array.from(unitIndex.keys()).map((unit, index) => {
      const colors = unitColors.get(unit) ?? [];
      const color = colors.length === 1 ? colors[0] : '#4b5563';
      const style = { fontFamily: FONT, fontSize: modalOpen ? '11px' : '9px', color, whiteSpace: 'nowrap' };
      return {
        title: { text: unit, margin: 4, style },
        labels: { style },
        gridLineWidth: index === 0 ? 1 : 0,
        opposite: index % 2 === 1,
      };
    });
    return {
      series: built,
      yAxes: axes,
      hasData: built.some((s) => s.data.length > 0),
      hasTotals: picked.some((s) => s.agg === 'sum'),
    };
  }, [view.overview, view.detail, groupType, stationId, measurements, modalOpen]);

  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    const { showLegend: legend } = layoutRef.current;
    // A tooltip left open would describe points that are no longer there.
    chart.tooltip?.hide(0);
    chart.pointer?.reset(false, 0);
    chart.update({
      yAxis: yAxes,
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
    chart.redraw(false);
  }, [resolvedHeight, title, showLegend]);

  // The window: the shared view, or the whole picked range.
  const win: Range | null = view.viewWindow ?? view.range;
  const winRef = useRef(win);
  winRef.current = win;
  useEffect(() => {
    const axis = chartRef.current?.chart?.xAxis[0];
    // Not while this chart is being pinched: new data arriving mid-pinch would snap it back to the old window.
    // The pinch ends by setting the window, which runs this again.
    if (!axis || !win || pinchRef.current) return;
    axis.chart.tooltip?.hide(0); // it would point at where the data was before the window moved
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
