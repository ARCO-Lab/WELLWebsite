import React, { useRef, useState, useEffect, useMemo } from "react";
import { Waves, Thermometer } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/animations/card";

interface LoggerMetric {
  label: string;
  key: string; // Matches measurement_type
}

const metricOptions: LoggerMetric[] = [
  { label: "Water Level", key: "Water Level" },
  { label: "Water Temperature", key: "Water Temperature" },
];

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
  const [scrollPosition, setScrollPosition] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const loggerData = useMemo(() => {
    return allData.filter((d) => d.group_type === "Logger");
  }, [allData]);

  // Determine which loggers to show
  const showAllLoggers = activeKeys.includes("All Loggers");
  const visibleLoggers = showAllLoggers
    ? ["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"]
    : activeKeys
        .filter((k) => k.startsWith("Logger"))
        .sort((a, b) => {
          const numA = parseInt(a.split(" ")[1]);
          const numB = parseInt(b.split(" ")[1]);
          return numA - numB;
        });

  // Determine which metrics to show
  const visibleMetrics = metricOptions.filter(({ label }) => activeKeys.includes(label));

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
    { label: "Water Level", key: "Water Level", icon: Waves, color: "text-mcmaster-maroon" },
    { label: "Water Temperature", key: "Water Temperature", icon: Thermometer, color: "text-mcmaster-gold" },
  ];

  // Create combinations of logger + metric
  const loggerMetricCombinations = [];
  for (const logger of visibleLoggers) {
    for (const metric of metricMap.filter(m => visibleMetrics.some(vm => vm.label === m.label))) {
      loggerMetricCombinations.push({
        ...metric,
        logger: logger,
        combinedKey: `${logger}-${metric.key}`
      });
    }
  }

  // Create infinite scrolling effect by duplicating combinations
  const infiniteCombinations = [...loggerMetricCombinations, ...loggerMetricCombinations, ...loggerMetricCombinations];

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = (e: WheelEvent) => {
      e.preventDefault();
      setScrollPosition(prev => {
        const newPos = prev + e.deltaX * 0.5;
        return Math.max(0, Math.min(newPos, loggerMetricCombinations.length * 280));
      });
    };

    container.addEventListener('wheel', handleScroll, { passive: false });
    return () => container.removeEventListener('wheel', handleScroll);
  }, [loggerMetricCombinations.length]);

  return (
    <div className="space-y-3">
      <h4 className="font-poppins font-semibold text-sm text-primary">Water Logger Metrics</h4>
      <div 
        ref={containerRef}
        className="relative overflow-hidden"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div 
          className={`flex space-x-3 ${isPaused ? '' : 'animate-scroll'}`}
          style={{
            width: `${loggerMetricCombinations.length * 280}px`,
            transform: `translateX(-${scrollPosition}px)`
          }}
        >
          {infiniteCombinations.map((item, index) => {
            const Icon = item.icon;
            const match = loggerData.find(
              (d) =>
                d.measurement_type === item.key &&
                d.group_type === "Logger" &&
                d.group_name === item.logger
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
                    <span className="mcmaster-notes text-primary text-xs">{item.logger}</span>
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
    </div>
  );
};

export default LoggerMetrics;