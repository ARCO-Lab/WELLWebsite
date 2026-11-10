// A sidebar panel that stays in view while the page scrolls (large screens only) and is always shown in full.
// If it fits in the window it sticks to the top; if it's taller (every filter group open on a laptop), it scrolls
// along with the page until its bottom is in view and sticks there, so the dates and Download are never cut off
// and the panel never needs a scrollbar of its own.

import React, { useEffect, useRef, useState } from "react";

const MARGIN_PX = 24;

const StickyPanel: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = "", children }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(MARGIN_PX);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setTop(Math.min(MARGIN_PX, window.innerHeight - el.offsetHeight - MARGIN_PX));
    update();
    const observer = new ResizeObserver(update); // groups opening and closing change the height
    observer.observe(el);
    window.addEventListener("resize", update);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  return (
    <div ref={ref} className={`lg:sticky ${className}`} style={{ top }}>
      {children}
    </div>
  );
};

export default StickyPanel;
