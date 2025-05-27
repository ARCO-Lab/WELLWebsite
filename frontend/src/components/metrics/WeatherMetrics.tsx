import { useEffect, useState } from "react";

interface WeatherMetric {
  label: string;
  key: string; // this will match sensor_measurement_type
}

const metrics: WeatherMetric[] = [
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

const WeatherMetrics = ({ activeKeys }: { activeKeys: string[] }) => {
  const [weatherData, setWeatherData] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/weather")
      .then((res) => res.json())
      .then((json) => setWeatherData(json))
      .catch((err) => console.error("Failed to fetch weather data:", err));
  }, []);

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow ">
      <h2 className="mb-2 text-lg font-semibold text-black">Weather Metrics</h2>
      <ul className="space-y-1 text-sm text-gray-800">
        {metrics
            .filter(({ label }) => activeKeys.includes(label))
            .map(({ label, key }) => {
          const entry = weatherData.find((d) => d.sensor_measurement_type === key);
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
