// Collapsible.tsx
import React, { useRef, useEffect, useState } from "react";

interface CollapsibleProps {
  open: boolean;
  children: React.ReactNode;
  duration?: number;
}

const Collapsible: React.FC<CollapsibleProps> = ({ open, children, duration = 300 }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(open ? "auto" : "0px");

  useEffect(() => {
    if (open) {
      const scrollHeight = ref.current?.scrollHeight || 0;
      setHeight(scrollHeight + "px");
      // After transition, set to auto for dynamic content
      const timeout = setTimeout(() => setHeight("auto"), duration);
      return () => clearTimeout(timeout);
    } else {
      // Set to current height, then to 0 for transition
      if (ref.current) {
        setHeight(ref.current.scrollHeight + "px");
        setTimeout(() => setHeight("0px"), 10);
      } else {
        setHeight("0px");
      }
    }
  }, [open, duration]);

  return (
    <div
      style={{
        overflow: "hidden",
        transition: `max-height ${duration}ms cubic-bezier(0.4, 0, 0.2, 1)`,
        maxHeight: height,
      }}
      ref={ref}
    >
      {children}
    </div>
  );
};

export default Collapsible;