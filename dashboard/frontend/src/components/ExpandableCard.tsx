// A card that opens a larger view (the dashboard modal): a click anywhere on it opens it, and a corner button
// does the same for keyboard and screen-reader users, so the card's content stays readable as normal content.
// Clicks on the content's own controls (a chart legend, a chart's buttons and accessibility buttons, any button,
// link or input) do their own job and don't open the modal, and neither does a drag (e.g. drag-to-zoom on a chart).
// The button sits in a row of its own above the content ("band", the default), so it never covers a chart, its
// legend or Highcharts' own buttons; "corner" floats it in the top-right corner, for cards that keep that corner
// free themselves (the Latest Data strips reserve it with right padding). With openOnClick={false} (the chart cards,
// where a click or tap belongs to the charts: tooltips, focus, dragging), only the button opens it.

import React, { useRef } from "react";
import { Maximize2 } from "lucide-react";

interface ExpandableCardProps {
  label: string; // what opens, e.g. "Weather graph"
  onOpen: () => void;
  className?: string;
  style?: React.CSSProperties;
  placement?: "band" | "corner";
  openOnClick?: boolean; // false: only the button opens the larger view
  children: React.ReactNode;
}

// Highcharts' accessibility layer puts its proxy buttons in .highcharts-a11y-proxy-container-before/-after;
// .highcharts-button covers its SVG buttons (e.g. "Reset zoom").
const OWN_CONTROLS =
  ".highcharts-legend, .highcharts-button, [class*='highcharts-a11y-proxy'], button, a, input, select, textarea";

// A pointer that moved further than this between press and release was dragging, not clicking.
const DRAG_PX = 5;

const ExpandButton = React.forwardRef<HTMLButtonElement, { label: string; onOpen: () => void; corner: boolean }>(
  ({ label, onOpen, corner }, ref) => (
    // 28 px to look at; on phones 40 px to tap (the ::after, kept small to stay clear of its neighbours)
    <button
      ref={ref}
      type="button"
      onClick={(e) => { e.stopPropagation(); onOpen(); }}
      className={`${corner ? "absolute right-1.5 top-1.5 z-10" : "relative"} grid h-7 w-7 place-items-center max-sm:after:absolute max-sm:after:-inset-1.5 max-sm:after:content-[''] rounded-md text-muted opacity-60 transition-opacity hover:bg-black/5 hover:text-primary hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary group-hover:opacity-100`}
      aria-label={`Open ${label} in a larger view`}
      title="Open in a larger view"
    >
      <Maximize2 aria-hidden className="h-3.5 w-3.5" />
    </button>
  ),
);
ExpandButton.displayName = "ExpandButton";

const ExpandableCard: React.FC<ExpandableCardProps> = ({ label, onOpen, className = "", style, placement = "band", openOnClick = true, children }) => {
  const pressedAt = useRef<{ x: number; y: number } | null>(null);
  const button = useRef<HTMLButtonElement>(null);
  const expandButton = <ExpandButton ref={button} label={label} onOpen={onOpen} corner={placement === "corner"} />;
  return (
    <div
      onPointerDown={(e) => { pressedAt.current = { x: e.clientX, y: e.clientY }; }}
      onClick={(e) => {
        if (!openOnClick) return;
        const start = pressedAt.current;
        pressedAt.current = null;
        if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) > DRAG_PX) return;
        const target = e.target as Element | null;
        if (target?.closest?.(OWN_CONTROLS)) return;
        // The corner button takes focus first, so that is where focus returns when the larger view closes.
        button.current?.focus({ preventScroll: true });
        onOpen();
      }}
      className={`mcmaster-card group relative ${openOnClick ? "mcmaster-card-interactive cursor-pointer" : ""} ${className}`} style={style}>
      {placement === "band" ? (
        // In the card's top padding plus a short row: the content starts 20 px lower than it would without it
        <div className="-mr-2.5 -mt-3 mb-1 flex justify-end">{expandButton}</div>
      ) : expandButton}
      {children}
    </div>
  );
};

export default ExpandableCard;
