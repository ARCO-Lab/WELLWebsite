// Which part of the range bar a press lands on. The window is the shaded stretch between pixels a and b of the bar;
// its handles sit on its two ends. A press near a handle resizes the window from that end, one inside it slides it,
// one elsewhere on the track centres it there. However narrow the window (two hours of a year is under a pixel), the
// middle MIN_GRAB_PX of it always slides it, and the handle zones move outward to make room:
// - narrower than MIN_GRAB_PX: the bar draws it MIN_GRAB_PX wide around its middle with the handles just outside
//   (MetricChart wraps Stock's navigator drawing to match), and presses follow that drawing;
// - narrower than MIN_GRAB_PX plus two handles: the handles only take presses on their outer side.
// Before, both handles covered a narrow window, so every press resized it, and a drag one way did nothing.

export const HANDLE_PX = 14; // how near a handle a press must land to take it
export const MIN_GRAB_PX = 20; // the narrowest the window's slide area gets

export type BarPart = 'start' | 'end' | 'window' | 'track';

export function barPart(x: number, a: number, b: number, handle = HANDLE_PX, minGrab = MIN_GRAB_PX): BarPart {
  if (b - a < minGrab) {
    const mid = (a + b) / 2, half = minGrab / 2;
    if (Math.abs(x - mid) <= half) return 'window';
    if (x < mid && mid - x <= half + handle) return 'start';
    if (x > mid && x - mid <= half + handle) return 'end';
    return 'track';
  }
  const inner = Math.max(0, Math.min(handle, (b - a - minGrab) / 2)); // how far into the window a handle reaches
  if (x >= a - handle && x <= a + inner) return 'start';
  if (x >= b - inner && x <= b + handle) return 'end';
  return x > a && x < b ? 'window' : 'track';
}
