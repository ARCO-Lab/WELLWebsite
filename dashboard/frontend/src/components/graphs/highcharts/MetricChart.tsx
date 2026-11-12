// This file defines the MetricChart component: one sensor chart (e.g. Logger 1, or the weather station's
// temperatures), drawn with Highcharts Core, that zooms and pans by itself. Its window and data come from its own
// controller (hooks/useChartWindow), so zooming Logger 1 leaves Logger 4 where it is.
//
// Drawing: one or more panes stacked on one time axis (a logger: water level on top, temperature below), each scaled
// to its own data (alignTicks off). The small charts in the cards show no y-axes (the tooltip gives values and the
// legend units); the larger view shows them; a colour per measurement; averaged lines over a band
// from the smallest to the largest reading in each bucket; rain as bars of totals as wide as their bucket; wind
// direction as points on an N/E/S/W axis. Averaged buckets sit at their middle; the tooltip names the span they
// cover. Points the line alone wouldn't show get a marker: filled for a reading between two gaps, hollow for a bucket
// with under half the readings its series usually has at that time of day (typicalCounts in utils/chartWindow).
//
// Input (handled here, not by Highcharts' zooming, so each gesture means one thing):
// - mouse wheel: a plain (vertical) wheel always scrolls the page, and now and then shows a hint. Ctrl/⌘ + wheel or
//   a trackpad pinch zooms around the pointer; Shift + wheel or a sideways swipe pans.
// - drag pans; Shift + drag selects a span to zoom to.
// - touch: one finger scrolls the page (a tap shows the tooltip); two fingers pinch to zoom and move to pan.
// - keyboard, once the chart has focus: ← → pan, + − zoom, 0 resets.
// The chart redraws at a pace its own redraw cost allows (lib/chartController), once per turn for new data and the
// window together. During a gesture the min-max bands are hidden (they double the cost of a redraw) and requests
// wait for its end. Screen readers get the chart's description and, from the toolbar, the window once it settles,
// rather than a description of every point (pointDescriptionEnabledThreshold), which made each redraw twice as slow.

