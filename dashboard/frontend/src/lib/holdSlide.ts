// Holding ‹ or › slides the window continuously: slowly at first, easing up to a steady speed, until the edge of the
// picked range or the release. The whole hold is one gesture for the controller, so its data requests wait for the
// end (one request, not one per step) and the chart is only redrawn meanwhile. With reduced motion, the hold steps a
// whole window at a time instead of sliding. No React or browser globals here (frames and the clock are passed in),
// so scripts/chartWindow.test.mjs can test it.

export interface Slidable {
  readonly window: { start: number; end: number };
  readonly extent: { start: number; end: number };
  pan(share: number, reason: "button"): void;
  page(dir: -1 | 1, reason: "button"): void;
  beginGesture(): void;
  endGesture(): void;
}

export const HOLD_DELAY_MS = 300; // a press held this long slides; a shorter one is a click (one window)
export const START_SPEED = 0.25; // windows per second when the slide starts
export const TOP_SPEED = 2; // windows per second once it has eased up
export const EASE_MS = 1200; // from the start speed to the top speed
export const STEP_EVERY_MS = 450; // with reduced motion: a window per step

/** Windows per second, `ms` after the slide started: smoothly from START_SPEED to TOP_SPEED over EASE_MS. */
export function holdSpeed(ms: number): number {
  const t = Math.min(Math.max(ms / EASE_MS, 0), 1);
  return START_SPEED + (TOP_SPEED - START_SPEED) * t * t * (3 - 2 * t);
}

export interface Clock {
  now(): number;
  frame(cb: () => void): number;
  cancelFrame(id: number): void;
  every(ms: number, cb: () => void): number;
  stopEvery(id: number): void;
}

/** Starts sliding `chart` the way `dir` points; returns the function that stops it. It also stops by itself at the
 *  edge of the picked range. */
export function startSlide(chart: Slidable, dir: -1 | 1, clock: Clock, reducedMotion: boolean): () => void {
  const atEdge = () => (dir < 0 ? chart.window.start <= chart.extent.start : chart.window.end >= chart.extent.end);
  let stopped = false, frameId = 0, timerId = 0;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    clock.cancelFrame(frameId);
    clock.stopEvery(timerId);
    chart.endGesture();
  };
  chart.beginGesture();
  if (reducedMotion) {
    chart.page(dir, "button");
    timerId = clock.every(STEP_EVERY_MS, () => { if (atEdge()) stop(); else chart.page(dir, "button"); });
    return stop;
  }
  const t0 = clock.now();
  let last = t0;
  const tick = () => {
    if (stopped) return;
    if (atEdge()) { stop(); return; }
    const t = clock.now(), dt = (t - last) / 1000;
    last = t;
    if (dt > 0) chart.pan(dir * holdSpeed(t - t0) * Math.min(dt, 0.1), "button"); // a long frame doesn't jump
    frameId = clock.frame(tick);
  };
  frameId = clock.frame(tick);
  return stop;
}

/** The browser's clock. */
export const browserClock: Clock = {
  now: () => performance.now(),
  frame: (cb) => requestAnimationFrame(cb),
  cancelFrame: (id) => cancelAnimationFrame(id),
  every: (ms, cb) => window.setInterval(cb, ms),
  stopEvery: (id) => window.clearInterval(id),
};
