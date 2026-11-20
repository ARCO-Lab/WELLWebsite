// Loading placeholders for the dashboard's map and graph cards, shown while their code (MapLibre, Highcharts) or
// the base map is still downloading, so a slow connection shows "Loading…" in a box of the final size instead of
// a blank area or a card that collapses and then jumps open.

import React, { useEffect, useRef } from "react";
import { useMountTurn } from "@/lib/mountTurn";

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
 *  "Loading data…" once its code is there.
 *
 *  The card's charts are built a moment after the card appears, one card at a time (lib/mountTurn.ts), so the tap
 *  or page load that added the card is painted first; until its turn the card waits like this too. */
export function GraphFrame({ busy, waiting, children }: { busy: boolean; waiting: boolean; children: React.ReactNode }) {
  const turn = useMountTurn(!waiting);
  const wait = waiting || !turn;
  return (
    <div className={`relative ${wait ? "min-h-[20rem] sm:min-h-[26rem]" : ""}`}>
      <div aria-busy={busy || !turn || undefined}>{turn && children}</div>
      {wait && <LoadingOverlay label="Loading graph…" className="rounded bg-gray-50/80" />}
    </div>
  );
}

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** The larger view's graphs: built once the dialog itself has been painted (lib/mountTurn.ts), so it opens at once.
 *  Until then a box of about a chart's height says "Loading…".
 *
 *  A dialog puts focus on its first control when it opens. With the graphs not there yet, that is its Close button,
 *  so once they are, focus moves on to their first control (where it went before), unless it has been moved since. */
export function AfterPaint({ children }: { children: React.ReactNode }) {
  const turn = useMountTurn();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!turn || !el) return;
    const active = document.activeElement;
    const dialog = el.closest('[role="dialog"]');
    if (!dialog || !active || !dialog.contains(active) || el.contains(active)) return;
    el.querySelector<HTMLElement>(FOCUSABLE)?.focus({ preventScroll: true });
  }, [turn]);
  if (turn) return <div ref={box}>{children}</div>;
  return (
    <div className="relative min-h-[20rem] sm:min-h-[min(70vh,36rem)]" aria-busy="true">
      <LoadingOverlay label="Loading graph…" className="rounded bg-gray-50/80" />
    </div>
  );
}
