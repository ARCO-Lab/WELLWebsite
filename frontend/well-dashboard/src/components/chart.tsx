import { useEffect, useState } from "react";

const WeatherChart = () => {
  const [weatherData, setWeatherData] = useState<any[]>([]);

  useEffect(() => {
    fetch("http://localhost:3000/api/weather")  // or "/api/weather" if using a Next.js proxy route
      .then((res) => res.json())
      .then((json) => {
        setWeatherData(json);
      })
      .catch((err) => console.error("Failed to fetch weather data:", err));
  }, []);

  return (
    <div className="bg-white p-4 rounded shadow">
      <h2 className="text-lg font-semibold mb-2">Raw Weather Data</h2>
      <pre className="text-sm text-gray-700 whitespace-pre-wrap overflow-x-auto">
        {JSON.stringify(weatherData, null, 2)}
      </pre>
    </div>
  );
};

export default WeatherChart;
