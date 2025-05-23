import React, { useState } from "react";

const FilterPanel = () => {
  const [open, setOpen] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });

  const toggle = (key: keyof typeof open) =>
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="w-full h-full p-4 bg-white rounded shadow overflow-y-auto">
      {/* Stream Gauges */}
      <div className="mb-4">
        <button
          onClick={() => toggle("gauges")}
          className="w-full text-left font-semibold text-gray-800 flex justify-between"
        >
          Stream Gauges
          <span>{open.gauges ? "▲" : "▼"}</span>
        </button>
        {open.gauges && (
          <ul className="ml-2 mt-2 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" /> Water Level</li>
            <li><input type="checkbox" /> Water Temperature</li>
          </ul>
        )}
      </div>

      {/* Weather Data */}
      <div className="mb-4">
        <button
          onClick={() => toggle("weather")}
          className="w-full text-left font-semibold text-gray-800 flex justify-between"
        >
          Weather Data
          <span>{open.weather ? "▲" : "▼"}</span>
        </button>
        {open.weather && (
          <ul className="ml-2 mt-2 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" /> Air Temperature</li>
            <li><input type="checkbox" /> Barometric Pressure</li>
            <li><input type="checkbox" /> Wind Speed and Direction</li>
            <li><input type="checkbox" /> Rainfall</li>
            <li><input type="checkbox" /> Solar Radiation</li>
            <li><input type="checkbox" /> Soil Moisture</li>
          </ul>
        )}
      </div>

      {/* Water Quality */}
      <div>
        <button
          onClick={() => toggle("quality")}
          className="w-full text-left font-semibold text-gray-800 flex justify-between"
        >
          Water Quality
          <span>{open.quality ? "▲" : "▼"}</span>
        </button>
        {open.quality && (
          <ul className="ml-2 mt-2 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" /> Temperature</li>
            <li><input type="checkbox" /> Conductivity</li>
            <li><input type="checkbox" /> Salinity</li>
            <li><input type="checkbox" /> Total Dissolved Solids (TDS)</li>
            <li><input type="checkbox" /> Dissolved Oxygen (ODO)</li>
            <li><input type="checkbox" /> Dissolved Oxygen Saturation (ODOSat)</li>
            <li><input type="checkbox" /> Turbidity</li>
            <li><input type="checkbox" /> Total Suspended Solids (TSS)</li>
          </ul>
        )}
      </div>
    </div>
  );
};

export default FilterPanel;
