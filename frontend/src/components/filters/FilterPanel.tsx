import React, { useState } from "react";

type Props = {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  setActiveGroups: React.Dispatch<React.SetStateAction<{
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  }>>;
  subFilters: {
    weather: string[];
    quality: string[];
  };
  setSubFilters: React.Dispatch<React.SetStateAction<{
    weather: string[];
    quality: string[];
    gauges: string[]; 
  }>>;
};

const FilterPanel: React.FC<Props> = ({ activeGroups, setActiveGroups, subFilters, setSubFilters }) => {
  const [open, setOpen] = useState({
    gauges: false,
    weather: false,
    quality: false,
  });

  const toggleGroupMain = (group: keyof typeof activeGroups) => {
    setActiveGroups((prev) => ({ ...prev, [group]: !prev[group] }));
    setOpen((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  const toggleSubFilter = (group: "weather" | "quality" | "gauges", label: string) => {
    setSubFilters((prev) => {
        const selected = new Set(prev[group]);
        selected.has(label) ? selected.delete(label) : selected.add(label);
        return { ...prev, [group]: Array.from(selected) };
    });
  };

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow">
      {/* Water Loggers */}
      <div className="mb-4">
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox" className= "cursor-pointer"
            checked={activeGroups.gauges}
            onChange={() => toggleGroupMain("gauges")}
          />
          <span>Water Loggers</span>
        </label>
        {open.gauges && (
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" className= "cursor-pointer"/> Water Level</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Water Temperature</li>
          </ul>
        )}
      </div>

      {/* Weather Data */}
      <div className="mb-4">
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox" className= "cursor-pointer"
            checked={activeGroups.weather}
            onChange={() => toggleGroupMain("weather")}
          />
          <span>Weather Data</span>
        </label>
        {open.weather && (
            <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
                {["Air Temperature", "Pressure", "Wind Speed", "Gust Speed", "Wind Direction", "Relative Humidity", "Dew Point", "Rain", "Water Content", "Solar Radiation", "Soil Temperature"].map((label) => (
                <li key={label}>
                    <label>
                    <input
                        type="checkbox" className= "cursor-pointer"
                        checked={subFilters.weather.includes(label)}
                        onChange={() => toggleSubFilter("weather", label)}
                    />{" "}
                    {label}
                    </label>
                </li>
                ))}
            </ul>
          )}

      </div>

      {/* Water Quality */}
      <div>
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox" className= "cursor-pointer"
            checked={activeGroups.quality}
            onChange={() => toggleGroupMain("quality")}
          />
          <span>Water Quality</span>
        </label>
        {open.quality && (
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            <li><input type="checkbox" className= "cursor-pointer"/> Temperature</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Conductivity</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Salinity</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Total Dissolved Solids (TDS)</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Dissolved Oxygen (ODO)</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Dissolved Oxygen Saturation (ODOSat)</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Turbidity</li>
            <li><input type="checkbox" className= "cursor-pointer"/> Total Suspended Solids (TSS)</li>
          </ul>
        )}
      </div>
    </div>
  );
};

export default FilterPanel;
