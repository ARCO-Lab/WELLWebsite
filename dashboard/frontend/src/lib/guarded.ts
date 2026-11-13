// A callback that reports what it throws instead of letting it escape. Chart data and redraws run in controller
// subscriptions (from animation frames and fetch replies), outside React's rendering, so an exception there was only
// logged and left the chart half drawn. MetricChart hands it to its card's error boundary instead.

export function guarded<A extends unknown[]>(fn: (...args: A) => void, report: (err: unknown) => void): (...args: A) => void {
  return (...args: A) => {
    try {
      fn(...args);
    } catch (err) {
      report(err);
    }
  };
}
