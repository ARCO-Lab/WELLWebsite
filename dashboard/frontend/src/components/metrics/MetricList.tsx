// Shared layout for the Latest Data panels (weather, water quality, loggers, creek sampling sites).
//
// A titled group of metric tiles ("icon · name   value unit"). In the panel they run as a slowly scrolling strip
// (one row per group, so the panel stays compact); in the modal they wrap so every tile is visible at once.
// Each tile is as wide as its content, so a name never runs into its value. Old readings say when they were
// taken, so a value from last night or from last year doesn't look current.

import React, { useEffect, useRef, useState } from "react";

export interface Reading {
  value?: number | null;
  unit?: string | null;
  recorded_at?: string | null; // wall-clock time at the site (America/Toronto), without an offset
}

export interface MetricRow {
  key: string;
  label: string;
  fullLabel?: string; // shown as a tooltip when the label is shortened
  icon: React.ElementType;
  color: string; // Tailwind text colour class for the icon
  reading?: Reading | null;
  format?: (value: number) => { value: string; unit?: string };
}

export interface MetricSection {
  key: string;
  title?: string; // logger or site name; omitted when the group has a single station
  rows: MetricRow[];
}

interface MetricGroupProps {
  title: string;
  sections: MetricSection[];
  loading?: boolean;
  layout?: "ticker" | "wrap"; // ticker in the panel, wrap in the modal
  // Readings older than this are marked "last reading …"; null for grab samples, which are always old.
  staleAfterHours?: number | null;
  timeLabel?: string; // e.g. "as of" or "sampled"
  dateOnly?: boolean; // grab samples carry a date, not a meaningful time
  emptyHint?: string;
}

// --- time helpers (recorded_at is site wall-clock time; "now" is converted to the same clock) ---

const SITE_TIME_ZONE = "America/Toronto";

function wallClockMs(value: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(value);
  if (!m) return null;
  const [y, mo, d, h, mi, s] = m.slice(1).map((x) => Number(x ?? 0));
  return Date.UTC(y, mo - 1, d, h, mi, s || 0);
}

function siteNowMs(): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: SITE_TIME_ZONE, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(new Date());
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
}

