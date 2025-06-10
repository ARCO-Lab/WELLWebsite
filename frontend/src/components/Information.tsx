import React, { useRef, useState, useEffect } from "react";
import Image from "next/image";

const infoMap: Record<number, string> = {
  1: "The filter panel lets you toggle sensor categories, select individual metrics, and adjust date ranges. You can also download filtered data as a CSV. Clicking a group or marker updates the filters in real time.",
  2: "The map displays sensor locations: blue droplets for water loggers, a pink droplet for the water quality sensor, and a gray cloud for the weather station. Hovering on a marker shows more information. Click markers to toggle sensors on or off.",
  3: "This section shows the most recent readings for your selected metrics. Click any metric to view it in a fullscreen modal for detailed analysis, including an AI-generated summary of alerts, key findings, and correlations.",
  4: "Graph visualizations update based on your filters and date range. Click a graph to open it fullscreen, revealing detailed X and Y axes. The modal also provides an AI-generated analysis of trends, correlations, and anomalies in the data.",
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