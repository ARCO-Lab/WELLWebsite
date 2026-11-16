// One-finger touches on a chart, kept from Highcharts until they turn out to be meant for it.
//
// Highcharts answers every touchstart on a chart by finding the nearest points and drawing the tooltip, and the
// browser can't start scrolling until that is done: on a phone each page scroll that began on a chart started late
// (0.25-0.45 s at 4x CPU slowdown) and flashed a tooltip nobody asked for. On charts that follow the finger (the
// sampling charts) it did the same again on every touchmove of that scroll.
//
// With this, a one-finger touch reaches Highcharts only once it is known to be for the chart:
// - a tap (lifted about where it landed): Highcharts gets its touchstart on release, so the tooltip shows then;
// - with `scrub`, a touch that first moves sideways: Highcharts gets its touchstart and every move after it, so the
//   tooltip follows the finger as before. Without `scrub` (a chart that pans under the finger itself) no move does.
// A touch that first moves up or down is the page's scroll: Highcharts never hears of it. Touches of two or more
// fingers (a pinch) pass through untouched. These listeners are passive, so they never hold up a scroll themselves.

import type Highcharts from "highcharts";

const SLOP_PX = 8; // a finger that has moved less than this is still a tap

interface Options {
  scrub?: boolean; // a sideways move goes to Highcharts (its tooltip follows the finger)
  ignore?: (touch: Touch) => boolean; // a touch that starts here is never Highcharts' (the chart's own range bar)
}

type TouchPointer = { onContainerTouchStart?: (e: TouchEvent) => void };

/** Listens on `el` (an ancestor of the chart's container), before the events reach Highcharts. Returns the undo. */
export function quietTouch(el: HTMLElement, chart: () => Highcharts.Chart | undefined, options: Options = {}): () => void {
  // waiting: one finger down, not moved yet; page: it is scrolling the page; chart: Highcharts has it
  let state: "idle" | "waiting" | "page" | "chart" = "idle";
  let start: TouchEvent | null = null;
  let x0 = 0, y0 = 0;

  // Highcharts does now what it would have done when the finger landed
  const hand = () => {
    const pointer = chart()?.pointer as TouchPointer | undefined;
    if (start && pointer?.onContainerTouchStart) pointer.onContainerTouchStart(start);
    start = null;
  };

  const onStart = (e: TouchEvent) => {
    if (e.touches.length !== 1) { // a second finger: Highcharts' from here on (or the chart's own pinch)
      state = "chart";
      start = null;
      return;
    }
    const t = e.touches[0];
    e.stopPropagation();
    if (options.ignore?.(t)) {
      state = "page";
      start = null;
      return;
    }
    state = "waiting";
    start = e;
    x0 = t.clientX;
    y0 = t.clientY;
  };
  const onMove = (e: TouchEvent) => {
    if (state === "chart" || state === "idle") return;
    if (state === "waiting") {
      const t = e.touches[0];
      const dx = Math.abs(t.clientX - x0), dy = Math.abs(t.clientY - y0);
      if (Math.max(dx, dy) >= SLOP_PX) {
        if (options.scrub && dx > dy) {
          state = "chart";
          hand();
          return; // this move, and the ones after it, reach Highcharts
        }
        state = "page";
        start = null;
      }
    }
    e.stopPropagation();
  };
  const onEnd = (e: TouchEvent) => {
    if (e.touches.length > 0) return;
    if (state === "waiting") hand(); // a tap
    state = "idle";
    start = null;
  };
  const onCancel = () => { // the browser took the touch (a scroll): not a tap
    state = "idle";
    start = null;
  };

  const capture = { capture: true, passive: true } as const;
  el.addEventListener("touchstart", onStart, capture);
  el.addEventListener("touchmove", onMove, capture);
  el.addEventListener("touchend", onEnd, capture);
  el.addEventListener("touchcancel", onCancel, capture);
  return () => {
    el.removeEventListener("touchstart", onStart, capture);
    el.removeEventListener("touchmove", onMove, capture);
    el.removeEventListener("touchend", onEnd, capture);
    el.removeEventListener("touchcancel", onCancel, capture);
  };
}
