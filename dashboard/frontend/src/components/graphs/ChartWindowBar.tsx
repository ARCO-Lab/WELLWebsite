// The bar above the sensor charts: which time window they show and at what resolution, with buttons to zoom in
// (halve the window), move it (half its width at a time), widen it, or go back to the picked days. It stays mounted
// with the charts, and buttons that can't act are marked aria-disabled instead of disabled, so keyboard focus is
// never dropped (e.g. on Reset, or on ◀ at the start). It also holds the one screen-reader announcement for all
// charts' loading and error states.

import React from "react";
import { ChevronLeft, ChevronRight, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useChartView } from "@/hooks/useChartSeries";
import {
  TIME_ZONE, bucketLabel, shiftWindow, zoomInWindow, zoomOutWindow, type Range,
} from "@/utils/chartWindow";

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
  + "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary "
  + "aria-disabled:cursor-not-allowed aria-disabled:opacity-40 aria-disabled:hover:bg-white";

// A button that stays focusable when it can't act (aria-disabled), so focus isn't lost when it stops applying.
const BarButton: React.FC<{
  label: string; title?: string; off: boolean; onPress: () => void; className?: string; children: React.ReactNode;
}> = ({ label, title, off, onPress, className = "", children }) => (
  <button type="button" className={`${buttonClass} ${className}`} aria-label={label} title={title}
    aria-disabled={off || undefined} onClick={() => { if (!off) onPress(); }}>
    {children}
  </button>
);

const ChartWindowBar: React.FC = () => {
  const view = useChartView();
  const { viewWindow, range, zoomTo } = view;

  const status = view.loading ? "Loading chart data…"
    : view.error ? view.error.message
    : view.detailLoading ? "Loading more detail…"
    : view.detailError ? "Couldn't load more detail; the charts show averages."
    : "";
  const live = <p className="sr-only" role="status" aria-live="polite">{status}</p>;

  if (!range || !view.overview) return live;
  const w = viewWindow ?? range;
  const zoomed = viewWindow !== null;
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
        {/* ◀ label ▶ stay on one row; on phones the zoom buttons (icons only there; each has an aria-label) go below */}
        <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
          <BarButton label="Show earlier" title="Earlier" className="shrink-0" off={w.start <= range.start}
            onPress={() => zoomTo(shiftWindow(w, range, -1))}>
            <ChevronLeft aria-hidden className="h-4 w-4" />
          </BarButton>
          <p className="flex min-w-0 flex-1 items-center gap-2 text-xs text-gray-800 sm:flex-none sm:text-sm">
            <span>{windowLabel(w)}<span className="text-gray-600">{resolution}</span></span>
            {view.detailLoading && (
              <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 motion-safe:animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" />
            )}
          </p>
          <BarButton label="Show later" title="Later" className="shrink-0" off={w.end >= range.end}
            onPress={() => zoomTo(shiftWindow(w, range, 1))}>
            <ChevronRight aria-hidden className="h-4 w-4" />
          </BarButton>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <BarButton label="Zoom in: show half as much time" title="Zoom in" off={w.end - w.start <= 3600 * 1000}
            onPress={() => zoomTo(zoomInWindow(w, range))}>
            <ZoomIn aria-hidden className="h-4 w-4" />
            <span className="hidden sm:inline">Zoom in</span>
          </BarButton>
          <BarButton label="Zoom out: show twice as much time" title="Zoom out" off={!zoomed}
            onPress={() => zoomTo(zoomOutWindow(w, range))}>
            <ZoomOut aria-hidden className="h-4 w-4" />
            <span className="hidden sm:inline">Zoom out</span>
          </BarButton>
          <BarButton label="Reset zoom: show all the picked days" title="Reset" off={!zoomed} onPress={() => zoomTo(null)}>
            <RotateCcw aria-hidden className="h-4 w-4" />
            <span className="hidden sm:inline">Reset</span>
          </BarButton>
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
        {!zoomed && (
          <p className="w-full text-xs text-muted">
            <span className="pointer-coarse:hidden">Or drag across a chart to zoom in.</span>
            <span className="hidden pointer-coarse:inline">Or pinch a chart to zoom in.</span>
          </p>
        )}
      </div>
    </>
  );
};

export default ChartWindowBar;
