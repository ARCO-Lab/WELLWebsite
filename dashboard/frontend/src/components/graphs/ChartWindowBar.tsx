// The bar above the sensor charts while they are zoomed: which time window they show and at what resolution,
// with buttons to move it (half its width at a time), widen it, or go back to the picked days. It also holds the
// one screen-reader announcement for all charts' loading and detail states, and says how to zoom when not zoomed.

import React from "react";
import { ChevronLeft, ChevronRight, RotateCcw, ZoomOut } from "lucide-react";
import { useChartView } from "@/hooks/useChartSeries";
import { TIME_ZONE, bucketLabel, shiftWindow, zoomOutWindow, type Range } from "@/utils/chartWindow";

let labelFormatter: Intl.DateTimeFormat | null = null;

/** "Apr 3 14:00", in Toronto time. */
function formatInstant(ms: number): string {
  labelFormatter ??= new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const p: Record<string, string> = {};
  for (const { type, value } of labelFormatter.formatToParts(new Date(ms))) p[type] = value;
  return `${p.month} ${p.day} ${p.hour}:${p.minute}`;
}

export function windowLabel(w: Range): string {
  return `${formatInstant(w.start)} – ${formatInstant(w.end)}`;
}

const buttonClass =
  "inline-flex h-8 items-center gap-1 rounded-md border border-gray-300 bg-white px-2 text-sm text-gray-800 hover:bg-gray-50 "
  + "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-40";

const ChartWindowBar: React.FC = () => {
  const view = useChartView();
  const { viewWindow: w, range, zoomTo } = view;

  const status = view.loading ? "Loading chart data…"
    : view.detailLoading ? "Loading more detail…"
    : view.detailError ? "Couldn't load more detail; the charts show averages."
    : "";
  const live = <p className="sr-only" role="status" aria-live="polite">{status}</p>;

  if (!w || !range) {
    if (!view.overview) return live;
    return (
      <>
        {live}
        <p className="mb-3 text-xs text-muted">
          <span className="pointer-coarse:hidden">Drag across a chart to zoom in.</span>
          <span className="hidden pointer-coarse:inline">Pinch a chart to zoom in.</span>
        </p>
      </>
    );
  }

  const resolution = view.shownBucketS ? ` · ${bucketLabel(view.shownBucketS, view.shownAggregated)}` : "";

  return (
    <>
      {live}
      <div
        role="group"
        aria-label="Chart time window"
        className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2"
        // Clicks here must not open the chart card's larger view
        onClick={(e) => e.stopPropagation()}
      >
        {/* ◀ label ▶ stay on one row; on phones the zoom buttons wrap below them */}
        <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
          <button type="button" className={`${buttonClass} shrink-0`} aria-label="Show earlier" title="Earlier"
            disabled={w.start <= range.start} onClick={() => zoomTo(shiftWindow(w, range, -1))}>
            <ChevronLeft aria-hidden className="h-4 w-4" />
          </button>
          <p className="flex min-w-0 flex-1 items-center gap-2 text-xs text-gray-800 sm:flex-none sm:text-sm">
            <span>{windowLabel(w)}<span className="text-gray-600">{resolution}</span></span>
            {view.detailLoading && (
              <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 motion-safe:animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" />
            )}
          </p>
          <button type="button" className={`${buttonClass} shrink-0`} aria-label="Show later" title="Later"
            disabled={w.end >= range.end} onClick={() => zoomTo(shiftWindow(w, range, 1))}>
            <ChevronRight aria-hidden className="h-4 w-4" />
          </button>
        </div>
        <div className="ml-auto flex gap-2">
          <button type="button" className={buttonClass} aria-label="Zoom out: show twice as much time"
            onClick={() => zoomTo(zoomOutWindow(w, range))}>
            <ZoomOut aria-hidden className="h-4 w-4" />
            Zoom out
          </button>
          <button type="button" className={buttonClass} aria-label="Reset zoom: show all the picked days"
            onClick={() => zoomTo(null)}>
            <RotateCcw aria-hidden className="h-4 w-4" />
            Reset
          </button>
        </div>
        {view.detailError && (
          <p className="w-full text-sm text-red-700">
            Couldn&apos;t load detail ·{" "}
            <button type="button" className="font-medium underline underline-offset-2 hover:text-red-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              onClick={view.retryDetail}>
              Retry
            </button>
          </p>
        )}
      </div>
    </>
  );
};

export default ChartWindowBar;
