// A card that opens a larger view (the dashboard modal): a click anywhere on it opens it, and a corner button
// does the same for keyboard and screen-reader users, so the card's content stays readable as normal content.
// Clicks on the content's own controls (a chart legend, a chart's buttons and accessibility buttons, any button,
// link or input) do their own job and don't open the modal, and neither does a drag (e.g. drag-to-zoom on a chart).

import React, { useRef } from "react";
import { Maximize2 } from "lucide-react";

interface ExpandableCardProps {
  label: string; // what opens, e.g. "Weather graph"
  onOpen: () => void;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

// Highcharts' accessibility layer puts its proxy buttons in .highcharts-a11y-proxy-container-before/-after;
// .highcharts-button covers its SVG buttons (e.g. "Reset zoom").
const OWN_CONTROLS =
  ".highcharts-legend, .highcharts-button, [class*='highcharts-a11y-proxy'], button, a, input, select, textarea";

// A pointer that moved further than this between press and release was dragging, not clicking.
const DRAG_PX = 5;

const ExpandableCard: React.FC<ExpandableCardProps> = ({ label, onOpen, className = "", style, children }) => {
  const pressedAt = useRef<{ x: number; y: number } | null>(null);
  return (
    <div
      onPointerDown={(e) => { pressedAt.current = { x: e.clientX, y: e.clientY }; }}
      onClick={(e) => {
        const start = pressedAt.current;
        pressedAt.current = null;
        if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) > DRAG_PX) return;
        const target = e.target as Element | null;
        if (target?.closest?.(OWN_CONTROLS)) return;
        onOpen();
      }}
      className={`mcmaster-card mcmaster-card-interactive group relative cursor-pointer ${className}`} style={style}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onOpen(); }}
        className="absolute right-1.5 top-1.5 z-10 grid h-7 w-7 place-items-center rounded-md text-muted opacity-60 transition-opacity hover:bg-black/5 hover:text-primary hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary group-hover:opacity-100"
        aria-label={`Open ${label} in a larger view`}
        title="Open in a larger view"
      >
        <Maximize2 aria-hidden className="h-3.5 w-3.5" />
      </button>
      {children}
    </div>
  );
};

export default ExpandableCard;
