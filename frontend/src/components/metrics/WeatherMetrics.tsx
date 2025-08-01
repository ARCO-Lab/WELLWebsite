import React, { useRef, useState, useEffect } from "react";
import { Thermometer, Droplets, Wind, CloudRain, Compass, Snowflake, Gauge, Sun, Waves, TreePine, Navigation } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/animations/card";

interface WeatherMetric {
  label: string;
  key: string; 
}

const metrics: WeatherMetric[] = [
  { label: "Air Temperature", key: "Air Temperature" },
  { label: "Relative Humidity", key: "Relative Humidity" },
  { label: "Wind Speed", key: "Wind Speed" },
  { label: "Gust Speed", key: "Gust Speed" },
  { label: "Wind Direction", key: "Wind Direction" },
  { label: "Dew Point", key: "Dew Point" },
  { label: "Rainfall", key: "Rain" },
  { label: "Pressure", key: "Pressure" },
  { label: "Solar Radiation", key: "Solar Radiation" },
  { label: "Water Content", key: "Water Content" },
  { label: "Soil Temperature", key: "Soil Temperature" },
];

const WeatherMetrics = ({
  activeKeys,
  activeGroups,
  metrics: weatherData = [],
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
    { label: "Air Temperature", key: "Air Temperature", icon: Thermometer, color: "text-mcmaster-maroon" },
    { label: "Relative Humidity", key: "Relative Humidity", icon: Droplets, color: "text-mcmaster-gold" },
    { label: "Wind Speed", key: "Wind Speed", icon: Wind, color: "text-mcmaster-grey" },
    { label: "Gust Speed", key: "Gust Speed", icon: Navigation, color: "text-primary" },
    { label: "Wind Direction", key: "Wind Direction", icon: Compass, color: "text-mcmaster-maroon" },
    { label: "Dew Point", key: "Dew Point", icon: Snowflake, color: "text-mcmaster-gold" },
    { label: "Rainfall", key: "Rain", icon: CloudRain, color: "text-mcmaster-grey" },
    { label: "Pressure", key: "Pressure", icon: Gauge, color: "text-primary" },
    { label: "Solar Radiation", key: "Solar Radiation", icon: Sun, color: "text-mcmaster-maroon" },
    { label: "Water Content", key: "Water Content", icon: Waves, color: "text-mcmaster-gold" },
    { label: "Soil Temperature", key: "Soil Temperature", icon: TreePine, color: "text-mcmaster-grey" }
  ];

  const filteredMetrics = metricMap.filter(({ label }) => 
    activeKeys.includes(label)
  );

  // Create infinite scrolling effect by duplicating metrics
  const infiniteMetrics = [...filteredMetrics, ...filteredMetrics, ...filteredMetrics];

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = (e: WheelEvent) => {
      e.preventDefault();
      setScrollPosition(prev => {
        const newPos = prev + e.deltaX * 0.5;
        // Adjust width calculation for new card size
        return Math.max(0, Math.min(newPos, filteredMetrics.length * 240));
      });
    };

    container.addEventListener('wheel', handleScroll, { passive: false });
    return () => container.removeEventListener('wheel', handleScroll);
  }, [filteredMetrics.length]);

  return (
    <div className="space-y-3">
      <h4 className="font-poppins font-semibold text-sm text-primary">Weather Station</h4>
      <div 
        ref={containerRef}
        className="relative overflow-hidden"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div 
          className={`flex space-x-3 ${isPaused ? '' : 'animate-scroll'}`}
          style={{
            // Adjust width calculation for new card size
            width: `${filteredMetrics.length * 240}px`,
            transform: `translateX(-${scrollPosition}px)`
          }}
        >
          {infiniteMetrics.map((item, index) => {

            const Icon = item.icon;
            const entry = weatherData.find((d) => d.measurement_type === item.key);
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
                      <span className="mcmaster-body font-medium text-sm">{item.label}</span>
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

export default WeatherMetrics;