// This file defines the MetricChart component: a card's one chart (the water loggers, the weather station or the
// water quality probe), holding every series its sub-filters select, drawn with Highcharts Stock. Its window and data
// come from its controller (hooks/useChartWindow, lib/chartController): the visible window is loaded at the bucket its
// width needs, down to raw 10-minute readings, from cached tiles (lib/seriesLoader), and the navigator below covers
// exactly the picked range.
//
// Drawing: one y-axis per unit, each scaled to its own data (alignTicks off); the cards hide the axes (the tooltip
// gives values, the legend units), the larger view shows them. A colour per measurement (per logger on the loggers'
// chart, temperature dashed); rain as bars of totals as wide as their bucket; wind direction as points; in the larger
// view a band from the smallest to the largest reading behind each averaged line. Averaged buckets sit at their middle
// and the tooltip names the span they cover. Points the line alone wouldn't show get a marker: filled for a reading
// between two gaps, hollow for a bucket with under half the readings its series usually has at that time of day.
// Stock's data grouping and ordinal axis are off: the server's buckets are drawn as they are, and gaps stay gaps.
//
// The navigator: an invisible series spans the picked range, so the navigator (and how far the chart can be moved)
// covers that range and not just where the data is; the navigator's own line is the range's overview, at the bucket
// the range needs. On touch screens the chart redraws when the finger lifts from the navigator, not on every move.
//
// Input (handled here, with Stock's own wheel zoom and panning off, so each gesture means one thing):
// - mouse wheel: a plain (vertical) wheel always scrolls the page, and now and then shows a hint. Ctrl/⌘ + wheel or
//   a trackpad pinch zooms around the pointer; Shift + wheel or a sideways swipe pans.
// - drag in the plot pans; Shift + drag selects a span to zoom to; the navigator and its scrollbar move and resize it.
// - touch: one finger scrolls the page (a tap shows the tooltip); two fingers pinch to zoom and move to pan.
// - keyboard, once the chart has focus: ← → pan, + − zoom, 0 resets.
// The chart redraws at a pace its own redraw cost allows, once per turn for new data and the window together. During a
// gesture the bands and the accessibility layer are off and requests wait for its end. Screen readers get the chart's
// description and, from the toolbar, the window once it settles, rather than a description of every point.

