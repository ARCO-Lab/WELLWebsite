// What a chart shows while a gesture (a drag, a pinch, a burst of wheel events) moves its window. A full Highcharts
// redraw of a card of ten series takes 55-80 ms on a desktop and several times that on a phone, too slow for every
// frame of a drag. A preview shows the moving window without one, and the chart is redrawn properly when the gesture
// pauses or ends. MetricChart uses it through this interface, so how it is drawn can change.

import type Highcharts from 'highcharts';

export interface Range { start: number; end: number }

export interface GesturePreview {
  /** Show window `w` (the first call of a gesture sets the preview up). */
  move(w: Range): void;
  /** Take the preview down (the chart is about to be redrawn for real). */
  end(): void;
  readonly active: boolean;
}

const PACE = 1.5; // as the controller paces redraws (lib/chartController.ts)

type NavigatorChart = Highcharts.Chart & { navigator?: { render(min: number, max: number): void } };
type LabelAxis = { labelGroup?: { element: SVGGElement } };

// The bitmap preview: the series as last drawn are copied into a layer over the plot, and each frame only moves and
// stretches that layer (a CSS transform on its own compositor layer: no layout, no repaint of the chart) and moves
// the navigator's window. The x-axis labels are hidden while the copy is moved (they would be wrong). When the window
// reaches past what was drawn, the chart is redrawn there for real and copied again, no sooner than its last redraw's
// cost allows (PACE times it after it ended), so between redraws the edges that weren't drawn show blank.
export function bitmapPreview(chart: Highcharts.Chart, host: HTMLElement): GesturePreview {
  let layer: HTMLDivElement | null = null;
  let drawn: Range | null = null; // the window the copy shows
  let hidden: SVGGElement[] = [];
  let cost = 0, lastEnd = -Infinity;
  const labels = () => (chart.xAxis?.[0] as unknown as LabelAxis | undefined)?.labelGroup?.element; // none once destroyed

  const take = () => {
    layer?.remove();
    layer = null;
    for (const g of hidden) g.style.visibility = '';
    hidden = [];
    drawn = null;
    const l = labels();
    if (l) l.style.visibility = '';
  };

  // Copy the series as they are drawn now (no redraw)
  const copy = () => {
    take();
    const groups = [...chart.container.querySelectorAll<SVGGElement>('.highcharts-series-group')];
    const svg = chart.container.querySelector('svg');
    const axis = chart.xAxis[0];
    if (!groups.length || !svg || axis.min === undefined || axis.max === undefined) return;
    const { plotLeft, plotTop, plotWidth, plotHeight, chartWidth, chartHeight } = chart;
    layer = document.createElement('div');
    Object.assign(layer.style, { // clipped to the plot, unmoved; the copy inside it moves
      position: 'absolute', left: '0', top: '0', width: `${chartWidth}px`, height: `${chartHeight}px`, pointerEvents: 'none',
      clipPath: `inset(${plotTop}px ${chartWidth - plotLeft - plotWidth}px ${chartHeight - plotTop - plotHeight}px ${plotLeft}px)`,
      contain: 'strict',
    });
    const moving = document.createElement('div');
    Object.assign(moving.style, { position: 'absolute', inset: '0', transformOrigin: '0 0', willChange: 'transform' });
    const svgCopy = svg.cloneNode(false) as SVGSVGElement;
    svgCopy.setAttribute('width', String(chartWidth));
    svgCopy.setAttribute('height', String(chartHeight));
    for (const g of groups) svgCopy.appendChild(g.cloneNode(true));
    moving.appendChild(svgCopy);
    layer.appendChild(moving);
    host.appendChild(layer);
    for (const g of groups) g.style.visibility = 'hidden';
    hidden = groups;
    drawn = { start: axis.min, end: axis.max };
  };

  const redrawAt = (w: Range) => {
    take();
    const t0 = performance.now();
    chart.xAxis[0].setExtremes(w.start, w.end, false, false);
    chart.redraw(false);
    lastEnd = performance.now();
    cost = lastEnd - t0;
    copy();
  };

  return {
    move(w) {
      if (!drawn) copy();
      if (drawn && (w.start < drawn.start || w.end > drawn.end) && performance.now() - lastEnd >= cost * PACE) redrawAt(w);
      if (!layer || !drawn) return;
      const { plotLeft, plotWidth } = chart;
      const k = (drawn.end - drawn.start) / (w.end - w.start);
      const tx = plotLeft * (1 - k) + ((drawn.start - w.start) / (w.end - w.start)) * plotWidth;
      (layer.firstChild as HTMLDivElement).style.transform = `translateX(${tx}px) scaleX(${k})`;
      const l = labels();
      if (l) l.style.visibility = Math.abs(tx) < 0.5 && Math.abs(k - 1) < 1e-3 ? '' : 'hidden';
      (chart as NavigatorChart).navigator?.render(w.start, w.end);
    },
    end: take,
    get active() { return layer !== null; },
  };
}

