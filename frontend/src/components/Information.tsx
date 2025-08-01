import React, { useRef, useState, useEffect } from "react";
import { Info } from "lucide-react";
import { Button } from "@/components/animations/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/animations/popover";

const infoMap: Record<number, string> = {
  1: "The filter panel lets you toggle sensor categories, select individual metrics, and adjust date ranges. You can also download filtered data as a CSV. Clicking a group or marker updates the filters in real time.",
  2: "The map displays sensor locations: blue droplets for water loggers, a pink droplet for the water quality sensor, and a gray cloud for the weather station. Hovering on a marker shows more information. Click markers to toggle sensors on or off.",
  3: "This section shows the most recent readings for your selected metrics. Click any metric to view it in a fullscreen modal for detailed analysis, including an AI-generated summary of alerts, key findings, and correlations.",
  4: "Graph visualizations update based on your filters and date range. Click a graph to open it fullscreen, revealing detailed X and Y axes. The modal also provides an AI-generated analysis of trends, correlations, and anomalies in the data.",
  5: "The AI Analysis section provides insights into your data. It generates summaries of trends, anomalies, and correlations based on the selected metrics and date range. You can switch between recent and all-time analyses.",
};

interface InformationProps {
  id: number;
}

const Information: React.FC<InformationProps> = ({ id }) => {
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