import React, { useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import Highcharts from 'highcharts';
import 'highcharts/highcharts-more'; // arearange, for the min-max bands
// Screen-reader descriptions for every chart (Highcharts warns without it)
import 'highcharts/modules/accessibility';
import HighchartsReact from 'highcharts-react-official';
import ChartToolbar from '@/components/graphs/ChartToolbar';
import ChartSlider from '@/components/graphs/ChartSlider';
import { useChartWindow } from '@/hooks/useChartWindow';
import type { ChartController, ChartSnapshot, ComposedData } from '@/lib/chartController';
import { POINTS_PER_PX, POINTS_PER_PX_PHONE, RAW_S } from '@/lib/seriesTiles';
import { MIN_RANGE_MS, TIME_ZONE, bucketSpanLabel, shortBucket, valueDecimals, type PointInfo } from '@/utils/chartWindow';
import { UNITS, aggOf, compassLabel, measurementColor, seriesNote, seriesType, type Agg } from '@/utils/chartStyle';

export interface MetricChartProps {
  id: string; // stable for this chart, e.g. "logger-2577531"
  title: string;
  groupType: 'Weather' | 'Quality' | 'Logger';
  stationId: string;
  panes: string[][]; // measurement_type values per pane, top to bottom
  height?: number;
  modalOpen?: boolean;
}

const FONT = 'Poppins, Arial, sans-serif';
const ZOOM_PER_WHEEL_PX = 1.0018; // a 100 px wheel step zooms by ~20 %
const WHEEL_GESTURE_END_MS = 150; // a burst of wheel events is one gesture until it pauses this long
const HINT_EVERY_MS = 30_000; // the zoom hint shows at most this often per chart (not over every chart a page scroll passes)

// What a series is, for the tooltip and legend.
interface SeriesInfo { measurement: string; unit: string; agg: Agg; note?: string }

const fmt = (v: number, unit: string) => {
  const d = valueDecimals(unit);
  const rounded = Number(v.toFixed(d));
  return Highcharts.numberFormat(rounded === 0 ? 0 : rounded, d, '.', ',');
};
const muted = (text: string) => `<span style="color:#6b7280">${text}</span>`;
const seriesName = (m: string, unit: string) => (unit && unit !== '°' ? `${m} (${unit})` : m);

// The shared tooltip: the span and resolution once, then a line per series: its value, the range of readings in the
// bucket (averages only), and for a partial bucket how many readings it holds.
function tooltipText(this: Highcharts.Point): string {
  const points = (this.points ?? [this]).filter((p) => (p.series.options.custom as SeriesInfo | undefined)?.measurement);
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
    let line = `${dot} ${info.measurement}: <b>${value}</b>`;
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

function buildOptions(props: MetricChartProps, keys: string[], controller: ChartController, height: number, axes: boolean): Highcharts.Options {
  const { panes, groupType, title } = props;
  const two = panes.length > 1;
  const yAxis: Highcharts.YAxisOptions[] = panes.map((ms, n) => {
    const unit = UNITS[ms[0]] ?? '';
    const color = ms.length === 1 ? measurementColor(ms[0]) : '#4b5563';
    const style = { fontFamily: FONT, fontSize: '10px', color, whiteSpace: 'nowrap' as const };
    const axis: Highcharts.YAxisOptions = {
      visible: axes, // hidden, an axis still scales its pane
      title: { text: unit === '°' ? 'Direction' : unit, margin: 4, style },
      labels: { style },
      gridLineWidth: 1,
      gridLineColor: '#eef0f3',
      lineWidth: 1,
      offset: 0,
      top: two ? (n === 0 ? '0%' : '60%') : undefined,
      height: two ? (n === 0 ? '52%' : '40%') : undefined,
    };
    if (ms.every((m) => aggOf(m) === 'vector_mean')) {
      Object.assign(axis, {
        min: 0, max: 360, tickPositions: [0, 90, 180, 270, 360],
        labels: { style, formatter(this: { value: number }) { return ['N', 'E', 'S', 'W', 'N'][this.value / 90] ?? ''; } },
      });
    }
    if (ms.every((m) => aggOf(m) === 'sum')) axis.min = 0;
    return axis;
  });
  const series: Highcharts.SeriesOptionsType[] = [];
  panes.forEach((ms, n) => ms.forEach((m) => {
    const key = `${groupType}|${props.stationId}|${m}`;
    const agg = aggOf(m);
    const unit = UNITS[m] ?? '';
    const color = measurementColor(m);
    const note = seriesNote(groupType, m);
    const info: SeriesInfo = { measurement: m, unit, agg, note: note?.note };
    if (agg === 'mean') {
      series.push({
        id: `${key}#band`, type: 'arearange', linkedTo: key, yAxis: n, color, fillOpacity: 0.16, lineWidth: 0,
        enableMouseTracking: false, marker: { enabled: false }, data: [], zIndex: 0, visible: !note?.hidden,
        accessibility: { enabled: false },
      } as Highcharts.SeriesArearangeOptions);
    }
    const type = seriesType(agg);
    series.push({
      id: key, type, name: seriesName(m, unit), custom: info, yAxis: n, color, data: [], zIndex: 1, visible: !note?.hidden,
      ...(type === 'line' ? { lineWidth: 1.5 } : {}),
      ...(type === 'column' ? { pointPadding: 0, groupPadding: 0, borderWidth: 0, grouping: false, pointRange: 3600 * 1000 } : {}),
      ...(type === 'scatter' ? { marker: { enabled: true, radius: 2, symbol: 'circle' }, findNearestPointBy: 'x' } : {}),
    } as Highcharts.SeriesOptionsType);
  }));
  const shown = series.filter((s) => s.type !== 'arearange');
  const w = controller.window;
  return {
    time: { timezone: TIME_ZONE },
    chart: {
      height,
      animation: false,
      alignTicks: false, // each axis fits its own data
      spacing: [6, 4, 4, 2],
      style: { fontFamily: FONT },
      events: {
        render(this: Highcharts.Chart) { controller.setPlotWidth(this.plotWidth); },
      },
    },
    title: { text: undefined },
    credits: { enabled: false },
    accessibility: {
      description: `${title}. Use the buttons above the chart, or the arrow, plus and minus keys, to move and zoom.`,
      keyboardNavigation: { enabled: false }, // the chart's own keys (see above) move and zoom it
      // No hidden description per point: the chart is described as a whole, and the toolbar announces its window
      series: { pointDescriptionEnabledThreshold: 1 },
      point: { describeNull: false },
    },
    legend: {
      enabled: shown.length > 1 || shown.some((s) => (s.custom as SeriesInfo).note),
      margin: 2, padding: 2, itemDistance: 12,
      itemStyle: { fontFamily: FONT, fontSize: '11px', fontWeight: 'normal' },
      labelFormatter(this: Highcharts.Series | Highcharts.Point) {
        const info = (this as Highcharts.Series).options?.custom as SeriesInfo | undefined;
        const name = (this as Highcharts.Series).name;
        return info?.note ? `${name} <span style="color:#9a3412">· ${info.note}</span>` : name;
      },
    },
    tooltip: { shared: true, formatter: tooltipText, style: { fontFamily: FONT, fontSize: '12px' }, outside: true },
    plotOptions: {
      series: {
        animation: false,
        connectNulls: false,
        turboThreshold: 0, // points are objects (they carry their bucket for the tooltip)
        states: { inactive: { opacity: 1 } },
        marker: { enabled: false, radius: 2.5, symbol: 'circle' },
      },
    },
    xAxis: {
      type: 'datetime',
      min: w.start,
      max: w.end,
      minRange: MIN_RANGE_MS,
      ordinal: false,
      crosshair: { width: 1, color: '#9ca3af' },
      title: { text: null },
      labels: { style: { fontFamily: FONT, fontSize: '10px' } },
    } as Highcharts.XAxisOptions,
    yAxis,
    series: keys.length ? series : [],
  };
}

const MetricChart: React.FC<MetricChartProps> = (props) => {
  const { id, title, groupType, stationId, panes, height = 240, modalOpen = false } = props;
  const structure = JSON.stringify(panes);
  const keys = useMemo(
    () => (JSON.parse(structure) as string[][]).flat().map((m) => `${groupType}|${stationId}|${m}`),
    [structure, groupType, stationId]
  );
  const controller = useChartWindow(modalOpen ? `${id}:modal` : id, keys);
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLDivElement>(null);
  const selectRef = useRef<HTMLDivElement>(null);

  const chartHeight = modalOpen ? Math.round(height * 1.4) : height;
  // Rebuilt (a new chart) only when what is drawn changes: other measurements, panes or height
  const options = useMemo(
    () => buildOptions({ id, title, groupType, stationId, panes: JSON.parse(structure) }, keys, controller, chartHeight, modalOpen),
    [id, title, groupType, stationId, structure, keys, controller, chartHeight, modalOpen]
  );

  const error = useChartValue(controller, (s) => s.error);
  const firstLoad = useChartValue(controller, (s) => s.shownBucket === null && !s.error);
  const windowEmpty = useChartValue(controller, (s) => s.windowEmpty && s.shownBucket !== null && !s.loading);
  const noData = useChartValue(controller, (s) => s.hasData === false);

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
        const pts = d.series.get(key) ?? [];
        const info = s.options.custom as SeriesInfo;
        const unit = controller.meta(key)?.unit;
        if (unit && unit !== info.unit) {
          info.unit = unit;
          s.update({ name: seriesName(info.measurement, unit) } as Highcharts.SeriesOptionsType, false);
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
    return () => { offData(); offRedraw(); offGesture(); window.clearTimeout(a11yTimer); };
  }, [controller, keys, options]);

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
    const onDown = (e: PointerEvent) => {
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
    return () => {
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

  const kind = panes.flat().every((m) => aggOf(m) === 'sum') ? 'totals' : 'means';
  const plotId = `plot-${id}${modalOpen ? '-modal' : ''}`;
  const firstKey = keys.find((k) => !seriesNote(groupType, k.split('|')[2])?.hidden) ?? keys[0];
  return (
    <div className="min-w-0" data-testid={`chart-${id}`}>
      <ChartToolbar controller={controller} title={title} kind={kind} />
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
              {noData ? 'No readings from this sensor' : 'No readings in this period'}
            </p>
          </div>
        )}
        {error && (
          <div role="alert" className="absolute inset-x-4 top-6 z-10 mx-auto max-w-md rounded border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-700 shadow-sm">
            {error.message}{' '}
            <button type="button" onClick={() => controller.retry()}
              className="font-medium underline underline-offset-2 hover:text-red-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
              Retry
            </button>
          </div>
        )}
      </div>
      {keys.length > 0 && (
        <ChartSlider controller={controller} sparkKey={firstKey} color={measurementColor(firstKey.split('|')[2])} label={title} controls={plotId} />
      )}
    </div>
  );
};

export default MetricChart;
