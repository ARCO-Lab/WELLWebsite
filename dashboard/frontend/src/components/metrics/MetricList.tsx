// Shared layout for the Latest Data panels (weather, water quality, loggers, creek sampling sites).
//
// A titled group of readings: rows of "icon · name … value unit", optionally grouped under a logger or site
// name, laid out in as many columns as fit (one in the narrow panel, several in the modal). Old readings say
// when they were taken, so a value from last night or from last year doesn't look current.

import React from "react";

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
  // Readings older than this are marked "last reading …"; null for grab samples, which are always old.
  staleAfterHours?: number | null;
  timeLabel?: string; // e.g. "as of" or "sampled"
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

// Formats a site wall-clock time: "11:30 AM" today, "Nov 8, 9:10 PM" this year, "Oct 6, 2025" before that.
export function formatSiteTime(value: string | null | undefined): string | null {
  const ms = value ? wallClockMs(value) : null;
  if (ms == null) return null;
  const now = new Date(siteNowMs());
  const at = new Date(ms);
  const sameDay = at.getUTCFullYear() === now.getUTCFullYear() && at.getUTCMonth() === now.getUTCMonth()
    && at.getUTCDate() === now.getUTCDate();
  const options: Intl.DateTimeFormatOptions = sameDay
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

// --- components ---

function Row({ row, staleAfterHours }: { row: MetricRow; staleAfterHours: number | null }) {
  const Icon = row.icon;
  const value = row.reading?.value;
  const hasValue = typeof value === "number" && Number.isFinite(value);
  const shown = hasValue ? (row.format ? row.format(value) : { value: formatNumber(value), unit: row.reading?.unit ?? undefined }) : null;
  const age = hoursOld(row.reading?.recorded_at);
  const stale = hasValue && staleAfterHours != null && age != null && age > staleAfterHours;

  return (
    <li className="flex min-w-0 items-start justify-between gap-3 py-1.5">
      <div className="min-w-0">
        <p className="flex min-w-0 items-center gap-1.5 text-sm text-foreground">
          <Icon aria-hidden className={`h-3.5 w-3.5 shrink-0 ${row.color}`} />
          <span className="truncate" title={row.fullLabel ?? row.label}>{row.label}</span>
        </p>
        {stale && (
          <p className="pl-5 text-[11px] leading-snug text-amber-800">
            Last reading {formatSiteTime(row.reading?.recorded_at)}
          </p>
        )}
      </div>
      <p className="shrink-0 whitespace-nowrap text-right leading-tight">
        {shown ? (
          <>
            <span className={`font-poppins text-base font-semibold tabular-nums ${stale ? "text-muted" : "text-primary"}`}>
              {shown.value}
            </span>
            {shown.unit && <span className="ml-1 text-xs text-muted">{shown.unit}</span>}
          </>
        ) : (
          <span className="text-xs text-muted">No data</span>
        )}
      </p>
    </li>
  );
}

const MetricGroup: React.FC<MetricGroupProps> = ({
  title,
  sections,
  loading = false,
  staleAfterHours = 3,
  timeLabel = "as of",
  emptyHint = "Pick metrics under Filters to see their latest values.",
}) => {
  // The newest reading in the group, for the "as of …" line.
  const newest = sections
    .flatMap((s) => s.rows.map((r) => r.reading?.recorded_at))
    .filter((t): t is string => !!t)
    .sort()
    .pop();
  const rowCount = sections.reduce((n, s) => n + s.rows.length, 0);

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="font-poppins text-sm font-semibold text-primary">{title}</h3>
        {!loading && newest && (
          <p className="text-[11px] text-muted">{timeLabel} {formatSiteTime(newest)}</p>
        )}
      </div>
      {loading ? (
        <div className="space-y-2" aria-hidden>
          {[0, 1, 2].map((i) => <div key={i} className="h-5 animate-pulse rounded bg-black/5" />)}
        </div>
      ) : rowCount === 0 ? (
        <p className="text-xs text-muted">{emptyHint}</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(13.5rem,1fr))] gap-x-6 gap-y-1">
          {sections.filter((s) => s.rows.length > 0).map((section) => (
            <section key={section.key} className="min-w-0">
              {section.title && <h4 className="pt-1 text-xs font-semibold text-foreground/80">{section.title}</h4>}
              <ul className="divide-y divide-input-border">
                {section.rows.map((row) => <Row key={row.key} row={row} staleAfterHours={staleAfterHours} />)}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
};

export default MetricGroup;
