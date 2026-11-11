// A sidebar panel that stays in view while the page scrolls (large screens only) and is always shown in full.
// If it fits in the window it sticks to the top. If it's taller (every filter group open on a laptop), it moves
// with the page as you scroll, either way, until its bottom (or top) is in view, and sticks there; so the dates and
// Download are never cut off and the panel never needs a scrollbar of its own. Its offset only changes as the page
// scrolls: when a group opens, the panel grows downwards and stays where it is, under the pointer.

import React, { useEffect, useRef } from "react";

const MARGIN_PX = 24;

const StickyPanel: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = "", children }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let top = MARGIN_PX;
    let lastY = window.scrollY;
    // top ranges from MARGIN_PX (top in view) down to where the bottom is MARGIN_PX above the window's bottom
    const clamp = () => {
      const lowest = Math.min(MARGIN_PX, window.innerHeight - el.offsetHeight - MARGIN_PX);
      top = Math.min(MARGIN_PX, Math.max(lowest, top));
      el.style.top = `${top}px`;
    };
    const onScroll = () => {
      top -= window.scrollY - lastY; // follow the page
      lastY = window.scrollY;
      clamp();
    };
    clamp();
    const observer = new ResizeObserver(clamp); // a group closing can leave the panel too far up
    observer.observe(el);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", clamp);
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", clamp);
    };
  }, []);

  return (
    <div ref={ref} className={`lg:sticky ${className}`}>
      {children}
    </div>
  );
};

export default StickyPanel;
