// What a chart shows while a gesture (a drag, a pinch, a burst of wheel events) moves its window. A full Highcharts
// redraw of a card of ten series takes 55-80 ms on a desktop and several times that on a phone, too slow for every
// frame of a drag. A preview shows the moving window without one, and the chart is redrawn properly when the gesture
// pauses or ends. MetricChart uses it through this interface, so how it is drawn can change.

import type Highcharts from 'highcharts';

export interface Range { start: number; end: number }

export interface GesturePreview {
  /** Whether window `w` can be shown from what the preview has drawn (always, before the first move). */
  covers(w: Range): boolean;
  /** Show window `w`. The first call of a gesture sets the preview up (one redraw). */
  move(w: Range): void;
  /** Take the preview down (the chart is about to be redrawn for real). */
  end(): void;
  readonly active: boolean;
}

type NavigatorChart = Highcharts.Chart & { navigator?: { render(min: number, max: number): void } };
type AxisGroups = { gridGroup?: { element: SVGGElement }; labelGroup?: { element: SVGGElement } };

// The bitmap preview: the chart is drawn once over the window and a window on each side of it, its series are copied
// into a layer of their own, and each frame only moves and stretches that layer and the x-axis's ticks and labels
// (CSS transforms, which the browser applies without layout or repaint) and moves the navigator's window. Labels
// stretch a little while zooming, until the real redraw. `extent`: how far the chart can be moved.
export function bitmapPreview(chart: Highcharts.Chart, host: HTMLElement, extent: () => Range): GesturePreview {
  let layer: HTMLDivElement | null = null;
  let drawn: Range | null = null; // the span the copied series were drawn over
  let hidden: SVGGElement[] = [];
  let moved: SVGGElement[] = [];

  const take = () => {
    layer?.remove();
    layer = null;
    for (const g of hidden) g.style.visibility = '';
    for (const g of moved) g.style.transform = '';
    hidden = [];
    moved = [];
    drawn = null;
  };

  const setUp = (w: Range) => {
    take();
    const axis = chart.xAxis[0];
    const ext = extent();
    const span = w.end - w.start;
    const wide = { start: Math.max(ext.start, w.start - span), end: Math.min(ext.end, w.end + span) };
    axis.setExtremes(wide.start, wide.end, false, false);
    chart.redraw(false);
    const groups = [...chart.container.querySelectorAll<SVGGElement>('.highcharts-series-group')];
    const svg = chart.container.querySelector('svg');
    if (!groups.length || !svg) return;
    layer = document.createElement('div');
    const { plotLeft, plotTop, plotWidth, plotHeight, chartWidth, chartHeight } = chart;
    // Clipped to the plot, unmoved; the copy inside it moves
    Object.assign(layer.style, {
      position: 'absolute', left: '0', top: '0', width: `${chartWidth}px`, height: `${chartHeight}px`, pointerEvents: 'none',
      clipPath: `inset(${plotTop}px ${chartWidth - plotLeft - plotWidth}px ${chartHeight - plotTop - plotHeight}px ${plotLeft}px)`,
    });
    const moving = document.createElement('div');
    Object.assign(moving.style, { position: 'absolute', inset: '0', transformOrigin: '0 0', willChange: 'transform' });
    const copy = svg.cloneNode(false) as SVGSVGElement;
    copy.setAttribute('width', String(chartWidth));
    copy.setAttribute('height', String(chartHeight));
    for (const g of groups) {
      const c = g.cloneNode(true) as SVGGElement;
      // The series' own clip is the plot at the old scale: what lies past it is wanted now
      c.removeAttribute('clip-path');
      for (const el of c.querySelectorAll('[clip-path]')) el.removeAttribute('clip-path');
      copy.appendChild(c);
    }
    moving.appendChild(copy);
    layer.appendChild(moving);
    host.appendChild(layer);
    for (const g of groups) g.style.visibility = 'hidden';
    hidden = groups;
    const a = axis as unknown as AxisGroups;
    moved = [a.gridGroup?.element, a.labelGroup?.element].filter((g): g is SVGGElement => !!g);
    for (const g of moved) g.style.transformOrigin = '0 0';
    drawn = wide;
  };

  const place = (w: Range) => {
    if (!layer || !drawn) return;
    const { plotLeft, plotWidth } = chart;
    const k = (drawn.end - drawn.start) / (w.end - w.start);
    const tx = plotLeft * (1 - k) + ((drawn.start - w.start) / (w.end - w.start)) * plotWidth;
    const transform = `translateX(${tx}px) scaleX(${k})`;
    (layer.firstChild as HTMLDivElement).style.transform = transform;
    for (const g of moved) g.style.transform = transform;
    (chart as NavigatorChart).navigator?.render(w.start, w.end);
  };

  return {
    covers: (w) => !drawn || (w.start >= drawn.start && w.end <= drawn.end),
    move(w) {
      if (!drawn) setUp(w);
      place(w);
    },
    end: take,
    get active() { return layer !== null; },
  };
}

// No preview: every frame of a gesture is a real redraw, at the pace the controller sets from what redraws cost.
export const noPreview: GesturePreview = { covers: () => false, move: () => {}, end: () => {}, active: false };
