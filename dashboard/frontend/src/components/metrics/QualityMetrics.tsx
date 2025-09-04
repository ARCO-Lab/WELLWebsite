// This file defines the QualityMetrics component for displaying metric cards for water quality data.
// It supports horizontal scrolling, metric filtering, and dynamic value display.

import React, { useRef, useState, useEffect } from "react";
import { Beaker, Eye, Waves, Zap, Droplets, FlaskConical, Activity, Thermometer } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/animations/card";

interface QualityMetric {
  label: string;
  key: string;
}

const metrics: QualityMetric[] = [
  { label: "Total Dissolved Solids (TDS)", key: "TDS" },
  { label: "Dissolved Oxygen (ODO)", key: "ODO" },
  { label: "Dissolved Oxygen Saturation (ODOSat)", key: "ODOSat" },
  { label: "Total Suspended Solids (TSS)", key: "TSS" },
  // Add more as needed
];

const QualityMetrics = ({
  activeKeys,
  activeGroups,
  metrics: qualityData = [],
  loading = false,
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
  metrics?: any[];
  loading?: boolean;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollPosition, setScrollPosition] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-16 bg-muted/20 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  const metricMap = [
    { label: "Total Dissolved Solids (TDS)", key: "TDS", icon: Beaker, color: "text-mcmaster-maroon" },
    { label: "Dissolved Oxygen (ODO)", key: "ODO", icon: Waves, color: "text-mcmaster-gold" },
    { label: "Dissolved Oxygen Saturation (ODOSat)", key: "ODOSat", icon: Eye, color: "text-mcmaster-grey" },
    { label: "Total Suspended Solids (TSS)", key: "TSS", icon: Zap, color: "text-primary" },
    { label: "Turbidity", key: "Turbidity", icon: Droplets, color: "text-mcmaster-maroon" },
    { label: "Salinity", key: "Salinity", icon: FlaskConical, color: "text-mcmaster-gold" },
    { label: "Conductivity", key: "Conductivity", icon: Activity, color: "text-mcmaster-grey" },
    { label: "Water Temperature", key: "Water Temperature", icon: Thermometer, color: "text-primary" }
  ];

  const filteredMetrics = metricMap.filter(({ label }) => 
    activeKeys.includes(label)
  );

  // Create infinite scrolling effect by duplicating metrics
  const infiniteMetrics = [...filteredMetrics, ...filteredMetrics, ...filteredMetrics];

  useEffect(() => { // Error Necessary
    // Attach horizontal scroll handler for mouse wheel
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = (e: WheelEvent) => {
      e.preventDefault();
      setScrollPosition(prev => {
        const newPos = prev + e.deltaX * 0.5;
        return Math.max(0, Math.min(newPos, filteredMetrics.length * 280));
      });
    };

    container.addEventListener('wheel', handleScroll, { passive: false });
    return () => container.removeEventListener('wheel', handleScroll);
  }, [filteredMetrics.length]);

  return (
    <div className="space-y-3">
      <h4 className="font-poppins font-semibold text-sm text-primary">Water Quality Metrics</h4>
      <div 
        ref={containerRef}
        className="relative overflow-hidden"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div 
          className={`flex space-x-3 ${isPaused ? '' : 'animate-scroll'}`}
          style={{
            width: `${filteredMetrics.length * 280}px`,
            transform: `translateX(-${scrollPosition}px)`
          }}
        >
          {infiniteMetrics.map((item, index) => {
            const Icon = item.icon;
            const entry = qualityData.find(
              (d) => d.measurement_type === item.key && d.group_type === 'Quality'
            );
            const value = entry?.value?.toFixed(2) ?? "--";
            const unit = entry?.unit ?? "";
            
            return (
              <Card 
                key={`${item.key}-${index}`} 
                className="min-w-[260px] border border-input-border hover:shadow-sm transition-all duration-200 shrink-0"
              >
                <CardContent className="p-3">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center space-x-2">
                      <Icon className={`h-4 w-4 ${item.color}`} />
                      <span className="mcmaster-body font-medium text-sm">{item.label.split(' (')[0]}</span>
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
    </div>
  );
};

export default QualityMetrics;