import React, { useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import Highcharts from 'highcharts';
import 'highcharts/modules/stock'; // the navigator and its scrollbar
import 'highcharts/highcharts-more'; // arearange, for the min-max bands
// Screen-reader descriptions for every chart (Highcharts warns without it)
import 'highcharts/modules/accessibility';
import HighchartsReact from 'highcharts-react-official';
import ChartToolbar, { windowLabel } from '@/components/graphs/ChartToolbar';
import { retryAllCharts, useChartWindow } from '@/hooks/useChartWindow';
import type { ChartController, ChartSnapshot, ComposedData } from '@/lib/chartController';
import { POINTS_PER_PX, POINTS_PER_PX_PHONE, RAW_S } from '@/lib/seriesTiles';
import { MIN_RANGE_MS, TIME_ZONE, bucketSpanLabel, shortBucket, valueDecimals, type PointInfo, type Range } from '@/utils/chartWindow';
import { compassLabel, seriesType, type Agg } from '@/utils/chartStyle';
import type { AxisSpec, SeriesSpec } from '@/utils/cardSeries';

export interface MetricChartProps {
  id: string; // stable for this chart: "logger", "weather", "quality"
  title: string;
  series: SeriesSpec[];
  axes: AxisSpec[];
  height?: number;
  modalOpen?: boolean;
}

const FONT = 'Poppins, Arial, sans-serif';
const ZOOM_PER_WHEEL_PX = 1.0018; // a 100 px wheel step zooms by ~20 %
const WHEEL_GESTURE_END_MS = 150; // a burst of wheel events is one gesture until it pauses this long
const HINT_EVERY_MS = 30_000; // the zoom hint shows at most this often per chart (not over every chart a page scroll passes)
const EXTENT_ID = 'picked-range'; // the invisible series that spans the picked range

// What a series is, for the tooltip and legend.
interface SeriesInfo { label: string; unit: string; agg: Agg; note?: string }

const fmt = (v: number, unit: string) => {
  const d = valueDecimals(unit);
  const rounded = Number(v.toFixed(d));
  return Highcharts.numberFormat(rounded === 0 ? 0 : rounded, d, '.', ',');
};
const muted = (text: string) => `<span style="color:#6b7280">${text}</span>`;
const isCoarse = () => typeof window !== 'undefined' && (window.matchMedia?.('(pointer: coarse)').matches ?? false);

// The shared tooltip: the span and resolution once, then a line per series: its value, the range of readings in the
// bucket (averages only), and for a partial bucket how many readings it holds.
function tooltipText(this: Highcharts.Point): string {
  const points = (this.points ?? [this]).filter((p) => (p.series.options.custom as SeriesInfo | undefined)?.label);
  const first = points[0]?.options.custom as PointInfo | undefined;
  if (!first) return '';
  const infos = points.map((p) => p.series.options.custom as SeriesInfo);
  const aggregated = first.bucketS > RAW_S;
  const kind = !aggregated ? 'reading' : infos.every((i) => i.agg === 'sum') ? 'total' : 'mean';
  const lines = points.map((p, i) => {
    const info = infos[i];
    const c = p.options.custom as PointInfo | undefined;
    if (p.y === null || p.y === undefined || !c) return '';
    const dot = `<span style="color:${p.color}">●</span>`;
    const value = info.agg === 'vector_mean' ? compassLabel(p.y) : `${fmt(p.y, info.unit)} ${info.unit}`;
    let line = `${dot} ${info.label}: <b>${value}</b>`;
    if (aggregated && info.agg === 'sum' && kind !== 'total') line += ' total';
    if (aggregated && info.agg === 'mean' && c.lo !== null && c.hi !== null && c.lo !== c.hi) {
      line += ` ${muted(`(${fmt(c.lo, info.unit)}–${fmt(c.hi, info.unit)})`)}`;
    }
    if (c.partial && c.n !== null && c.typical !== null) {
      line += ` ${muted(`· fewer readings than usual: ${c.n} (usually ${c.typical})`)}`;
    }
    // Where finer detail meets coarser data, a point can stand for another span than the header's: say which.
    if (c.start !== first.start || c.bucketS !== first.bucketS) {
      line += ` ${muted(`· ${bucketSpanLabel(c.start, c.bucketS)}, ${shortBucket(c.bucketS)}`)}`;
    }
    if (info.note) line += ` ${muted(`· ${info.note}`)}`;
    return line;
  }).filter(Boolean);
  const header = `<span style="font-size:11px">${bucketSpanLabel(first.start, first.bucketS)} · ${shortBucket(first.bucketS)} ${kind}</span>`;
  return [header, ...lines].join('<br/>');
}

/** One value of a chart's state, re-rendering only when it changes (not on every frame of a drag). */
function useChartValue<T>(controller: ChartController, pick: (s: ChartSnapshot) => T): T {
  return useSyncExternalStore(controller.subscribe, () => pick(controller.snapshot()), () => pick(controller.snapshot()));
}

// The picked range as two empty points: what the navigator and the x-axis span
const extentData = (e: Range): [number, null][] => [[e.start, null], [e.end, null]];

function buildOptions(title: string, specs: SeriesSpec[], axisSpecs: AxisSpec[], controller: ChartController, height: number, axes: boolean): Highcharts.Options {
  const coarse = isCoarse();
  const yAxis: Highcharts.YAxisOptions[] = axisSpecs.map((a, n) => {
    const own = specs.filter((s) => s.axis === n);
    const color = own.length === 1 ? own[0].color : '#4b5563';
    const style = { fontFamily: FONT, fontSize: '10px', color, whiteSpace: 'nowrap' as const };
    const axis: Highcharts.YAxisOptions = {
      visible: axes, // hidden, an axis still scales its series
      opposite: n % 2 === 1,
      title: { text: a.unit === '°' ? 'Direction' : a.unit, margin: 4, style },
      labels: { style, align: n % 2 === 1 ? 'left' : 'right', x: n % 2 === 1 ? 4 : -4 },
      gridLineWidth: n === 0 ? 1 : 0, // one set of grid lines: the axes' ticks don't line up
      gridLineColor: '#eef0f3',
      lineWidth: 1,
      showLastLabel: true,
    };
    if (own.length && own.every((s) => s.agg === 'vector_mean')) {
      Object.assign(axis, {
        min: 0, max: 360, tickPositions: [0, 90, 180, 270, 360],
        labels: { ...axis.labels, formatter(this: { value: number }) { return ['N', 'E', 'S', 'W', 'N'][this.value / 90] ?? ''; } },
      });
    }
    if (own.length && own.every((s) => s.agg === 'sum')) axis.min = 0;
    return axis;
  });
  const series: Highcharts.SeriesOptionsType[] = [];
  for (const s of specs) {
    const info: SeriesInfo = { label: s.name.replace(/ \([^)]*\)$/, ''), unit: s.unit, agg: s.agg, note: s.note };
    if (axes && s.agg === 'mean') { // bands in the larger view only: on a card with many series they hide the lines
      series.push({
        id: `${s.key}#band`, type: 'arearange', linkedTo: s.key, yAxis: s.axis, color: s.color, fillOpacity: 0.14,
        lineWidth: 0, enableMouseTracking: false, marker: { enabled: false }, data: [], zIndex: 0, visible: !s.hidden,
        accessibility: { enabled: false },
      } as Highcharts.SeriesArearangeOptions);
    }
    const type = seriesType(s.agg);
    series.push({
      id: s.key, type, name: s.name, custom: info, yAxis: s.axis, color: s.color, data: [], zIndex: 1, visible: !s.hidden,
      ...(s.dash ? { dashStyle: s.dash } : {}),
      ...(type === 'line' ? { lineWidth: 1.5 } : {}),
      ...(type === 'column' ? { pointPadding: 0, groupPadding: 0, borderWidth: 0, grouping: false, pointRange: 3600 * 1000 } : {}),
      ...(type === 'scatter' ? { marker: { enabled: true, radius: 2, symbol: 'circle' }, findNearestPointBy: 'x' } : {}),
    } as Highcharts.SeriesOptionsType);
  }
  const ext = controller.extent, w = controller.window;
  series.push({
    id: EXTENT_ID, type: 'line', data: extentData(ext), yAxis: 0, enableMouseTracking: false, showInLegend: false,
    showInNavigator: false, includeInDataExport: false, accessibility: { enabled: false }, lineWidth: 0,
  } as Highcharts.SeriesLineOptions);
  const first = specs.find((s) => !s.hidden) ?? specs[0];
  return {
    time: { timezone: TIME_ZONE },
    chart: {
      height,
      animation: false,
      alignTicks: false, // each axis fits its own data
      spacing: [6, 4, 4, 2],
      style: { fontFamily: FONT },
      zooming: { mouseWheel: { enabled: false } }, // the plain wheel scrolls the page; Ctrl + wheel zooms (below)
      panning: { enabled: false }, // drag-panning is ours (mouse only), so one finger still scrolls the page
      events: {
        render(this: Highcharts.Chart) { controller.setPlotWidth(this.plotWidth); },
      },
    },
    title: { text: undefined },
    credits: { enabled: false },
    rangeSelector: { enabled: false },
    navigator: {
      enabled: true,
      height: coarse ? 30 : 36,
      margin: 6,
      adaptToUpdatedData: false, // its extent is the picked range, not wherever data happens to be
      maskFill: 'rgba(122, 0, 60, 0.12)',
      outlineColor: '#d1d5db',
      handles: { backgroundColor: '#ffffff', borderColor: '#7a003c', height: 18, width: 9 },
      series: { type: 'line', color: first?.color ?? '#6b7280', lineWidth: 1, data: [], dataGrouping: { enabled: false } } as Highcharts.NavigatorSeriesOptions,
      xAxis: { labels: { style: { fontFamily: FONT, fontSize: '9px', color: '#6b7280' } } },
    },
    // liveRedraw (for the navigator too): on touch screens the chart redraws when the finger lifts
    scrollbar: { enabled: true, liveRedraw: !coarse, height: coarse ? 12 : 10, barBorderRadius: 5, buttonBorderRadius: 5, trackBorderRadius: 5 },
    accessibility: {
      description: `${title}. Use the buttons above the chart, or the arrow, plus and minus keys, to move and zoom.`,
      keyboardNavigation: { enabled: false }, // the chart's own keys (see above) move and zoom it
      // No hidden description per point: the chart is described as a whole, and the toolbar announces its window
      series: { pointDescriptionEnabledThreshold: 1 },
      point: { describeNull: false },
    },
    legend: {
      enabled: true,
      margin: 2, padding: 2, itemDistance: 12,
      itemStyle: { fontFamily: FONT, fontSize: '11px', fontWeight: 'normal' },
      labelFormatter(this: Highcharts.Series | Highcharts.Point) {
        const info = (this as Highcharts.Series).options?.custom as SeriesInfo | undefined;
        const name = (this as Highcharts.Series).name;
        return info?.note ? `${name} <span style="color:#9a3412">· ${info.note}</span>` : name;
      },
    },
    tooltip: { shared: true, split: false, formatter: tooltipText, style: { fontFamily: FONT, fontSize: '12px' }, outside: true },
    plotOptions: {
      series: {
        animation: false,
        connectNulls: false,
        turboThreshold: 0, // points are objects (they carry their bucket for the tooltip)
        dataGrouping: { enabled: false }, // the server's buckets, as they are
        showInNavigator: false,
        states: { inactive: { opacity: 1 } },
        marker: { enabled: false, radius: 2.5, symbol: 'circle' },
      },
    },
    xAxis: {
      type: 'datetime',
      ordinal: false, // time is time: a gap in the data is a gap on the axis
      min: w.start,
      max: w.end,
      minRange: MIN_RANGE_MS,
      crosshair: { width: 1, color: '#9ca3af' },
      title: { text: null },
      labels: { style: { fontFamily: FONT, fontSize: '10px' } },
      events: {
        // The navigator, its scrollbar and the plot move the axis themselves: tell the controller, which loads that
        // window (programmatic changes, which carry no trigger, come from the controller and are ignored)
        afterSetExtremes(e) {
          if (!e.trigger || e.min === undefined || e.max === undefined) return;
          controller.setWindow({ start: e.min, end: e.max }, e.trigger === 'navigator' || e.trigger === 'scrollbar' ? 'slider' : 'drag');
        },
      },
    } as Highcharts.XAxisOptions,
    yAxis,
    series,
  };
}

