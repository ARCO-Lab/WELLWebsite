// This file defines the CreekMetrics component for displaying metric cards for creek sampling sites.
// It supports horizontal scrolling, site/metric filtering, and dynamic value display.

import React, { useRef, useState, useEffect, useMemo } from "react";
import { Bug, Biohazard, Cloudy, FlaskConical, Zap, Atom, Flame, Leaf } from "lucide-react";
import { Card, CardContent } from "@/components/animations/card";
import { SAMPLING_FILTER_CONFIG, SAMPLING_METRICS } from "@/components/config/filters";

// Define the structure for our metric configurations
interface MetricConfig {
  label: string;
  key: string; // Matches measurement_type from the API
  icon: React.ElementType;
  color: string;
}

// Map each sampling metric to its configuration
const metricMap: MetricConfig[] = [
  { label: "E. coli", key: "E. coli", icon: Bug, color: "text-mcmaster-maroon" },
  { label: "Total coliform", key: "Total coliform", icon: Biohazard, color: "text-mcmaster-gold" },
  { label: "Turbidity", key: "Turbidity", icon: Cloudy, color: "text-mcmaster-grey" },
  { label: "pH", key: "pH", icon: FlaskConical, color: "text-primary" },
  { label: "Conductivity", key: "Conductivity", icon: Zap, color: "text-mcmaster-maroon" },
  { label: "Chloride", key: "Chloride", icon: Atom, color: "text-mcmaster-gold" },
  { label: "Total phosphorus", key: "Total phosphorus", icon: Flame, color: "text-mcmaster-grey" },
  { label: "Soluble reactive phosphorus", key: "Soluble reactive phosphorus", icon: Flame, color: "text-primary" },
  { label: "Total nitrogen", key: "Total nitrogen", icon: Leaf, color: "text-mcmaster-maroon" },
  { label: "Nitrate nitrogen", key: "Nitrate nitrogen", icon: Leaf, color: "text-mcmaster-gold" },
  { label: "Ammonia nitrogen", key: "Ammonia nitrogen", icon: Leaf, color: "text-mcmaster-grey" },
];

interface CreekMetricsProps {
  creekKey: keyof typeof SAMPLING_FILTER_CONFIG;
  subFilters: string[];
  metrics?: any[];
  loading?: boolean;
}

const CreekMetrics: React.FC<CreekMetricsProps> = ({
  creekKey,
  subFilters,
  metrics: allData = [],
  loading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [scrollPosition, setScrollPosition] = useState(0);

  const metricCombinations = [];
  const creekConfig = SAMPLING_FILTER_CONFIG[creekKey];


  // --- Start: Corrected Logic ---

  // 1. Directly filter the metricMap based on subFilters.
  // This is the pattern from QualityMetrics.tsx.
  // If no metrics are in subFilters, this will correctly be an empty array.
  const metricsToDisplay = metricMap.filter(m => subFilters.includes(m.label));

  // 2. Determine which sites to show for this creek. Default to ALL if no site filter is present.
  // This is the pattern from CreekGraph.tsx.
  let selectedSitesForCreek: { id: string; name: string }[] = [];
  const allSitesForCreek = Object.entries(creekConfig.sites).map(([id, name]) => ({ id, name }));
  const siteFilters = subFilters.filter(f => !SAMPLING_METRICS.includes(f));

  if (siteFilters.includes("All Sites") || siteFilters.length === 0) {
    selectedSitesForCreek = allSitesForCreek;
  } else {
    selectedSitesForCreek = allSitesForCreek.filter(site => siteFilters.includes(site.id));
  }

  // --- End: Corrected Logic ---

  // 3. Create the card combinations for the selected sites and metrics.
  // This will now only create combinations if metricsToDisplay has items.
  for (const site of selectedSitesForCreek) {
    for (const metric of metricsToDisplay) {
      metricCombinations.push({
        ...metric,
        siteName: site.name,
        siteId: site.id,
        creekKey: creekKey,
        combinedKey: `${creekKey}-${site.id}-${metric.key}`
      });
    }
  }

  const infiniteCombinations = metricCombinations.length > 0 ? [...metricCombinations, ...metricCombinations, ...metricCombinations] : [];

  // useEffect hook for mouse wheel scrolling, aligned with QualityMetrics
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = (e: WheelEvent) => {
      // Only scroll if the component is paused (hovered)
      if (!isPaused) return;
      
      e.preventDefault();
      setScrollPosition(prev => {
        // Use e.deltaX for horizontal scroll, multiplied for sensitivity
        const newPos = prev + e.deltaX * 0.5; 
        const maxScroll = metricCombinations.length * 272;
        return Math.max(0, Math.min(newPos, maxScroll));
      });
    };

    container.addEventListener('wheel', handleScroll, { passive: false });
    return () => container.removeEventListener('wheel', handleScroll);
  }, [metricCombinations.length, isPaused]);

  if (loading) {
    return (
      <div className="space-y-3">
        <h4 className="font-poppins font-semibold text-sm text-primary">{creekConfig.label} Metrics</h4>
        <div className="h-16 bg-muted/20 rounded animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h4 className="font-poppins font-semibold text-sm text-primary">{creekConfig.label} Metrics</h4>
      {metricCombinations.length > 0 && (
        <div 
          ref={containerRef}
          className="relative overflow-hidden"
          onMouseEnter={() => setIsPaused(true)}
          // Reset scroll position on mouse leave
          onMouseLeave={() => {
            setIsPaused(false);
            setScrollPosition(0);
          }}
        >
          <div 
            className={`flex space-x-3 ${isPaused ? '' : 'animate-scroll'}`}
            style={{
              transform: `translateX(-${scrollPosition}px)`,
              width: `${metricCombinations.length * 272}px`
            }}
          >
            {infiniteCombinations.map((item, index) => {
              const Icon = item.icon;
              const match = allData.find(
                (d) =>
                  d.measurement_type === item.key &&
                  String(d.site_id) === item.siteId
              );
              const value = match?.value?.toFixed(2) ?? "--";
              const unit = match?.unit ?? "";
              
              return (
                <Card 
                  key={`${item.combinedKey}-${index}`} 
                  className="min-w-[260px] border border-input-border hover:shadow-sm transition-all duration-200 shrink-0"
                >
                  <CardContent className="p-3 relative">
                    <div className="absolute top-0 left-9">
                      <span className="mcmaster-notes text-primary text-xs">{item.siteName}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Icon className={`h-4 w-4 ${item.color}`} />
                        <span className="mcmaster-body font-medium text-sm relative top-1">{item.label}</span>
                      </div>
                      <div className="text-right">
                        <span className="font-poppins font-semibold text-lg text-primary">
                          {value}
                        </span>
                        <span className="mcmaster-notes text-muted ml-1 text-xs">{unit}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default CreekMetrics;