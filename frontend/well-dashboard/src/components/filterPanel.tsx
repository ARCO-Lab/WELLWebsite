import React, { useState } from "react";

const FilterPanel = () => {
  const [open, setOpen] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });

  const [checked, setChecked] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });

  const toggleGroupMain = (group: keyof typeof checked) => {
    setChecked((prev) => ({ ...prev, [group]: !prev[group] }));
    setOpen((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow">
      {/* Water Loggers */}
      <div className="mb-4">
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox"
            checked={checked.gauges}
            onChange={() => toggleGroupMain("gauges")}
          />
          <span>Water Loggers</span>
        </label>
        {open.gauges && (
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" /> Water Level</li>
            <li><input type="checkbox" /> Water Temperature</li>
          </ul>
        )}
      </div>

      {/* Weather Data */}
      <div className="mb-4">
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox"
            checked={checked.weather}
            onChange={() => toggleGroupMain("weather")}
          />
          <span>Weather Data</span>
        </label>
        {open.weather && (
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" /> Air Temperature</li>
            <li><input type="checkbox" /> Barometric Pressure</li>
            <li><input type="checkbox" /> Wind Speed</li>
            <li><input type="checkbox" /> Gust Speed</li>
            <li><input type="checkbox" /> Wind Direction</li>
            <li><input type="checkbox" /> Relative Humidity</li>
            <li><input type="checkbox" /> Dew Point</li>
            <li><input type="checkbox" /> Rainfall</li>
            <li><input type="checkbox" /> Water Content</li>
            <li><input type="checkbox" /> Solar Radiation</li>
          </ul>
        )}
      </div>

      {/* Water Quality */}
      <div>
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox"
            checked={checked.quality}
            onChange={() => toggleGroupMain("quality")}
          />
          <span>Water Quality</span>
        </label>
        {open.quality && (
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
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
