// The strip under a chart: the whole history as a thin line (one series of the chart, daily, from the tiles the
// chart already loads; no request of its own) with the chart's window drawn over it. Drag the window to move it,
// drag its edges to resize it, click (or tap) elsewhere to centre it there. Works with one finger on touch screens.
// It is drawn with Highcharts Core and plain HTML (Highcharts Stock's navigator isn't licensed here), and updates
// once per frame straight from the chart's controller, without re-rendering React.

import React, { useEffect, useRef } from "react";
import Highcharts from "highcharts";
import type { ChartController } from "@/lib/chartController";
import { MIN_RANGE_MS, TIME_ZONE } from "@/utils/chartWindow";

interface Props {
  controller: ChartController;
  sparkKey: string; // the series drawn in the strip
  color: string;
  label: string; // what the strip moves, for its accessible name
}

const ChartSlider: React.FC<Props> = ({ controller, sparkKey, color, label }) => {
  const strip = useRef<HTMLDivElement>(null);
  const spark = useRef<HTMLDivElement>(null);
  const win = useRef<HTMLDivElement>(null);
  const shadeL = useRef<HTMLDivElement>(null);
  const shadeR = useRef<HTMLDivElement>(null);

  // The line: built once, updated when overview tiles arrive
  useEffect(() => {
    if (!spark.current) return;
    const ext = controller.extent;
    const chart = Highcharts.chart(spark.current, {
      chart: { height: 44, spacing: [3, 0, 3, 0], animation: false, backgroundColor: "#f9fafb", style: { pointerEvents: "none" } },
      time: { timezone: TIME_ZONE },
      title: { text: undefined }, credits: { enabled: false }, legend: { enabled: false }, tooltip: { enabled: false },
      accessibility: { enabled: false }, // the strip is hidden from screen readers; the chart's buttons do the same
      xAxis: { visible: false, min: ext.start, max: ext.end },
      yAxis: { visible: false },
      plotOptions: { series: { animation: false, enableMouseTracking: false, lineWidth: 1, color, marker: { enabled: false } } },
      series: [{ type: "line", data: [] }],
    });
    let shown = -1;
    const update = () => {
      const pts = controller.overview(sparkKey);
      if (pts.length === shown) return;
      shown = pts.length;
      chart.series[0].setData(pts.map((p) => [p.x, p.y]), false, false, false);
      const e = controller.extent;
      chart.xAxis[0].setExtremes(e.start, e.end, false, false);
      chart.redraw(false);
    };
    update();
    const off = controller.onData(update);
    return () => {
      off();
      chart.destroy();
    };
  }, [controller, sparkKey, color]);

  // The window over the line, once per frame
  useEffect(() => {
    const place = () => {
      const e = controller.extent, w = controller.window, total = e.end - e.start;
      const l = ((w.start - e.start) / total) * 100, r = ((w.end - e.start) / total) * 100;
      if (win.current) {
        win.current.style.left = `${l}%`;
        win.current.style.width = `${Math.max(r - l, 0.3)}%`;
      }
      if (shadeL.current) shadeL.current.style.width = `${l}%`;
      if (shadeR.current) shadeR.current.style.left = `${r}%`;
    };
    place();
    const offFrame = controller.onFrame(place);
    const offSnap = controller.subscribe(place); // extent changes
    return () => { offFrame(); offSnap(); };
  }, [controller]);

  // Dragging
  useEffect(() => {
    const el = strip.current;
    if (!el) return;
    let drag: { mode: "move" | "l" | "r"; x0: number; w0: { start: number; end: number }; width: number } | null = null;
    const down = (e: PointerEvent) => {
      if (e.button !== 0) return;
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      const box = el.getBoundingClientRect();
      const ext = controller.extent, total = ext.end - ext.start;
      const target = e.target as HTMLElement;
      // A window only a few pixels wide is moved, not resized: its handles would cover it
      const narrow = (win.current?.offsetWidth ?? 0) < 24;
      const handle = narrow ? undefined : target.dataset.handle;
      const onWindow = target === win.current || !!target.dataset.handle;
      const mode = handle === "l" ? "l" : handle === "r" ? "r" : onWindow ? "move" : null;
      if (!mode) { // centre the window where the strip was clicked, then drag it from there
        const t = ext.start + ((e.clientX - box.left) / box.width) * total;
        const w = controller.window, half = (w.end - w.start) / 2;
        controller.setWindow({ start: t - half, end: t + half }, "slider");
      }
      drag = { mode: mode ?? "move", x0: e.clientX, w0: { ...controller.window }, width: box.width };
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const ext = controller.extent;
      const dt = ((e.clientX - drag.x0) / drag.width) * (ext.end - ext.start);
      const w0 = drag.w0;
      if (drag.mode === "move") controller.setWindow({ start: w0.start + dt, end: w0.end + dt }, "slider");
      else if (drag.mode === "l") controller.setWindow({ start: Math.min(w0.start + dt, w0.end - MIN_RANGE_MS), end: w0.end }, "slider", "end");
      else controller.setWindow({ start: w0.start, end: Math.max(w0.end + dt, w0.start + MIN_RANGE_MS) }, "slider", "start");
    };
    const up = () => { drag = null; };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
    };
  }, [controller]);

  return (
    <div
      ref={strip}
      className="relative mt-1 h-11 touch-none select-none overflow-hidden rounded border border-gray-200"
      aria-hidden="true" // the toolbar's buttons and the chart's keys do the same for keyboards and screen readers
      data-testid="chart-slider"
      title={`Drag to move ${label}; drag an edge to resize; click to centre`}
    >
      <div ref={spark} className="pointer-events-none absolute inset-0" />
      <div ref={shadeL} className="pointer-events-none absolute inset-y-0 left-0 bg-white/60" />
      <div ref={shadeR} className="pointer-events-none absolute inset-y-0 right-0 bg-white/60" />
      <div ref={win} data-testid="chart-slider-window"
        className="absolute inset-y-0 min-w-2 cursor-grab rounded-sm border border-primary/70 bg-primary/10 active:cursor-grabbing">
        <div data-handle="l" className="absolute inset-y-1.5 -left-1.5 w-3 cursor-ew-resize rounded-sm border border-primary/80 bg-white" />
        <div data-handle="r" className="absolute inset-y-1.5 -right-1.5 w-3 cursor-ew-resize rounded-sm border border-primary/80 bg-white" />
      </div>
    </div>
  );
};

export default ChartSlider;
