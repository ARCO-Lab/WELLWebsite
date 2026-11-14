// Numbers the wind rose shows besides its bars (components/graphs/highcharts/WindRose.tsx), kept here so they can be
// tested without a browser.

import type { WindRoseResponse } from "../hooks/useWindRose.ts";

/** The share of readings in the slowest speed class, calm wind with no meaningful direction, in percent of all the
 *  readings; null when there are none or the slowest class doesn't start at 0. */
export function calmPercent(data: WindRoseResponse | null, speed: string): number | null {
  const rose = data?.roses[speed];
  const first = data?.speed_classes[0];
  if (!rose || !rose.total || !first || first.from !== 0) return null;
  return (rose.percent[0] ?? []).reduce((a, v) => a + v, 0);
}
