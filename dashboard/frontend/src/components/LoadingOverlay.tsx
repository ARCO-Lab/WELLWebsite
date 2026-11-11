// Loading placeholders for the dashboard's map and graph cards, shown while their code (MapLibre, Highcharts) or
// the base map is still downloading, so a slow connection shows "Loading…" in a box of the final size instead of
// a blank area or a card that collapses and then jumps open.

import React from "react";

/** A "Loading…" note over its positioned parent; it lets clicks through to whatever is underneath. */
export function LoadingOverlay({ label = "Loading…", className = "" }: { label?: string; className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 z-[5] grid place-items-center ${className}`}>
      <p role="status" className="flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-sm text-gray-700 shadow-sm">
        <span aria-hidden="true" className="h-4 w-4 rounded-full border-2 border-gray-300 border-t-gray-700 motion-safe:animate-spin" />
        {label}
      </p>
    </div>
  );
}

/** A graph card's body: while `waiting` (the chart code isn't loaded yet) it keeps a chart's height and says
 *  "Loading…"; the chart itself is aria-busy while `busy` (that, or the data still loading). The "Loading…" note
 *  sits outside the busy element: screen readers may hold back updates inside one. The chart draws its own
 *  "Loading data…" once its code is there. */
export function GraphFrame({ busy, waiting, children }: { busy: boolean; waiting: boolean; children: React.ReactNode }) {
  return (
    <div className={`relative ${waiting ? "min-h-[20rem] sm:min-h-[26rem]" : ""}`}>
      <div aria-busy={busy || undefined}>{children}</div>
      {waiting && <LoadingOverlay label="Loading graph…" className="rounded bg-gray-50/80" />}
    </div>
  );
}
