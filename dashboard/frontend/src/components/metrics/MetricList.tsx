// Shared layout for the Latest Data panels (weather, water quality, loggers, creek sampling sites).
//
// A titled group of metric tiles. In the panel each group's tiles fill its card as a strip: as many rows as the card
// has room for, columns that widen to fill the card when everything fits, and otherwise a slow, seamless scroll.
// A strip tile shows its name above its value; a name or caption too long for the strip ends in an ellipsis, but the
// value is always whole. In the modal the tiles ("icon · name   value unit") wrap so every one is visible at once.
// Old readings say when they were taken, so a value from last night or from last year doesn't look current.

import React, { useEffect, useRef, useState } from "react";
import { Clock } from "lucide-react";

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

// Whether formatSiteTime shows a clock time for this value (it shows only a date for one from an earlier year),
// so the "as of" line can name the zone, Eastern Time, next to it.
function showsClockTime(value: string | null | undefined, dateOnly = false): boolean {
  const ms = value ? wallClockMs(value) : null;
  return !dateOnly && ms != null && new Date(ms).getUTCFullYear() === new Date(siteNowMs()).getUTCFullYear();
}

// --- layout of the Latest Data panel ---

// The group cards share the panel: one card fills it, two take half each, three a third each. Beside the map (lg
// and up) the panel is a column at least as tall as the map, so the cards share its height, and a card with room
// for more than one row of tiles gets them. Below lg the panel is as wide as the page, so the cards sit side by
// side (halves from sm, thirds from md) and stack on phones. A card never gets less than its title and one row:
// with more groups than fit (five creeks), the panel grows instead.
export function latestGroupsClass(count: number): string {
  const columns = count > 3 ? "sm:grid-cols-2 md:grid-cols-3" : count === 3 ? "md:grid-cols-3" : count === 2 ? "sm:grid-cols-2" : "";
  return `grid min-w-0 grid-cols-1 gap-3 ${columns} lg:flex-1 lg:grid-cols-1 lg:auto-rows-fr`;
}

// Each group's card in the panel is a column, so the strip can take the room under the title.
export const LATEST_CARD_CLASS = "flex flex-col rounded-lg p-3";

// Shown above the groups when the latest values couldn't be fetched, so empty tiles aren't taken for "no data".
// Any values already shown are the last ones fetched, and the message says so.
export function LatestDataError({ hasValues, onRetry }: { hasValues: boolean; onRetry: () => void }) {
  return (
    <p role="alert" className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {hasValues ? "Couldn’t refresh the latest data; these are the last values fetched." : "Couldn’t load the latest data."}{" "}
      <button
        type="button"
        onClick={onRetry}
        className="font-medium underline underline-offset-2 hover:text-red-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        Retry
      </button>
    </p>
  );
}

// --- tiles ---

const GAP_PX = 12; // gap-3, between tiles
const FADE_PX = 16; // the strip's faded edge, 1rem
const TILE_INSET_PX = 26; // a strip tile's padding (px-3) and border, both sides

// Every tile in a strip has the same height, so the rows line up: room for the lines any tile in the group needs
// (a caption for a logger or site, the name, the value, a "last reading" note). In px, with the tile's padding. The
// caption and name lines are a little taller than the rest, so cutting them short doesn't clip their descenders.
function tileHeight(lines: { caption: boolean; stale: boolean }): number {
  return 60 + (lines.caption ? 14 : 0) + (lines.stale ? 14 : 0);
}

function shownValue(row: MetricRow) {
  const value = row.reading?.value;
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return row.format ? row.format(value) : { value: formatNumber(value), unit: row.reading?.unit ?? undefined };
}

function isStale(row: MetricRow, staleAfterHours: number | null): boolean {
  const age = hoursOld(row.reading?.recorded_at);
  return shownValue(row) != null && staleAfterHours != null && age != null && age > staleAfterHours;
}

function Value({ row, stale }: { row: MetricRow; stale: boolean }) {
  const shown = shownValue(row);
  if (!shown) return <span className="text-xs text-muted">No data</span>;
  return (
    <>
      <span className={`font-poppins text-lg font-semibold leading-6 tabular-nums ${stale ? "text-muted" : "text-primary"}`}>{shown.value}</span>
      {shown.unit && <span className="ml-1 text-xs text-muted">{shown.unit}</span>}
    </>
  );
}

