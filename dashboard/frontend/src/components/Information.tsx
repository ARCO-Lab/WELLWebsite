// This file defines the Information component for displaying contextual help tooltips using a popover.
// It shows an info icon that, when clicked, displays a description based on the provided id.

import React, { useRef, useState, useEffect } from "react";
import { Info } from "lucide-react";
import { Button } from "@/components/animations/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/animations/popover";


const infoMap: Record<number, string> = {
  // --- Sensor Tab ---
  1: "Filter sensor data by category (Loggers, Weather, Quality), select individual metrics, and adjust date ranges. Your selections here and on the map are synchronized.",
  2: "The map displays sensor locations. Blue droplets are water loggers, the pink droplet is the water quality sensor, and the gray cloud is the weather station. Click markers to toggle them.",
  3: "This section shows the most recent readings for your selected sensor metrics. Click any metric to view it in a fullscreen modal for detailed analysis.",
  4: "Graph visualizations for sensor data update based on your filters. Click a graph to open it fullscreen, revealing an AI-generated analysis of trends, correlations, and anomalies.",
  5: "The AI generates insights from your selected sensor data. It summarizes trends, anomalies, and correlations, helping you understand the relationships between different sensor readings.",

  // --- Sampling Tab ---
  6: "Filter sampling data by creek, select metrics like E. coli or pH, and choose specific sampling sites. Your selections here and on the map are synchronized.",
  7: "The map displays sampling site locations, color-coded by creek: orange for Ancaster Creek, yellow for Tiffany Creek, green for Sulphur Creek, black for Coldwater Creek, and white for Spencer’s Creek. Hover over a marker to see its name. Click markers to toggle individual sites on or off.",
  8: "This section shows the latest measurements for your selected sampling metrics and sites. Click any metric to view it in a fullscreen modal for detailed analysis.",
  9: "Graphs are grouped first by creek, then by individual sampling site. Click a graph to open it fullscreen and view an AI-generated analysis of water quality trends over time.",
  10: "The AI generates insights from your selected sampling data. It summarizes trends and potential issues based on the selected metrics, sites, and date range."
};


interface InformationProps {
  id: number;
}

const Information: React.FC<InformationProps> = ({ id }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [alignRight, setAlignRight] = useState(true);

  useEffect(() => {
    // Dynamically align the popover based on icon position in the viewport
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
    <div className="w-fit shrink-0" ref={containerRef}>
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-muted hover:text-primary transition-colors"
          >
            <Info className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent 
          className="w-64 p-3 text-sm text-white bg-gray-800 border border-gray-700 animate-in fade-in-0 zoom-in-95 duration-200"
          align={alignRight ? "end" : "start"}
          sideOffset={5}
        >
          {infoMap[id] || "No description available."}
        </PopoverContent>
      </Popover>
    </div>
  );
};

export default Information;