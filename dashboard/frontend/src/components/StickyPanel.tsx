// A sidebar panel that stays in view while the page scrolls (large screens only) and is always shown in full.
// If it fits in the window it sticks to the top. If it's taller (every filter group open on a laptop), it moves
// with the page as you scroll, either way, until its bottom (or top) is in view, and sticks there; so the dates and
// Download are never cut off and the panel never needs a scrollbar of its own. Its offset only changes as the page
// scrolls: when a group opens, the panel grows downwards and stays where it is, under the pointer.
//
// Embedded in the WordPress page (lib/embed.ts), the iframe is as tall as the dashboard and never scrolls, so CSS
// sticky does nothing. There the "window" is the part of the iframe the WordPress page reports in view, and the panel
// is moved with a transform instead, never past the bottom of its column.

import React, { useEffect, useRef } from "react";
import { getEmbedView, subscribeEmbedView } from "@/lib/embed";

const MARGIN_PX = 24;

const StickyPanel: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = "", children }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const wide = window.matchMedia("(min-width: 64rem)"); // Tailwind's lg, where the panel sticks
    // The scrolled position and height of what is in view: the WordPress page's report when embedded
    const scrollY = () => getEmbedView()?.top ?? window.scrollY;
    const viewHeight = () => getEmbedView()?.height ?? window.innerHeight;
    let top = MARGIN_PX;
    let lastY = scrollY();
    // top ranges from MARGIN_PX (top in view) down to where the bottom is MARGIN_PX above the window's bottom
    const clamp = () => {
      const lowest = Math.min(MARGIN_PX, viewHeight() - el.offsetHeight - MARGIN_PX);
      top = Math.min(MARGIN_PX, Math.max(lowest, top));
      const embedView = getEmbedView();
      const column = el.parentElement;
      if (embedView && column && wide.matches) {
        // Moved down from where it sits to `top` below the part in view, within its column (whose height the
        // transform doesn't change)
        const columnTop = column.getBoundingClientRect().top + window.scrollY;
        const room = column.offsetHeight - el.offsetHeight;
        const shift = Math.max(0, Math.min(room, embedView.top + top - columnTop));
        el.style.top = "";
        // Follows the page at once (.mcmaster-card animates every property, which would make it trail behind)
        el.style.transitionProperty = "box-shadow, background-color, border-color, color";
        el.style.transform = shift > 0 ? `translateY(${Math.round(shift)}px)` : "";
      } else {
        el.style.transform = "";
        el.style.transitionProperty = "";
        el.style.top = `${top}px`;
      }
    };
    const onScroll = () => {
      const y = scrollY();
      top -= y - lastY; // follow the page
      lastY = y;
      clamp();
    };
    clamp();
    const observer = new ResizeObserver(clamp); // a group closing can leave the panel too far up
    observer.observe(el);
    if (el.parentElement) observer.observe(el.parentElement); // the column grows as graphs open
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", clamp);
    wide.addEventListener("change", clamp);
    const unsubscribe = subscribeEmbedView(onScroll);
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", clamp);
      wide.removeEventListener("change", clamp);
      unsubscribe();
    };
  }, []);

  return (
    <div ref={ref} className={`lg:sticky ${className}`}>
      {children}
    </div>
  );
};

export default StickyPanel;
