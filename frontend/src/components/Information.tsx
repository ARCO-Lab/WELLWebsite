import React, { useRef, useState, useEffect } from "react";
import Image from "next/image";

const infoMap: Record<number, string> = {
  1: "The filter panel lets you toggle sensor categories, individual parameters, and different date ranges with the option to download the data with filters and dates applied as a CSV.",
  2: "The map displays sensor locations. Blue Droplets are water loggers. The pink droplet is a water quality sensor, and the gray cloud represents a weather station.",
  3: "This section shows the most recent sensor readings for selected metrics.",
  4: "Graph visualizations appear here based on selected filters and time range.",
};

const Information: React.FC<{ id: number }> = ({ id }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [alignRight, setAlignRight] = useState(true);

  useEffect(() => {
    const handlePosition = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        // If the icon is in the right half of the viewport, align right, else align left
        setAlignRight(rect.left > window.innerWidth / 2);
      }
    };
    handlePosition();
    window.addEventListener("resize", handlePosition);
    return () => window.removeEventListener("resize", handlePosition);
  }, []);

  return (
    <div className="relative group w-fit shrink-0" ref={containerRef}>
      <Image
        src="/icons/infoIcon.png"
        alt="Info"
        width={18}
        height={18}
        className="cursor-pointer"
      />
      <div
        className={`absolute z-10 hidden w-64 p-2 mt-1 text-sm text-white bg-gray-700 rounded group-hover:block
          ${alignRight ? "right-0" : "left-0"}`}
      >
        {infoMap[id] || "No description available."}
      </div>
    </div>
  );
};

export default Information;