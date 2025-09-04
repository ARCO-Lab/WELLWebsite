// This file defines the LoggerMetrics component for displaying metric cards for selected water loggers.
// It supports horizontal scrolling, logger/metric filtering, and dynamic value display.

import React, { useRef, useState, useEffect, useMemo } from "react";
import { Waves, Thermometer } from "lucide-react";
import { Card, CardContent } from "@/components/animations/card";
import { SENSOR_FILTER_CONFIG } from "@/components/config/filters";

// Define metric display properties - matching CreekMetrics pattern
const metricDisplayMap = {
  "Water Surface Elevation": { label: "Surface Elevation", icon: Waves, color: "text-mcmaster-maroon" },
  "Water Temperature": { label: "Water Temperature", icon: Thermometer, color: "text-mcmaster-gold" },
};

const LoggerMetrics = ({
  activeKeys,
  activeGroups,
  metrics: allData = [],
  loading = false,
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
  metrics?: any[];
  loading?: boolean;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [scrollPosition, setScrollPosition] = useState(0);

  const loggerConfig = SENSOR_FILTER_CONFIG.gauges;
  const allLoggerIds = Object.keys(loggerConfig.sites);
  const allMetrics = loggerConfig.metrics;

  // 1. Filter metrics to display based on activeKeys - MATCH CreekMetrics logic
  const metricsToDisplay = useMemo(() => {
    return allMetrics.filter(metric => activeKeys.includes(metric));
  }, [activeKeys, allMetrics]);

  // 2. Determine which loggers to show - MATCH CreekMetrics logic (no fallback)
  const visibleLoggerIds = useMemo(() => {
    if (activeKeys.includes("All Loggers")) {
      return allLoggerIds;
    }
    
    // Only return explicitly selected loggers, no fallback
    const selected = activeKeys.filter(key => allLoggerIds.includes(key));
    return selected.sort();
  }, [activeKeys, allLoggerIds]);

  // 3. Create combinations of logger + metric for display
  const loggerMetricCombinations = useMemo(() => {
    const combinations = [];
    
    // Only create combinations if we have both loggers AND metrics selected
    for (const loggerId of visibleLoggerIds) {
      const loggerName = loggerConfig.sites[loggerId as keyof typeof loggerConfig.sites];
      for (const metricKey of metricsToDisplay) {
        const displayInfo = metricDisplayMap[metricKey as keyof typeof metricDisplayMap];
        if (displayInfo) {
          combinations.push({
            loggerId: loggerId,
            loggerName: loggerName,
            metricKey: metricKey,
            ...displayInfo,
            combinedKey: `${loggerId}-${metricKey}`
          });
        }
      }
    }
    return combinations;
  }, [visibleLoggerIds, metricsToDisplay, loggerConfig.sites]);

  // Effect for manual scrolling on hover - MATCH CreekMetrics pattern
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = (e: WheelEvent) => {
      if (!isPaused) return;
      
      e.preventDefault();
      setScrollPosition(prev => {
        const newPos = prev + e.deltaX * 0.5; 
        const maxScroll = loggerMetricCombinations.length * 272;
        return Math.max(0, Math.min(newPos, maxScroll));
      });
    };

    container.addEventListener('wheel', handleScroll, { passive: false });
    return () => container.removeEventListener('wheel', handleScroll);
  }, [loggerMetricCombinations.length, isPaused]);

  if (loading) {
    return (
      <div className="space-y-3">
        <h4 className="font-poppins font-semibold text-sm text-primary">Water Logger Metrics</h4>
        <div className="h-24 bg-muted/20 rounded animate-pulse" />
      </div>
    );
  }

  const infiniteCombinations = loggerMetricCombinations.length > 0 ? [...loggerMetricCombinations, ...loggerMetricCombinations, ...loggerMetricCombinations] : [];

  return (
    <div className="space-y-3">
      <h4 className="font-poppins font-semibold text-sm text-primary">Water Logger Metrics</h4>
      {loggerMetricCombinations.length > 0 && (
        <div 
          ref={containerRef}
          className="relative overflow-hidden"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => {
            setIsPaused(false);
            setScrollPosition(0);
          }}
        >
          <div 
            className={`flex space-x-3 ${isPaused ? '' : 'animate-scroll'}`}
            style={{
              transform: `translateX(-${scrollPosition}px)`,
              width: `${loggerMetricCombinations.length * 272}px`
            }}
          >
            {infiniteCombinations.map((item, index) => {
              const Icon = item.icon;
              // FIX: Add a check for group_type to ensure we only get data from loggers.
              const match = allData.find(
                (d) =>
                  String(d.station_id) === item.loggerId &&
                  d.measurement_type === item.metricKey &&
                  d.group_type === 'Logger'
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
                      <span className="mcmaster-notes text-primary text-xs">{item.loggerName}</span>
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

export default LoggerMetrics;