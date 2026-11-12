// The horizontal scrollbar under a chart. Its thumb is the chart's window within all the data there is: drag it to
// move the window, drag its ends to resize it, press the track to page a whole window that way (repeating while
// held), or use the arrows at either end. With focus: ← → move a little, Page Up / Page Down a whole window, Home /
// End to either end. On touch screens a finger moving sideways drags or pages, a tap pages once, and a vertical
// swipe that starts on the bar scrolls the page as anywhere else. Behind the thumb, the whole history as a faint line
// (one series of the chart, daily, from the tiles the chart already loads; no request of its own), so the bar also
// shows where the data is. Drawn with Highcharts Core and plain HTML (not Highcharts Stock's navigator, which costs
// 4-5 times as much to redraw), and updated every frame straight from the chart's controller, without React.

import React, { useEffect, useRef } from "react";
import Highcharts from "highcharts";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ChartController } from "@/lib/chartController";
import { MIN_RANGE_MS, TIME_ZONE } from "@/utils/chartWindow";
import { windowLabel } from "@/components/graphs/ChartToolbar";

const PAGE_REPEAT_MS = 300;
const MIN_THUMB_PX = 24;
const TOUCH_SLOP_PX = 6; // a finger must move this far before its direction decides what it does

interface Props {
  controller: ChartController;
  sparkKey: string; // the series drawn faintly in the track
  color: string;
  label: string; // the chart's title, for the scrollbar's accessible name
  controls?: string; // the id of the chart it scrolls
}