// A tile in the strip: the name above its value, so a tile stays narrow enough to be seen whole in the narrow
// column beside the map. It never wraps, and tiles in one column share its width. Its caption and name are never
// wider than the strip has room for (less the fade at its edge), cut short with an ellipsis when longer (the full
// name is in the tooltip and in the modal), so a tile can be seen whole; the value is always shown in full. An old
// reading shows its time under a clock ("last reading" for screen readers), short enough for the narrow column.
function StripTile({ row, caption, stale, height }: { row: MetricRow; caption?: string; stale: boolean; height: number }) {
  const Icon = row.icon;
  return (
    <div className="flex flex-col justify-center whitespace-nowrap rounded-lg border border-input-border bg-card px-3 py-2 leading-tight" style={{ height }}>
      {caption && <p className="max-w-[var(--line-max,none)] shrink-0 truncate text-[11px] font-semibold leading-[14px] text-primary/80" title={caption}>{caption}</p>}
      <p className="flex max-w-[var(--line-max,none)] shrink-0 items-center gap-1.5 text-[13px] text-foreground" title={row.fullLabel ?? row.label}>
        <Icon aria-hidden className={`h-3.5 w-3.5 shrink-0 ${row.color}`} />
        <span className="truncate leading-[1.3]">{row.label}</span>
      </p>
      <p className="shrink-0"><Value row={row} stale={stale} /></p>
      {stale && (
        <p className="flex shrink-0 items-center gap-1 text-[11px] text-amber-800">
          <Clock aria-hidden className="h-3 w-3 shrink-0" />
          <span className="sr-only">Last reading</span>
          {formatSiteTime(row.reading?.recorded_at)}
        </p>
      )}
    </div>
  );
}

// A tile in the modal: name on the left, value on the right. It is at most as wide as the modal, and a long name
// wraps instead of being cut off on a narrow phone.
function WrapTile({ row, caption, stale }: { row: MetricRow; caption?: string; stale: boolean }) {
  const Icon = row.icon;
  return (
    <div className="flex min-w-0 max-w-full items-center gap-3 rounded-lg border border-input-border bg-card px-3 py-2">
      <Icon aria-hidden className={`h-4 w-4 shrink-0 ${row.color}`} />
      <div className="min-w-0 break-words leading-tight">
        {caption && <p className="text-[11px] font-semibold text-primary/80">{caption}</p>}
        <p className="text-sm text-foreground" title={row.fullLabel ?? row.label}>{row.label}</p>
        {stale && <p className="text-[11px] text-amber-800">Last reading {formatSiteTime(row.reading?.recorded_at)}</p>}
      </div>
      <p className="ml-auto shrink-0 whitespace-nowrap pl-1 leading-tight"><Value row={row} stale={stale} /></p>
    </div>
  );
}