const MetricChart: React.FC<MetricChartProps> = (props) => {
  const { id, title, series: specs, axes, height = 320, modalOpen = false } = props;
  const structure = JSON.stringify({ specs, axes });
  const keys = useMemo(() => (JSON.parse(structure).specs as SeriesSpec[]).map((s) => s.key), [structure]);
  const controller = useChartWindow(modalOpen ? `${id}:modal` : id, keys);
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLDivElement>(null);
  const selectRef = useRef<HTMLDivElement>(null);

  const chartHeight = modalOpen ? Math.round(height * 1.5) : height;
  // Rebuilt (a new chart) only when what is drawn changes: other series, height or the larger view
  const options = useMemo(() => {
    const s = JSON.parse(structure) as { specs: SeriesSpec[]; axes: AxisSpec[] };
    return buildOptions(title, s.specs, s.axes, controller, chartHeight, modalOpen);
  }, [title, structure, controller, chartHeight, modalOpen]);

  const error = useChartValue(controller, (s) => s.error);
  const firstLoad = useChartValue(controller, (s) => s.shownBucket === null && !s.error);
  const windowEmpty = useChartValue(controller, (s) => s.windowEmpty && s.shownBucket !== null && !s.loading);
  const noData = useChartValue(controller, (s) => s.hasData === false);
  const extentStart = useChartValue(controller, (s) => s.extent.start);
  const extentEnd = useChartValue(controller, (s) => s.extent.end);

  // Data and window into the chart: data is set without drawing, and the paced redraw (onRedraw, right after) draws
  // it and the window in one go.
  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    let pointRange = 0;
    let dirty = false;
    const apply = (d: ComposedData) => {
      dirty = true;
      chart.tooltip?.hide(0); // it would describe points that are no longer there
      for (const key of keys) {
        const s = chart.get(key) as Highcharts.Series | undefined;
        if (!s) continue;
        // Only the picked range: tiles reach past its ends, and points there would stretch the axis and navigator
        const e = controller.extent;
        const pts = (d.series.get(key) ?? []).filter((p) => p.x >= e.start && p.x <= e.end);
        const info = s.options.custom as SeriesInfo;
        const unit = controller.meta(key)?.unit;
        if (unit && unit !== info.unit) {
          info.unit = unit;
          s.update({ name: unit === '°' ? info.label : `${info.label} (${unit})` } as Highcharts.SeriesOptionsType, false);
        }
        const color = s.color as string;
        s.setData(pts.map((p) => {
          const c = p.custom;
          if (!c || p.y === null || !(c.partial || c.isolated)) return p;
          return { ...p, marker: c.partial ? { enabled: true, fillColor: '#ffffff', lineColor: color, lineWidth: 1.5 } : { enabled: true } };
        }) as Highcharts.PointOptionsType[], false, false, false);
        const band = chart.get(`${key}#band`) as Highcharts.Series | undefined;
        band?.setData(pts.map((p) => {
          const c = p.custom;
          return c && p.y !== null && c.bucketS > RAW_S && c.lo !== null && c.hi !== null ? [p.x, c.lo, c.hi] : [p.x, null, null];
        }), false, false, false);
        if (info.agg === 'sum') { // bars as wide as their bucket
          const range = (d.shownBucket ?? RAW_S) * 1000;
          if (range !== pointRange) s.update({ pointRange: range } as Highcharts.SeriesColumnOptions, false);
        }
      }
      pointRange = (d.shownBucket ?? RAW_S) * 1000;
      navigator();
    };
    // The navigator's line: the first shown series over the picked range, at the overview's bucket, with the range's
    // two ends so it spans all of it
    let navShown = '';
    const navigator = () => {
      const nav = (chart as Highcharts.Chart & { navigator?: { series?: Highcharts.Series[] } }).navigator?.series?.[0];
      const key = keys.find((k) => (chart.get(k) as Highcharts.Series | undefined)?.visible) ?? keys[0];
      if (!nav || !key) return;
      const pts = controller.overview(key);
      const e = controller.extent;
      const sig = `${key}|${pts.length}|${e.start}|${e.end}|${pts.at(-1)?.y ?? ''}`;
      if (sig === navShown) return;
      navShown = sig;
      nav.setData([[e.start, null], ...pts.map((p) => [p.x, p.y] as [number, number | null]), [e.end, null]], false, false, false);
      (chart.get(EXTENT_ID) as Highcharts.Series | undefined)?.setData(extentData(e), false, false, false);
      dirty = true;
    };
    const place = (w: { start: number; end: number }) => {
      const axis = chart.xAxis[0];
      if (Math.abs((axis.min ?? 0) - w.start) > 1 || Math.abs((axis.max ?? 0) - w.end) > 1) {
        chart.tooltip?.hide(0);
        axis.setExtremes(w.start, w.end, false, false);
        dirty = true;
      }
      if (dirty) {
        dirty = false;
        chart.redraw(false);
      }
    };
    // The bands go during a gesture and come back, in one redraw, when it ends (hidden-by-default series stay hidden)
    const bands = (show: boolean) => {
      for (const s of chart.series) {
        if (s.type !== 'arearange') continue;
        const line = chart.get(String(s.options.id).replace(/#band$/, '')) as Highcharts.Series | undefined;
        const want = show && (line?.visible ?? true);
        if (s.visible !== want) {
          s.setVisible(want, false);
          dirty = true;
        }
      }
    };
    apply(controller.lastData);
    place(controller.window);
    // A series shown or hidden in the legend: the navigator follows the first one shown
    const offLegend = Highcharts.addEvent(chart, 'redraw', () => {
      const before = navShown;
      navigator();
      if (navShown !== before) chart.redraw(false);
    });
    const offData = controller.onData(apply);
    const offRedraw = controller.onRedraw(place);
    // Accessibility repositions its hidden buttons (forcing a page layout) on every redraw: off while the window
    // moves, back 300 ms after (the toolbar's live region still announces where the gesture ended)
    let a11yTimer = 0;
    const a11y = (on: boolean) => chart.update({ accessibility: { enabled: on } }, false);
    const offGesture = controller.onGesture((active) => {
      bands(!active);
      window.clearTimeout(a11yTimer);
      if (active) a11y(false);
      else a11yTimer = window.setTimeout(() => { a11y(true); chart.redraw(false); }, 300);
    });
    return () => { offData(); offRedraw(); offGesture(); offLegend(); window.clearTimeout(a11yTimer); };
  }, [controller, keys, options]);

  // A new picked range (or the hour moving on): the navigator and the x-axis span it
  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    (chart.get(EXTENT_ID) as Highcharts.Series | undefined)?.setData(extentData({ start: extentStart, end: extentEnd }), true, false, false);
  }, [extentStart, extentEnd, options]);

  // About one point per pixel on phones (each costs more to draw there), 1.5 elsewhere
  useEffect(() => {
    const coarse = window.matchMedia?.('(pointer: coarse)');
    const set = () => controller.setDensity(coarse?.matches || window.innerWidth < 640 ? POINTS_PER_PX_PHONE : POINTS_PER_PX);
    set();
    window.addEventListener('resize', set);
    return () => window.removeEventListener('resize', set);
  }, [controller]);

  // Charts off screen load after the ones on screen
  useEffect(() => {
    const el = plotRef.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([entry]) => controller.setVisible(entry.isIntersecting), { rootMargin: '200px' });
    io.observe(el);
    return () => io.disconnect();
  }, [controller]);

  // Wheel, drag, touch and keys
  useEffect(() => {
    const el = plotRef.current;
    if (!el) return;
    const chart = () => chartRef.current?.chart;
    let hintTimer = 0;
    let hintShown = -Infinity;
    let wheelEnd = 0;
    const wheelGesture = () => { // a burst of wheel events is one gesture: it ends when they pause
      controller.beginGesture();
      window.clearTimeout(wheelEnd);
      wheelEnd = window.setTimeout(() => controller.endGesture(), WHEEL_GESTURE_END_MS);
    };
    const showHint = () => {
      if (performance.now() - hintShown < HINT_EVERY_MS) return;
      hintShown = performance.now();
      hintRef.current?.classList.add('opacity-100');
      window.clearTimeout(hintTimer);
      hintTimer = window.setTimeout(() => hintRef.current?.classList.remove('opacity-100'), 1200);
    };
    const timeAt = (clientX: number) => {
      const c = chart();
      if (!c) return (controller.window.start + controller.window.end) / 2;
      return c.xAxis[0].toValue(clientX - c.container.getBoundingClientRect().left);
    };
    const inPlot = (clientX: number, clientY: number) => {
      const c = chart();
      if (!c) return false;
      const box = c.container.getBoundingClientRect();
      const x = clientX - box.left, y = clientY - box.top;
      return x >= c.plotLeft && x <= c.plotLeft + c.plotWidth && y >= c.plotTop && y <= c.plotTop + c.plotHeight;
    };

    const onWheel = (e: WheelEvent) => {
      const c = chart();
      if (!c) return;
      const sideways = Math.abs(e.deltaX) > Math.abs(e.deltaY) || e.shiftKey;
      const ctrl = e.ctrlKey || e.metaKey;
      const unit = e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? 800 : 1;
      const w = controller.window;
      if (sideways && !ctrl) {
        e.preventDefault();
        wheelGesture();
        const delta = (Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY) * unit;
        controller.pan(delta / Math.max(c.plotWidth, 1), 'wheel');
        return;
      }
      if (!ctrl) {
        showHint(); // and let the page scroll
        return;
      }
      e.preventDefault();
      wheelGesture();
      const factor = Math.min(2, Math.max(0.5, Math.pow(ZOOM_PER_WHEEL_PX, e.deltaY * unit)));
      const at = Math.min(Math.max(timeAt(e.clientX), w.start), w.end);
      controller.zoom(factor, at, 'wheel');
    };

    let drag: { x0: number; w0: { start: number; end: number }; mode: 'pan' | 'select'; moved: boolean; id: number } | null = null;
    // A press below the plot (the navigator, its scrollbar) starts a gesture that ends when the pointer lifts anywhere
    let below = false;
    const belowPlot = (clientY: number) => {
      const c = chart();
      return !!c && clientY - c.container.getBoundingClientRect().top > c.plotTop + c.plotHeight + 8;
    };
    const liftBelow = () => {
      if (!below) return;
      below = false;
      controller.endGesture();
    };
    const onDown = (e: PointerEvent) => {
      if (belowPlot(e.clientY)) {
        below = true;
        controller.beginGesture();
        return;
      }
      if (e.pointerType !== 'mouse' || e.button !== 0 || !inPlot(e.clientX, e.clientY)) return;
      el.focus({ preventScroll: true }); // for the keys
      drag = { x0: e.clientX, w0: { ...controller.window }, mode: e.shiftKey ? 'select' : 'pan', moved: false, id: e.pointerId };
    };
    const onMove = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      if (e.buttons === 0) { // the button was released where we didn't hear it (outside the window, say)
        onUp(e);
        return;
      }
      const c = chart();
      if (!c) return;
      const dx = e.clientX - drag.x0;
      if (!drag.moved) {
        if (Math.abs(dx) < 4) return;
        drag.moved = true;
        el.setPointerCapture(e.pointerId);
        c.tooltip?.hide(0);
        if (drag.mode === 'pan') controller.beginGesture();
      }
      if (drag.mode === 'pan') {
        const dt = (-dx / Math.max(c.plotWidth, 1)) * (drag.w0.end - drag.w0.start);
        controller.setWindow({ start: drag.w0.start + dt, end: drag.w0.end + dt }, 'drag');
      } else if (selectRef.current) {
        const box = c.container.getBoundingClientRect();
        const lo = Math.max(Math.min(drag.x0, e.clientX) - box.left, c.plotLeft);
        const hi = Math.min(Math.max(drag.x0, e.clientX) - box.left, c.plotLeft + c.plotWidth);
        Object.assign(selectRef.current.style, {
          display: 'block', left: `${lo}px`, width: `${Math.max(hi - lo, 0)}px`, top: `${c.plotTop}px`, height: `${c.plotHeight}px`,
        });
      }
    };
    const onUp = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      if (drag.mode === 'select' && drag.moved) {
        const a = timeAt(drag.x0), b = timeAt(e.clientX);
        if (b !== a) controller.setWindow({ start: Math.min(a, b), end: Math.max(a, b) }, 'select');
      }
      if (selectRef.current) selectRef.current.style.display = 'none';
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      drag = null;
      controller.endGesture();
    };
    // Capture lost (e.g. the window lost focus mid-drag): end the drag where it is; a selection is dropped
    const onLost = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      if (selectRef.current) selectRef.current.style.display = 'none';
      drag = null;
      controller.endGesture();
    };

    // The plot's left edge and width are measured once per pinch: reading them on every move forced a layout of the
    // whole page each time (the page doesn't scroll during a pinch). Two-finger events stop here, before Highcharts'
    // own touch handling (which measured the page again for its tooltip), since they are this chart's pinch.
    let pinch: { d0: number; t0: number; span0: number; left: number; width: number } | null = null;
    const touchState = (e: TouchEvent) => {
      const [a, b] = [e.touches[0], e.touches[1]];
      return { d: Math.max(20, Math.abs(a.clientX - b.clientX)), cx: (a.clientX + b.clientX) / 2 };
    };
    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length !== 2) return;
      e.preventDefault();
      e.stopPropagation();
      const c = chart();
      if (!c) return;
      const { d, cx } = touchState(e);
      const w = controller.window;
      const left = c.container.getBoundingClientRect().left + c.plotLeft;
      pinch = { d0: d, t0: timeAt(cx), span0: w.end - w.start, left, width: Math.max(c.plotWidth, 1) };
      chart()?.tooltip?.hide(0);
      controller.beginGesture();
    };
    const onTouchMove = (e: TouchEvent) => {
      if (!pinch || e.touches.length !== 2) return;
      e.preventDefault();
      e.stopPropagation();
      const { d, cx } = touchState(e);
      const span = Math.max(pinch.span0 * (pinch.d0 / d), MIN_RANGE_MS);
      const share = (cx - pinch.left) / pinch.width;
      const start = pinch.t0 - share * span;
      controller.setWindow({ start, end: start + span }, 'pinch');
    };
    const onTouchEnd = (e: TouchEvent) => {
      if (e.touches.length < 2 && pinch) {
        pinch = null;
        controller.endGesture();
      }
    };

    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const acts: Record<string, () => void> = {
        ArrowLeft: () => controller.pan(-0.1, 'key'),
        ArrowRight: () => controller.pan(0.1, 'key'),
        '+': () => controller.zoom(2 / 3, undefined, 'key'),
        '=': () => controller.zoom(2 / 3, undefined, 'key'),
        '-': () => controller.zoom(1.5, undefined, 'key'),
        '_': () => controller.zoom(1.5, undefined, 'key'),
        '0': () => controller.reset(),
        Home: () => controller.reset(),
      };
      const act = acts[e.key];
      if (act) {
        e.preventDefault();
        act();
      }
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    el.addEventListener('pointerdown', onDown);
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerup', onUp);
    el.addEventListener('pointercancel', onUp);
    el.addEventListener('lostpointercapture', onLost);
    el.addEventListener('touchstart', onTouchStart, { passive: false, capture: true });
    el.addEventListener('touchmove', onTouchMove, { passive: false, capture: true });
    el.addEventListener('touchend', onTouchEnd);
    el.addEventListener('touchcancel', onTouchEnd);
    el.addEventListener('keydown', onKey);
    window.addEventListener('pointerup', liftBelow);
    window.addEventListener('pointercancel', liftBelow);
    return () => {
      window.removeEventListener('pointerup', liftBelow);
      window.removeEventListener('pointercancel', liftBelow);
      window.clearTimeout(hintTimer);
      window.clearTimeout(wheelEnd);
      controller.endGesture();
      el.removeEventListener('wheel', onWheel);
      el.removeEventListener('pointerdown', onDown);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerup', onUp);
      el.removeEventListener('pointercancel', onUp);
      el.removeEventListener('lostpointercapture', onLost);
      el.removeEventListener('touchstart', onTouchStart, { capture: true });
      el.removeEventListener('touchmove', onTouchMove, { capture: true });
      el.removeEventListener('touchend', onTouchEnd);
      el.removeEventListener('touchcancel', onTouchEnd);
      el.removeEventListener('keydown', onKey);
    };
  }, [controller]);

  const kind = specs.length > 0 && specs.every((s) => s.agg === 'sum') ? 'totals' : 'means';
  const plotId = `plot-${id}${modalOpen ? '-modal' : ''}`;
  return (
    <div className="min-w-0" data-testid={`chart-${id}`}>
      <ChartToolbar controller={controller} title={title} kind={kind} headingLevel="h3" />
      <div
        ref={plotRef}
        id={plotId}
        tabIndex={0}
        role="group"
        aria-label={`${title} chart. Arrow keys move it, plus and minus zoom, 0 resets.`}
        className="well-chart relative cursor-grab touch-pan-y rounded-md outline-none focus-visible:ring-2 focus-visible:ring-primary active:cursor-grabbing"
        style={{ height: chartHeight }}
      >
        <HighchartsReact
          key={structure}
          highcharts={Highcharts}
          options={options}
          allowChartUpdate={false}
          ref={chartRef}
          containerProps={{ style: { height: `${chartHeight}px` } }}
        />
        <div ref={selectRef} className="pointer-events-none absolute hidden bg-primary/10 outline outline-1 outline-primary/50" />
        <div ref={hintRef} aria-hidden="true" data-testid="chart-wheel-hint"
          className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-md bg-gray-900/55 px-4 text-center text-sm text-white opacity-0 transition-opacity duration-200">
          Hold Ctrl (⌘ on a Mac) and scroll to zoom
        </div>
        {firstLoad && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded bg-white/70" aria-hidden="true">
            <span className="flex items-center gap-2 text-sm text-gray-700">
              <span className="h-4 w-4 motion-safe:animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" />
              Loading data…
            </span>
          </div>
        )}
        {!firstLoad && !error && (noData || windowEmpty) && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <p className="rounded-md bg-white/90 px-3 py-1.5 text-sm text-muted">
              {noData ? `No readings between ${windowLabel({ start: extentStart, end: extentEnd }, extentEnd)}` : 'No readings in this part of the range'}
            </p>
          </div>
        )}
        {error && (
          <div role="alert" className="absolute inset-x-4 top-6 z-10 mx-auto max-w-md rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700 shadow-sm">
            {error.message}{' '}
            {/* One click retries every chart that failed (a server error usually hits them all at once) */}
            <button type="button" onClick={() => { controller.retry(); retryAllCharts(); }}
              className="font-medium underline underline-offset-2 hover:text-red-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricChart;
