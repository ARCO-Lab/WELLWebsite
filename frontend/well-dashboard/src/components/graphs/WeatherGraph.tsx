import { useEffect, useState } from "react";

const WeatherGraph = () => {
  const [weatherData, setWeatherData] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/weather")  // or "/api/weather" if using a Next.js proxy route
      .then((res) => res.json())
      .then((json) => {
        setWeatherData(json);
      })
      .catch((err) => console.error("Failed to fetch weather data:", err));
  }, []);

  return (
    <div className="p-4 bg-white rounded shadow">
      <h2 className="mb-2 text-lg font-semibold">Weather Station</h2>
      <pre className="overflow-x-auto text-sm text-gray-700 whitespace-pre-wrap">
        {JSON.stringify(weatherData, null, 2)}
      </pre>
    </div>
  );
};

export default WeatherGraph;
