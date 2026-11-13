// The row above one chart: its title, the time it shows ("Oct 1 14:00 – Oct 3 02:00"), the resolution drawn
// ("6-h means"), a spinner while finer data loads, and buttons to move (◀ ▶, half the window), zoom (− +) and go back
// to the picked days (Reset). Each chart has its own; buttons that can't act are aria-disabled (not disabled), so
// keyboard focus is never dropped.

import React, { useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, Minus, Plus, RotateCcw } from "lucide-react";
import type { ChartController } from "@/lib/chartController";
import { useChartSnapshot } from "@/hooks/useChartWindow";
import { MIN_RANGE_MS, TIME_ZONE, shortBucket, type Range } from "@/utils/chartWindow";

let formatter: Intl.DateTimeFormat | null = null;
function parts(ms: number): Record<string, string> {
  formatter ??= new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE, year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const p: Record<string, string> = {};
  for (const { type, value } of formatter.formatToParts(new Date(ms))) p[type] = value;
  return p;
}

/** "Oct 1 14:00 – Oct 3 02:00", with years when the window isn't all in the year `now` is in. */
export function windowLabel(w: Range, now: number): string {
  const a = parts(w.start), b = parts(w.end), year = parts(now).year;
  const withYear = a.year !== year || b.year !== year;
  const f = (p: Record<string, string>) => `${p.month} ${p.day}${withYear ? `, ${p.year}` : ""} ${p.hour}:${p.minute}`;
  return `${f(a)} – ${f(b)}`;
}

/** "10-min readings", "6-h means", "daily totals". */
export function resolutionLabel(bucketS: number, kind: "means" | "totals"): string {
  return bucketS <= 600 ? "10-min readings" : `${shortBucket(bucketS)} ${kind}`;
}

const buttonClass =
  "inline-grid h-7 min-w-7 place-items-center rounded-md border border-gray-300 bg-white px-1.5 text-xs text-gray-800 hover:bg-gray-50 "
  + "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary max-sm:h-8 max-sm:min-w-8 "
  + "aria-disabled:cursor-not-allowed aria-disabled:opacity-40 aria-disabled:hover:bg-white";

const ToolButton: React.FC<{ label: string; title: string; off: boolean; onPress: () => void; children: React.ReactNode }> =
  ({ label, title, off, onPress, children }) => (
    <button type="button" className={buttonClass} aria-label={label} title={title} aria-disabled={off || undefined}
      onClick={() => { if (!off) onPress(); }}>
      {children}
    </button>
  );

interface Props {
  controller: ChartController;
  title: string;
  kind: "means" | "totals"; // what an averaged bucket of this chart holds
  headingLevel?: "h3" | "h4";
}

const ChartToolbar: React.FC<Props> = ({ controller, title, kind, headingLevel = "h4" }) => {
  const snap = useChartSnapshot(controller);
  // The dates follow every frame of a gesture straight from the controller (React re-renders this toolbar only when
  // the gesture ends: see ChartController.updateSnapshot)
  const labelRef = useRef<HTMLSpanElement>(null);
  useEffect(() => controller.onFrame((win) => {
    if (labelRef.current) labelRef.current.textContent = windowLabel(win, controller.extent.end);
  }), [controller]);
  const w = snap.window, ext = snap.extent, def = controller.defaultWindow;
  const atDefault = Math.abs(w.start - def.start) < 60_000 && Math.abs(w.end - def.end) < 60_000;
  const Heading = headingLevel;
  // Announced once the window comes to rest after the user moved it, not on every frame of a drag, and not when new
  // picked days move every chart at once (twenty announcements of the same dates; the date pickers say it already)
  const status = snap.error ? `${title}: ${snap.error.message}`
    : snap.settledByUser ? `${title}: ${windowLabel(snap.settled, ext.end)}, ${resolutionLabel(snap.wantedBucket, kind)}` : "";
  return (
    <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
      <Heading className="text-sm font-semibold text-gray-900">{title}</Heading>
      <p className="flex min-w-0 items-center gap-1.5 text-[11px] text-gray-600">
        <span ref={labelRef} data-testid="chart-window-label">{windowLabel(w, ext.end)}</span>
        {snap.shownBucket !== null && (
          <span className="whitespace-nowrap rounded bg-gray-100 px-1.5 py-0.5 text-gray-700" data-testid="chart-resolution">
            {resolutionLabel(snap.shownBucket, kind)}
          </span>
        )}
        {/* Animated only while shown: twenty idle spinning (if invisible) layers made the browser re-layer the page every frame */}
        <span aria-hidden="true" className={`h-3 w-3 shrink-0 rounded-full border-2 border-gray-300 border-t-gray-700 ${snap.loading ? "motion-safe:animate-spin" : "invisible"}`} />
      </p>
      <span className="sr-only" role="status" aria-live="polite">{status}</span>
      <div className="ml-auto flex gap-1" role="group" aria-label={`${title}: time window`}>
        <ToolButton label="Show the time just before this window" title="Earlier" off={w.start <= ext.start} onPress={() => controller.page(-1)}>
          <ChevronLeft aria-hidden className="h-3.5 w-3.5" />
        </ToolButton>
        <ToolButton label="Zoom out: show twice as much time" title="Zoom out" off={w.end - w.start >= ext.end - ext.start}
          onPress={() => controller.zoom(2)}>
          <Minus aria-hidden className="h-3.5 w-3.5" />
        </ToolButton>
        <ToolButton label="Zoom in: show half as much time" title="Zoom in" off={w.end - w.start <= MIN_RANGE_MS}
          onPress={() => controller.zoom(0.5)}>
          <Plus aria-hidden className="h-3.5 w-3.5" />
        </ToolButton>
        <ToolButton label="Show the time just after this window" title="Later" off={w.end >= ext.end} onPress={() => controller.page(1)}>
          <ChevronRight aria-hidden className="h-3.5 w-3.5" />
        </ToolButton>
        <ToolButton label="Reset: show the picked days" title="Reset" off={atDefault} onPress={() => controller.reset()}>
          <span className="flex items-center gap-1 px-0.5"><RotateCcw aria-hidden className="h-3 w-3" /><span className="max-sm:hidden">Reset</span></span>
        </ToolButton>
      </div>
    </div>
  );
};

export default ChartToolbar;