// Formats a site wall-clock time: "11:30 AM" today, "Nov 8, 9:10 PM" this year, "Oct 6, 2025" before that
// (or always the date, for samples).
export function formatSiteTime(value: string | null | undefined, dateOnly = false): string | null {
  const ms = value ? wallClockMs(value) : null;
  if (ms == null) return null;
  const now = new Date(siteNowMs());
  const at = new Date(ms);
  const sameDay = at.getUTCFullYear() === now.getUTCFullYear() && at.getUTCMonth() === now.getUTCMonth()
    && at.getUTCDate() === now.getUTCDate();
  const options: Intl.DateTimeFormatOptions = dateOnly
    ? { month: "short", day: "numeric", year: "numeric" }
    : sameDay
      ? { hour: "numeric", minute: "2-digit" }
      : at.getUTCFullYear() === now.getUTCFullYear()
        ? { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
        : { month: "short", day: "numeric", year: "numeric" };
  return new Intl.DateTimeFormat("en-CA", { ...options, timeZone: "UTC" }).format(at);
}

function hoursOld(value: string | null | undefined): number | null {
  const ms = value ? wallClockMs(value) : null;
  return ms == null ? null : (siteNowMs() - ms) / 3_600_000;
}

const numberFormat = new Intl.NumberFormat("en-CA", { maximumFractionDigits: 2 });

export const formatNumber = (value: number) => numberFormat.format(value);

// 16-point compass name for a wind direction in degrees.
export function compassPoint(degrees: number): string {
  const names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  return names[Math.round((((degrees % 360) + 360) % 360) / 22.5) % 16];
}

// --- tiles ---

// In the strip a tile is one line, as wide as its content. In the modal (wrap) it is at most as wide as the modal,
// and a long name wraps instead of being cut off on a narrow phone.
function Tile({ row, caption, staleAfterHours, wrap = false }: { row: MetricRow; caption?: string; staleAfterHours: number | null; wrap?: boolean }) {
  const Icon = row.icon;
  const value = row.reading?.value;
  const hasValue = typeof value === "number" && Number.isFinite(value);
  const shown = hasValue ? (row.format ? row.format(value) : { value: formatNumber(value), unit: row.reading?.unit ?? undefined }) : null;
  const age = hoursOld(row.reading?.recorded_at);
  const stale = hasValue && staleAfterHours != null && age != null && age > staleAfterHours;

  return (
    <div className={`flex items-center gap-3 rounded-lg border border-input-border bg-card px-3 py-2 ${wrap ? "min-w-0 max-w-full" : "shrink-0 whitespace-nowrap"}`}>
      <Icon aria-hidden className={`h-4 w-4 shrink-0 ${row.color}`} />
      <div className={`leading-tight ${wrap ? "min-w-0 break-words" : ""}`}>
        {caption && <p className="text-[11px] font-semibold text-primary/80">{caption}</p>}
        <p className="text-sm text-foreground" title={row.fullLabel ?? row.label}>{row.label}</p>
        {stale && <p className="text-[11px] text-amber-800">Last reading {formatSiteTime(row.reading?.recorded_at)}</p>}
      </div>
      <p className="ml-auto shrink-0 whitespace-nowrap pl-1 leading-tight">
        {shown ? (
          <>
            <span className={`font-poppins text-lg font-semibold tabular-nums ${stale ? "text-muted" : "text-primary"}`}>
              {shown.value}
            </span>
            {shown.unit && <span className="ml-1 text-xs text-muted">{shown.unit}</span>}
          </>
        ) : (
          <span className="text-xs text-muted">No data</span>
        )}
      </p>
    </div>
  );
}

const SPEED_PX_PER_S = 30;

// The scrolling strip. It scrolls by moving scrollLeft, so the strip is also an ordinary horizontal scroller:
// a trackpad, Shift + wheel, a swipe or the arrow keys move it by hand, while a normal wheel still scrolls the page.
// When the tiles don't all fit, a second copy follows the first and the strip wraps by exactly one copy's width,
// so the loop is seamless. It pauses where it is while a mouse is over it or it has keyboard focus, and for 2.5 s
// after a touch (a tap is not a hover, and focus from a click or a closing modal doesn't pause it). It doesn't
// auto-scroll at all for people who ask their system for reduced motion.
function Ticker({ label, children }: { label: string; children: React.ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null);
  const firstCopy = useRef<HTMLDivElement>(null);
  const paused = useRef(false);
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [overflowing, setOverflowing] = useState(false);

  // Only scroll (and add the second copy) when the tiles don't fit.
  useEffect(() => {
    const el = scroller.current;
    const copy = firstCopy.current;
    if (!el || !copy) return;
    const check = () => setOverflowing(copy.offsetWidth > el.clientWidth + 1);
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    observer.observe(copy);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = scroller.current;
    const copy = firstCopy.current;
    if (!el || !copy || !overflowing) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    let last = performance.now();
    let position = el.scrollLeft;
    const gap = parseFloat(getComputedStyle(copy.parentElement as Element).columnGap) || 0;

    const step = (now: number) => {
      const copyWidth = copy.offsetWidth + gap; // where the second copy starts
      const elapsed = Math.min(now - last, 100);
      last = now;
      if (paused.current || reduceMotion) {
        position = el.scrollLeft; // follow any scrolling by hand
      } else {
        position += (SPEED_PX_PER_S * elapsed) / 1000;
      }
      if (position >= copyWidth) position -= copyWidth; // seamless wrap, by hand or automatic
      if (Math.abs(el.scrollLeft - position) >= 0.5) el.scrollLeft = position;
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [overflowing]);

  useEffect(() => () => { if (resumeTimer.current) clearTimeout(resumeTimer.current); }, []);

  const pause = () => {
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
    paused.current = true;
  };
  const resume = (delay = 0) => {
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
    resumeTimer.current = setTimeout(() => { paused.current = false; }, delay);
  };

  return (
    <div
      ref={scroller}
      role="region"
      aria-label={label}
      tabIndex={0}
      onPointerEnter={(e) => { if (e.pointerType === "mouse") pause(); }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") resume(); }}
      onFocus={(e) => { if (e.currentTarget.matches(":focus-visible")) pause(); }}
      onBlur={() => resume()}
      onTouchStart={pause}
      onTouchEnd={() => resume(2500)}
      className={`overflow-x-auto overscroll-x-contain rounded-md [scrollbar-width:none] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary [&::-webkit-scrollbar]:hidden ${
        overflowing ? "[mask-image:linear-gradient(to_right,transparent,black_1rem,black_calc(100%-1rem),transparent)]" : ""
      }`}
    >
      <div className="flex w-max gap-3">
        <div ref={firstCopy} className="flex gap-3">{children}</div>
        {overflowing && <div className="flex gap-3" aria-hidden>{children}</div>}
      </div>
    </div>
  );
}

const MetricGroup: React.FC<MetricGroupProps> = ({
  title,
  sections,
  loading = false,
  layout = "ticker",
  staleAfterHours = 3,
  timeLabel = "as of",
  dateOnly = false,
  emptyHint = "Pick metrics under Filters to see their latest values.",
}) => {
  // The newest reading in the group, for the "as of …" line.
  const newest = sections
    .flatMap((s) => s.rows.map((r) => r.reading?.recorded_at))
    .filter((t): t is string => !!t)
    .sort()
    .pop();
  const tiles = sections.flatMap((section) =>
    section.rows.map((row) => (
      <Tile key={row.key} row={row} caption={section.title} staleAfterHours={staleAfterHours} wrap={layout === "wrap"} />
    ))
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="font-poppins text-sm font-semibold text-primary">{title}</h3>
        {!loading && newest && (
          <p className="text-[11px] text-muted">{timeLabel} {formatSiteTime(newest, dateOnly)}</p>
        )}
      </div>
      {loading ? (
        <div className="h-14 animate-pulse rounded-lg bg-black/5" aria-hidden />
      ) : tiles.length === 0 ? (
        <p className="text-xs text-muted">{emptyHint}</p>
      ) : layout === "wrap" ? (
        <div className="flex flex-wrap gap-3">{tiles}</div>
      ) : (
        <Ticker label={`${title}, scrolling`}>{tiles}</Ticker>
      )}
    </div>
  );
};

export default MetricGroup;
