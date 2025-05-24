import { useEffect, useState } from "react";
import { setFlagsFromString } from "v8";

// CHANGE ONCE LOGGER API WORKING


interface LoggerMetric {
  label: string;
  key: string; // this will match sensor_measurement_type
}

const metrics: LoggerMetric[] = [
  { label: "Air Temperature", key: "Temperature" },
  { label: "Relative Humidity", key: "RH" },
  { label: "Wind Speed", key: "Wind Speed" },
  { label: "Gust Speed", key: "Gust Speed" },
  { label: "Wind Direction", key: "Wind Direction" },
  { label: "Dew Point", key: "Dew Point" },
  { label: "Rainfall", key: "Rain" },
  { label: "Pressure", key: "Pressure" },
  { label: "Solar Radiation", key: "Solar Radiation" },
  { label: "Water Content", key: "Water Content" },
];

const LoggerMetrics = () => {
  const [loggerData, setLoggerData] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/weather")
      .then((res) => res.json())
      .then((json) => setLoggerData(json))
      .catch((err) => console.error("Failed to fetch weather data:", err));
  }, []);

  return (
    <div className="p-4 overflow-y-auto bg-white rounded shadow max-h-25">
      <h2 className="mb-2 text-lg font-semibold">Water Logger Metrics</h2>
      <ul className="space-y-1 text-sm text-gray-800">
        {metrics.map(({ label, key }) => {
          const entry = loggerData.find((d) => d.sensor_measurement_type === key);
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

export default LoggerMetrics;
