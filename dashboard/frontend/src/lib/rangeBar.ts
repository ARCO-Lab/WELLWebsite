// Which part of the range bar a press lands on. The window is the shaded stretch between pixels a and b of the bar;
// its handles sit on its two ends. A press near a handle resizes the window from that end, one inside it slides it,
// one elsewhere on the track centres it there. However narrow the window (two hours of a year is under a pixel), the
// middle MIN_GRAB_PX of it always slides it, and the handle zones move outward to make room:
// - narrower than MIN_GRAB_PX: the bar draws it MIN_GRAB_PX wide around its middle with the handles just outside
//   (MetricChart wraps Stock's navigator drawing to match), and presses follow that drawing. At the bar's ends it is
//   moved inward far enough that both handles stay on the bar (a window at the very end, where a hold-slide stops and
//   the latest data is, can still be resized from either side);
// - narrower than MIN_GRAB_PX plus two handles: the handles only take presses on their outer side.
// Before, both handles covered a narrow window, so every press resized it, and a drag one way did nothing.

export const HANDLE_PX = 14; // how near a handle a press must land to take it
export const MIN_GRAB_PX = 20; // the narrowest the window's slide area gets

export type BarPart = 'start' | 'end' | 'window' | 'track';

/** The stretch drawn (and grabbed) for a window from `a` to `b` on a bar from `lo` to `hi`: at least MIN_GRAB_PX wide
 *  around its middle, moved inward so that it and a handle's width on each side stay on the bar. */
export function grabSpan(a: number, b: number, lo: number, hi: number, minGrab = MIN_GRAB_PX, handle = HANDLE_PX): [number, number] {
  if (b - a >= minGrab) return [a, b];
  const room = hi - lo - 2 * handle >= minGrab ? handle : 0; // a bar too short for the handles too: just the bar
  const width = Math.min(minGrab, hi - lo);
  const start = Math.min(Math.max((a + b) / 2 - width / 2, lo + room), hi - room - width);
  return [start, start + width];
}

/** Where a narrow window's handle is drawn: just outside its grab stretch, on the bar. */
export function handleAt(index: 0 | 1, a: number, b: number, lo: number, hi: number, handle = HANDLE_PX, minGrab = MIN_GRAB_PX): number {
  const [ga, gb] = grabSpan(a, b, lo, hi, minGrab, handle);
  const x = index === 0 ? ga - handle / 2 : gb + handle / 2;
  return Math.min(Math.max(x, lo), hi);
}

/** The part a press at `x` takes; `lo` and `hi` are the bar's ends (all in the same pixels). */
export function barPart(x: number, a: number, b: number, lo = -Infinity, hi = Infinity, handle = HANDLE_PX, minGrab = MIN_GRAB_PX): BarPart {
  if (b - a < minGrab) {
    const [ga, gb] = Number.isFinite(lo) && Number.isFinite(hi) ? grabSpan(a, b, lo, hi, minGrab, handle)
      : [(a + b) / 2 - minGrab / 2, (a + b) / 2 + minGrab / 2];
    if (x >= ga && x <= gb) return 'window';
    if (x < ga && ga - x <= handle) return 'start';
    if (x > gb && x - gb <= handle) return 'end';
    return 'track';
  }
  const inner = Math.max(0, Math.min(handle, (b - a - minGrab) / 2)); // how far into the window a handle reaches
  if (x >= a - handle && x <= a + inner) return 'start';
  if (x >= b - inner && x <= b + handle) return 'end';
  return x > a && x < b ? 'window' : 'track';
}