const ChartSlider: React.FC<Props> = ({ controller, sparkKey, color, label, controls }) => {
  const track = useRef<HTMLDivElement>(null);
  const spark = useRef<HTMLDivElement>(null);
  const thumb = useRef<HTMLDivElement>(null);

  // The line: built once, updated when overview tiles arrive
  useEffect(() => {
    if (!spark.current) return;
    const ext = controller.extent;
    const chart = Highcharts.chart(spark.current, {
      chart: { height: 30, spacing: [4, 0, 4, 0], animation: false, backgroundColor: "transparent", style: { pointerEvents: "none" } },
      time: { timezone: TIME_ZONE },
      title: { text: undefined }, credits: { enabled: false }, legend: { enabled: false }, tooltip: { enabled: false },
      accessibility: { enabled: false }, // decoration: the scrollbar itself carries the accessible name and value
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

  // The thumb, once per frame, and the scrollbar's value for screen readers (how far along, and the dates)
  useEffect(() => {
    const place = () => {
      const e = controller.extent, w = controller.window, total = e.end - e.start;
      const el = track.current;
      if (thumb.current && el) {
        // In pixels, so a thumb kept at its smallest grabbable width (MIN_THUMB_PX) still lies wholly inside the track
        const W = el.clientWidth;
        const width = Math.max(((w.end - w.start) / total) * W, MIN_THUMB_PX);
        const left = Math.min(Math.max(((w.start - e.start) / total) * W, 0), W - width);
        thumb.current.style.left = `${left}px`;
        thumb.current.style.width = `${width}px`;
      }
    };
    // The value and its text (the dates) for assistive technology: only when the window settles, not every frame of a
    // drag (formatting is slow on a phone, and a value changing many times a second is just noise to a screen reader)
    const describe = () => {
      const el = track.current;
      if (!el) return;
      const e = controller.extent, w = controller.window, room = e.end - e.start - (w.end - w.start);
      el.setAttribute("aria-valuenow", String(room > 0 ? Math.round(((w.start - e.start) / room) * 100) : 0));
      el.setAttribute("aria-valuetext", windowLabel(w, e.end));
    };
    place();
    describe();
    const offFrame = controller.onFrame(place);
    const offSnap = controller.subscribe(() => { place(); describe(); }); // extent changes, and the end of a gesture
    const resized = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(place); // pixels: follow the width
    if (track.current) resized?.observe(track.current);
    return () => { offFrame(); offSnap(); resized?.disconnect(); };
  }, [controller]);

  // Dragging the thumb (or its edges, to resize), and paging: a press on the track moves the window a whole width
  // towards the press, again every PAGE_REPEAT_MS while held, as a scrollbar does.
  useEffect(() => {
    const el = track.current;
    if (!el) return;
    let drag: { mode: "move" | "l" | "r"; x0: number; w0: { start: number; end: number }; width: number } | null = null;
    let paging = 0;
    let pageX = 0;
    // A touch (or pen) that hasn't moved TOUCH_SLOP_PX yet: sideways makes it a drag or paging, down or up leaves it
    // to the browser (the page scrolls: the track is touch-action: pan-y), lifting it in place is a tap (one page)
    type Press = { id: number; x0: number; y0: number; onThumb: boolean; edge?: string };
    let pending: Press | null = null;
    const pageTowards = () => {
      const box = el.getBoundingClientRect(), ext = controller.extent, w = controller.window;
      const t = ext.start + ((pageX - box.left) / box.width) * (ext.end - ext.start);
      if (t < w.start) controller.pan(-1, "slider");
      else if (t > w.end) controller.pan(1, "slider");
      else stopPaging(); // the thumb has reached the press
    };
    const stopPaging = () => { window.clearInterval(paging); paging = 0; };
    const press = (e: PointerEvent): Press => {
      const target = e.target as HTMLElement;
      // A thumb only a few pixels wide is moved, not resized: its edges would cover it
      const narrow = (thumb.current?.offsetWidth ?? 0) < 32;
      return {
        id: e.pointerId, x0: e.clientX, y0: e.clientY,
        onThumb: target === thumb.current || !!target.dataset.handle || !!target.closest?.("[data-thumb]"),
        edge: narrow ? undefined : target.dataset.handle,
      };
    };
    // Start dragging the thumb (from where the press began) or paging towards the press
    const begin = (p: Press, clientX: number) => {
      el.setPointerCapture(p.id);
      el.focus({ preventScroll: true });
      controller.beginGesture(); // no requests until the drag or paging ends (lib/chartController)
      if (!p.onThumb) {
        pageX = clientX;
        pageTowards();
        paging = window.setInterval(pageTowards, PAGE_REPEAT_MS);
        return;
      }
      drag = { mode: p.edge === "l" ? "l" : p.edge === "r" ? "r" : "move", x0: p.x0, w0: { ...controller.window }, width: el.getBoundingClientRect().width };
    };
    const down = (e: PointerEvent) => {
      if (e.button !== 0) return;
      if (e.pointerType === "mouse") {
        e.preventDefault(); // no text selection
        begin(press(e), e.clientX);
      } else {
        pending = press(e);
      }
    };
    const move = (e: PointerEvent) => {
      if (pending && e.pointerId === pending.id) {
        const dx = e.clientX - pending.x0, dy = e.clientY - pending.y0;
        if (Math.max(Math.abs(dx), Math.abs(dy)) < TOUCH_SLOP_PX) return;
        const p = pending;
        pending = null;
        if (Math.abs(dx) > Math.abs(dy)) begin(p, e.clientX); // sideways: this bar's; otherwise the page scrolls
        else return;
      }
      if (paging) { pageX = e.clientX; return; }
      if (!drag) return;
      const ext = controller.extent;
      const dt = ((e.clientX - drag.x0) / drag.width) * (ext.end - ext.start);
      const w0 = drag.w0;
      if (drag.mode === "move") controller.setWindow({ start: w0.start + dt, end: w0.end + dt }, "slider");
      else if (drag.mode === "l") controller.setWindow({ start: Math.min(w0.start + dt, w0.end - MIN_RANGE_MS), end: w0.end }, "slider", "end");
      else controller.setWindow({ start: w0.start, end: Math.max(w0.end + dt, w0.start + MIN_RANGE_MS) }, "slider", "start");
    };
    const up = (e: PointerEvent) => {
      if (pending && e.pointerId === pending.id) { // a tap: one page towards it (on the thumb: nothing)
        const p = pending;
        pending = null;
        if (!p.onThumb) {
          pageX = p.x0;
          pageTowards();
        }
        return;
      }
      end();
    };
    const end = () => {
      if (!drag && !paging) return;
      drag = null;
      stopPaging();
      controller.endGesture();
    };
    // Cancelled (the browser took the touch to scroll the page, or the system did): a press not yet decided does
    // nothing; a drag or paging under way stops where it is
    const cancel = () => {
      pending = null;
      end();
    };
    const key = (e: KeyboardEvent) => {
      const ext = controller.extent, w = controller.window, span = w.end - w.start;
      const acts: Record<string, () => void> = {
        ArrowLeft: () => controller.pan(-0.1, "key"),
        ArrowRight: () => controller.pan(0.1, "key"),
        PageUp: () => controller.pan(-1, "key"),
        PageDown: () => controller.pan(1, "key"),
        Home: () => controller.setWindow({ start: ext.start, end: ext.start + span }, "key"),
        End: () => controller.setWindow({ start: ext.end - span, end: ext.end }, "key"),
      };
      const act = acts[e.key];
      if (act) {
        e.preventDefault();
        act();
      }
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", cancel);
    el.addEventListener("lostpointercapture", end);
    el.addEventListener("keydown", key);
    return () => {
      stopPaging();
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", cancel);
      el.removeEventListener("lostpointercapture", end);
      el.removeEventListener("keydown", key);
    };
  }, [controller]);

  const arrow = (dir: -1 | 1) => (
    // Arrows like a scrollbar's; the toolbar has the same moves as labelled buttons, so these stay out of the tab order
    <button type="button" tabIndex={-1} aria-hidden="true" onClick={() => controller.pan(dir * 0.1, "button")}
      className="grid h-8 w-6 shrink-0 place-items-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-800">
      {dir < 0 ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
    </button>
  );

  return (
    <div className="mt-1 flex items-center gap-0.5" data-testid="chart-slider">
      {arrow(-1)}
      <div
        ref={track}
        role="scrollbar"
        tabIndex={0}
        aria-orientation="horizontal"
        aria-controls={controls}
        aria-label={`${label}: time scrollbar. Arrow keys move it a little, Page Up and Page Down a whole window.`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={0}
        className="relative h-8 min-w-0 flex-1 touch-pan-y select-none overflow-hidden rounded-full border border-gray-200 bg-gray-100 outline-none focus-visible:ring-2 focus-visible:ring-primary"
        title="Drag to move the window; drag its ends to resize it; click the track to page"
      >
        {/* The same box as the thumb's, so a point in the history lines up with the thumb over it */}
        <div ref={spark} className="pointer-events-none absolute inset-0 opacity-60" />
        <div ref={thumb} data-thumb data-testid="chart-slider-window"
          className="absolute inset-y-0.5 cursor-grab rounded-full border border-primary/60 bg-primary/20 shadow-sm active:cursor-grabbing">
          {/* Grip lines in the middle, so it reads as something to drag */}
          <span className="pointer-events-none absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 gap-0.5">
            <span className="h-3 w-px bg-primary/70" /><span className="h-3 w-px bg-primary/70" /><span className="h-3 w-px bg-primary/70" />
          </span>
          <div data-handle="l" className="absolute inset-y-0 left-0 w-2 cursor-ew-resize rounded-l-full" />
          <div data-handle="r" className="absolute inset-y-0 right-0 w-2 cursor-ew-resize rounded-r-full" />
        </div>
      </div>
      {arrow(1)}
    </div>
  );
};

export default ChartSlider;