const SPEED_PX_PER_S = 30;
// Keys that scroll a focused strip: pressing one pauses it, even when the focus came from a click or a closing modal.
const SCROLL_KEYS = new Set(["ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);

// Whether focus came from the keyboard. Browsers without :focus-visible (old iOS Safari) throw; pause there too.
function keyboardFocus(el: Element): boolean {
  try {
    return el.matches(":focus-visible");
  } catch {
    return true;
  }
}

// How many rows of tiles fit in a strip this tall, balanced so the last column isn't nearly empty
// (7 tiles with room for 6 rows: 4 + 3, not 6 + 1).
function rowsFor(height: number, tile: number, tiles: number): number {
  const fit = Math.max(1, Math.floor((height + GAP_PX) / (tile + GAP_PX)));
  const columns = Math.max(1, Math.ceil(tiles / fit));
  return Math.max(1, Math.ceil(tiles / columns));
}

// The scrolling strip. It fills its slot in the card: the tiles run in columns as tall as the slot has room for
// (one row in a short card, several in a tall one), and when they all fit the columns widen to fill the width
// instead of leaving it empty. It scrolls by moving scrollLeft, so it is also an ordinary horizontal scroller:
// a trackpad, Shift + wheel, a swipe or the arrow keys move it by hand, while a normal wheel still scrolls the page.
// When the tiles don't all fit, a second copy follows the first and the strip wraps by exactly one copy's width,
// so the loop is seamless. It pauses where it is while a mouse is over it or it has keyboard focus, and for 2.5 s
// after a touch. A tap is not a hover, and focus from a click or a closing modal pauses it only once a scrolling
// key is pressed. It doesn't auto-scroll at all for people who ask their system for reduced motion.
function Ticker({ label, tileHeight, children }: { label: string; tileHeight: number; children: React.ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null);
  const firstCopy = useRef<HTMLDivElement>(null);
  const paused = useRef(false);
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [overflowing, setOverflowing] = useState(false);
  const [rows, setRows] = useState(1);
  const [stripWidth, setStripWidth] = useState(0);
  const [atStart, setAtStart] = useState(true);
  const tileCount = React.Children.count(children);

  // Rows from the slot's height (set by the card, not by the tiles), and scroll (with the second copy) only when
  // the tiles don't fit across.
  useEffect(() => {
    const el = scroller.current;
    const copy = firstCopy.current;
    if (!el || !copy) return;
    const check = () => {
      setRows(rowsFor(el.clientHeight, tileHeight, tileCount));
      setStripWidth(el.clientWidth);
      setOverflowing(copy.offsetWidth > el.clientWidth + 1);
    };
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    observer.observe(copy);
    return () => observer.disconnect();
  }, [tileCount, tileHeight]);

  useEffect(() => {
    const el = scroller.current;
    const copy = firstCopy.current;
    if (!el || !copy || !overflowing) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    let last = performance.now();
    let position = el.scrollLeft;

    const step = (now: number) => {
      const copyWidth = copy.offsetWidth + GAP_PX; // where the second copy starts
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

  // Columns as wide as their widest tile, sharing out any spare width when everything fits.
  // A tile's caption and name are at most the strip's width less the fade on its right and the tile's padding and
  // border, so a tile can be seen whole. This holds whether or not the strip scrolls: tying it to the overflow check
  // would change the width that check measures, and the two could flip each other back and forth.
  const grid: React.CSSProperties & { "--line-max"?: string } = {
    ...(stripWidth > FADE_PX + TILE_INSET_PX + 40 ? { "--line-max": `${stripWidth - FADE_PX - TILE_INSET_PX}px` } : {}),
    gridTemplateRows: `repeat(${rows}, ${tileHeight}px)`,
    gridAutoFlow: "column",
    gridAutoColumns: "minmax(max-content, 1fr)",
  };

  return (
    // The strip sits over its slot, so its height comes from the card rather than from the tiles inside it.
    <div className="relative flex-1" style={{ minHeight: tileHeight }}>
      <div
        ref={scroller}
        role="region"
        aria-label={label}
        tabIndex={0}
        onPointerEnter={(e) => { if (e.pointerType === "mouse") pause(); }}
        onPointerLeave={(e) => { if (e.pointerType === "mouse") resume(); }}
        onFocus={(e) => { if (keyboardFocus(e.currentTarget)) pause(); }}
        onKeyDown={(e) => { if (SCROLL_KEYS.has(e.key)) pause(); }}
        onBlur={() => resume()}
        onScroll={(e) => setAtStart(e.currentTarget.scrollLeft < 1)}
        onTouchStart={pause}
        onTouchEnd={() => resume(2500)}
        // When the tiles don't all fit, the edges fade, so a tile cut off at the edge reads as "more this way" (also when
        // the strip stands still for reduced motion), not as a clipped card. At its start only the right edge fades, so
        // the first tile is whole.
        className={`absolute inset-0 flex items-center overflow-x-auto overflow-y-hidden overscroll-x-contain rounded-lg [scrollbar-width:none] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary [&::-webkit-scrollbar]:hidden ${
          !overflowing ? "" : atStart
            ? "[mask-image:linear-gradient(to_right,black_calc(100%-1rem),transparent)]"
            : "[mask-image:linear-gradient(to_right,transparent,black_1rem,black_calc(100%-1rem),transparent)]"
        }`}
      >
        <div className="flex min-w-full gap-3">
          <div ref={firstCopy} className={`grid gap-3 ${overflowing ? "w-max shrink-0" : "flex-1"}`} style={grid}>{children}</div>
          {overflowing && <div className="grid w-max shrink-0 gap-3" style={grid} aria-hidden>{children}</div>}
        </div>
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
  const ticker = layout === "ticker";
  const items = sections.flatMap((section) =>
    section.rows.map((row) => ({ row, caption: section.title, stale: isStale(row, staleAfterHours) }))
  );
  const height = tileHeight({ caption: items.some((t) => t.caption), stale: items.some((t) => t.stale) });
  const tiles = items.map(({ row, caption, stale }) =>
    ticker
      ? <StripTile key={row.key} row={row} caption={caption} stale={stale} height={height} />
      : <WrapTile key={row.key} row={row} caption={caption} stale={stale} />
  );

  return (
    <div className={ticker ? "flex flex-1 flex-col gap-2" : "space-y-2"}>
      {/* The time follows the title on its line, or starts the next line whole. In the panel a float keeps the first
          line clear of the card's corner button without narrowing the lines below it. */}
      <div className="flow-root leading-5">
        {ticker && <span aria-hidden className="float-right h-5 w-7" />}
        <h3 className="mr-3 inline font-poppins text-sm font-semibold text-primary">{title}</h3>
        {!loading && newest && (
          <p className="inline-block whitespace-nowrap text-[11px] text-muted">
            {timeLabel} {formatSiteTime(newest, dateOnly)}
            {showsClockTime(newest, dateOnly) && <abbr title="Eastern Time, the sites' local time" className="no-underline"> ET</abbr>}
          </p>
        )}
      </div>
      {loading ? (
        <div className="h-[60px] animate-pulse rounded-lg bg-black/5" aria-hidden />
      ) : tiles.length === 0 ? (
        <p className="text-xs text-muted">{emptyHint}</p>
      ) : ticker ? (
        <Ticker label={`${title}, scrolling`} tileHeight={height}>{tiles}</Ticker>
      ) : (
        <div className="flex flex-wrap gap-3">{tiles}</div>
      )}
    </div>
  );
};

export default MetricGroup;
