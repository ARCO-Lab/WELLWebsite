import { useEffect, useState } from "react";
import useLatestMetrics from "@/hooks/useLatestMetrics";

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
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
}) => {

  const { metrics: weatherData } = useLatestMetrics();

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow ">
      <h2 className="mb-2 text-lg font-semibold text-black">Weather Metrics</h2>
      <ul className="space-y-1 text-sm text-gray-800">
        {metrics
            .filter(({ label }) => activeKeys.includes(label))
            .map(({ label, key }) => {
          const entry = weatherData.find((d) => d.measurement_type === key);
          const value = entry?.value?.toFixed(2) ?? "--";
          const unit = entry?.unit ?? "";
          return (
            <li key={key}>
              <span className="font-medium">{label}:</span> {value} {unit}
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default WeatherMetrics;