// ---- The canvas preview ----

/** One series as the canvas preview paints it: points in time order (y null: a gap), and how it is drawn. */
export interface PaintSeries { id: string; points: { x: number; y: number | null }[]; kind: 'line' | 'bars' | 'dots' }

const MAX_CANVAS_PX = 4096; // the widest a painted canvas gets (CSS px): room to pan without painting again
const ZOOM_MARGIN = 0.6; // while zooming, windows painted on each side
const RESNAP = 1.6; // painted again when stretched or squeezed past this
const RELEASE_AFTER_MS = 10_000; // a canvas unused this long gives its memory back

type Tick = { pos: number; label?: Highcharts.SVGElement; mark?: Highcharts.SVGElement; gridLine?: Highcharts.SVGElement };
type TickAxis = Highcharts.Axis & { ticks?: Record<string, Tick> };

// The canvas preview: while a gesture runs, the series are painted on one canvas per chart (reused, never one per
// paint) straight from the data the chart has loaded, a few windows wide, with the y scales of the last real redraw.
// Each frame only moves and stretches the canvas (a CSS transform), shifts the x-axis ticks and moves the navigator's
// window: no Highcharts redraw until the gesture ends. It is painted again (a few ms) when stretched past RESNAP or
// when the window nears its edge. `series` gives the data to paint, by series id.
// `navDragging`: a navigator drag is on (the container then keeps its pointer events: the drag needs them).
export function canvasPreview(chart: Highcharts.Chart, host: HTMLElement, series: () => PaintSeries[],
  navDragging: () => boolean = () => false): GesturePreview {
  const box = document.createElement('div');
  const inner = document.createElement('div');
  const canvas = document.createElement('canvas');
  inner.appendChild(canvas);
  box.appendChild(inner);
  let painted: { base: Range; from: number; to: number; x0: number } | null = null;
  let drawn: Range | null = null; // the window Highcharts last drew (its ticks and y scales)
  let hidden: SVGGElement[] = [];
  let lastSpan = 0;
  let release = 0; // frees the canvas's memory (~16 MB on a phone) a while after a gesture, until the next one

  const paintSeries = (g: CanvasRenderingContext2D, ps: PaintSeries, X: (t: number) => number, a: number, z: number) => {
    const s = chart.get(ps.id) as Highcharts.Series | undefined;
    if (!s || !s.visible) return;
    const ya = s.yAxis, Y = (v: number) => ya.toPixels(v, true);
    g.strokeStyle = g.fillStyle = String(s.color);
    // Only the points over the painted span, and one each side so lines run to the edges
    const pts = ps.points;
    if (!pts.length) return;
    let lo = 0, hi = pts.length;
    while (lo < hi) { const m = (lo + hi) >> 1; if (pts[m].x < a) lo = m + 1; else hi = m; }
    const from = Math.max(0, lo - 1);
    let to = from;
    while (to < pts.length - 1 && pts[to].x <= z) to++;
    if (ps.kind === 'dots') {
      for (let i = from; i <= to; i++) { const y = pts[i].y; if (y !== null) g.fillRect(X(pts[i].x) - 1.5, Y(y) - 1.5, 3, 3); }
      return;
    }
    if (ps.kind === 'bars') { // rain: a bar per bucket from 0, as wide as the space to its neighbours (as Highcharts draws columns)
      const y0 = Y(0);
      for (let i = from; i <= to; i++) {
        const y = pts[i].y;
        if (y === null || y <= 0) continue;
        const x = X(pts[i].x);
        const left = i > 0 ? (x - X(pts[i - 1].x)) / 2 : Infinity, right = i < pts.length - 1 ? (X(pts[i + 1].x) - x) / 2 : Infinity;
        const half = Math.min(left, right, 40);
        const w = Math.max(1, (Number.isFinite(half) ? half : 1.5) * 2);
        g.fillRect(x - w / 2, Y(y), w, y0 - Y(y));
      }
      return;
    }
    g.lineWidth = 1.5;
    g.beginPath();
    for (let i = from; i <= to; i++) {
      const y = pts[i].y;
      if (y === null) continue;
      const prev = i > from ? pts[i - 1].y : null;
      if (prev === null) g.moveTo(X(pts[i].x), Y(y));
      else g.lineTo(X(pts[i].x), Y(y));
    }
    g.stroke();
    // A reading between two gaps (a line can't show it): a dot, as the chart marks it
    for (let i = from; i <= to; i++) {
      if (pts[i].y === null) continue;
      const before = i === 0 || pts[i - 1].y === null, after = i === pts.length - 1 || pts[i + 1].y === null;
      if (before && after) g.fillRect(X(pts[i].x) - 1.5, Y(pts[i].y as number) - 1.5, 3, 3);
    }
  };

  const paint = (base: Range, zooming: boolean) => {
    const W = chart.plotWidth, H = chart.plotHeight, span = base.end - base.start;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const k = zooming ? ZOOM_MARGIN : Math.max(0.25, (MAX_CANVAS_PX / W - 1) / 2);
    const a = base.start - span * k, z = base.end + span * k;
    const x0 = Math.floor(-k * W), cw = Math.ceil((1 + 2 * k) * W);
    const pw = Math.round(cw * dpr), ph = Math.round(H * dpr);
    if (canvas.width !== pw || canvas.height !== ph) { canvas.width = pw; canvas.height = ph; }
    canvas.style.cssText = `display:block;width:${cw}px;height:${H}px`;
    const g = canvas.getContext('2d');
    if (!g) return;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, pw, ph);
    g.scale(dpr, dpr);
    g.lineJoin = 'round';
    const X = (t: number) => ((t - base.start) / span) * W - x0;
    for (const ps of series()) paintSeries(g, ps, X, a, z);
    painted = { base: { ...base }, from: a, to: z, x0 };
  };

  const show = () => {
    const { plotLeft, plotTop, plotWidth, plotHeight } = chart;
    box.style.cssText = `position:absolute;left:${plotLeft}px;top:${plotTop}px;width:${plotWidth}px;height:${plotHeight}px;overflow:hidden;pointer-events:none;contain:strict`;
    if (box.parentNode !== host) host.appendChild(box);
    // The chart's own series, not the navigator's (Stock marks those internal)
    hidden = [];
    for (const se of chart.series as (Highcharts.Series & { group?: Highcharts.SVGElement; markerGroup?: Highcharts.SVGElement })[]) {
      if ((se.options as { isInternal?: boolean }).isInternal) continue;
      for (const g of [se.group, se.markerGroup]) if (g) hidden.push(g.element as SVGGElement);
    }
    for (const g of hidden) g.style.visibility = 'hidden';
    chart.tooltip?.hide(0);
    (chart.xAxis[0] as Highcharts.Axis & { hideCrosshair?: () => void }).hideCrosshair?.();
    // No hovering while the canvas stands in for the series: the tooltip and crosshair would describe stale points
    if (!navDragging()) chart.container.style.pointerEvents = 'none';
  };

  // The x-axis ticks of the last real redraw, shifted to where their times now are (hidden past the plot's edges)
  const ticks = (w: Range) => {
    if (!drawn) return;
    const axis = chart.xAxis[0] as TickAxis, W = chart.plotWidth;
    const span = w.end - w.start, dspan = drawn.end - drawn.start;
    for (const t of Object.values(axis.ticks ?? {})) {
      const dx = ((t.pos - w.start) / span - (t.pos - drawn.start) / dspan) * W;
      const px = ((t.pos - w.start) / span) * W;
      const opacity = px >= -1 && px <= W + 1 ? 1 : 0;
      for (const el of [t.label, t.mark, t.gridLine]) el?.attr({ translateX: dx, opacity });
    }
  };

  return {
    move(w) {
      const span = w.end - w.start;
      const zooming = lastSpan > 0 && Math.abs(span - lastSpan) > span * 0.001;
      lastSpan = span;
      window.clearTimeout(release);
      if (!drawn) {
        const axis = chart.xAxis[0];
        drawn = { start: axis.min ?? w.start, end: axis.max ?? w.end };
        show();
      }
      let k = painted ? (painted.base.end - painted.base.start) / span : 1;
      if (!painted || k > RESNAP || k < 1 / RESNAP || w.start < painted.from || w.end > painted.to) {
        paint(w, zooming);
        k = 1;
      }
      if (!painted) return;
      const t = ((painted.base.start - w.start) / span) * chart.plotWidth;
      const x = k * painted.x0 + t - painted.x0;
      inner.style.cssText = `position:absolute;left:${painted.x0}px;top:0;transform-origin:0 0;will-change:transform;transform:translateX(${x}px) scaleX(${k})`;
      ticks(w);
      (chart as NavigatorChart).navigator?.render(w.start, w.end);
    },
    end() {
      // Also called when the chart is being destroyed (unmount): whatever of it is already gone is skipped
      if (drawn && chart.xAxis?.[0]) ticks(drawn);
      box.remove();
      for (const g of hidden) g.style.visibility = '';
      hidden = [];
      painted = null;
      drawn = null;
      lastSpan = 0;
      if (chart.container) chart.container.style.pointerEvents = '';
      window.clearTimeout(release);
      release = window.setTimeout(() => { canvas.width = 0; canvas.height = 0; }, RELEASE_AFTER_MS);
    },
    get active() { return drawn !== null; },
  };
}

// The first 2D canvas a page paints costs a one-time set-up (measured 240-300 ms) that would land in the first gesture:
// paint a throwaway one when the page is idle after load.
let warmed = false;
export function warmCanvas(): void {
  if (warmed || typeof window === 'undefined') return;
  warmed = true;
  const w = window as Window & { requestIdleCallback?: (cb: () => void) => number };
  const idle = (cb: () => void) => (w.requestIdleCallback ? w.requestIdleCallback(cb) : w.setTimeout(cb, 1000));
  idle(() => {
    const c = document.createElement('canvas');
    c.width = 512;
    c.height = 128;
    c.style.cssText = 'position:fixed;left:-9999px;top:0;width:512px;height:128px;will-change:transform';
    document.body.appendChild(c);
    const g = c.getContext('2d');
    if (g) {
      g.beginPath();
      for (let i = 0; i < 512; i += 4) g.lineTo(i, 64 + 50 * Math.sin(i / 30));
      g.stroke();
    }
    window.setTimeout(() => c.remove(), 500);
  });
}

// No preview: every frame of a gesture is a real redraw, at the pace the controller sets from what redraws cost.
export const noPreview: GesturePreview = { move: () => {}, end: () => {}, active: false };
