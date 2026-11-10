// A card that opens a larger view (the dashboard modal): a click anywhere on it opens it, and a corner button
// does the same for keyboard and screen-reader users, so the card's content stays readable as normal content.

import React from "react";
import { Maximize2 } from "lucide-react";

interface ExpandableCardProps {
  label: string; // what opens, e.g. "Weather graph"
  onOpen: () => void;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

const ExpandableCard: React.FC<ExpandableCardProps> = ({ label, onOpen, className = "", style, children }) => (
  <div onClick={onOpen} className={`mcmaster-card mcmaster-card-interactive group relative cursor-pointer ${className}`} style={style}>
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

export default ExpandableCard;
