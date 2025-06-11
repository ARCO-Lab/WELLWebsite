import React, { useState } from "react";
import Collapsible from "@/components/animations/Collapsible";
import FadeAnimation from "@/components/animations/FadeAnimation";

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
    gauges: string[];
  };
  setSubFilters: React.Dispatch<React.SetStateAction<{
    weather: string[];
    quality: string[];
    gauges: string[]; 
  }>>;
  open: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  setOpen: React.Dispatch<React.SetStateAction<{ 
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  }>>;
};

const FilterPanel: React.FC<Props> = ({ activeGroups, setActiveGroups, subFilters, setSubFilters, open, setOpen }) => {

  const toggleGroupMain = (group: keyof typeof activeGroups) => {
    setActiveGroups((prev) => ({ ...prev, [group]: !prev[group] }));
    setOpen((prev) => ({ ...prev, [group]: !prev[group] }));

    if (group === "gauges") {
      setSubFilters((prev) => ({
        ...prev,
        gauges: !activeGroups.gauges
          ? ["All Loggers"] // all on
          : [],            // all off
      }));
    }
  };

  const toggleSubFilter = (group: "weather" | "quality" | "gauges", label: string) => {
    setSubFilters((prev) => {
      const selected = new Set(prev[group]);
      const loggerLabels = ["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"];
      const metricLabels = ["Water Level", "Water Temperature"];

      const isLoggerLabel = group === "gauges" && loggerLabels.includes(label);
      const isMetricLabel = group === "gauges" && metricLabels.includes(label);
      const isAllLoggers = group === "gauges" && label === "All Loggers";

      // Toggle value
      if (selected.has(label)) {
        selected.delete(label);
      } else {
        selected.add(label);
      }

      // Handle All Loggers toggle
      if (isAllLoggers) {
        const preserved = [...selected].filter((l) => metricLabels.includes(l));

        return {
          ...prev,
          gauges: selected.has("All Loggers")
            ? [...preserved, "All Loggers"]
            : [...preserved],
        };
      }


      // If toggling a logger and all loggers are now selected, convert to All Loggers
      if (isLoggerLabel) {
        const selectedLoggers = [...selected].filter((l) => loggerLabels.includes(l));
        const allSelected = loggerLabels.every((l) => selected.has(l));
        const preserved = [...selected].filter((l) => metricLabels.includes(l));

        if (allSelected) {
          return {
            ...prev,
            gauges: [...preserved, "All Loggers"],
          };
        }

        return {
          ...prev,
          gauges: [...preserved, ...selectedLoggers],
        };
      }

      // Regular toggle for metrics or other groups
      return {
        ...prev,
        [group]: Array.from(selected),
      };
    });
  };

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow">
      {/* Water Loggers */}
      <div className="mb-4">
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox" className="cursor-pointer"
            checked={activeGroups.gauges}
            onChange={() => toggleGroupMain("gauges")}
          />
          <span>Water Loggers</span>
        </label>
        <Collapsible open={open.gauges} >
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            {["Water Level", "Water Temperature", "All Loggers"].map((label, idx) => (
              <FadeAnimation
                key={label}
                delay={idx * 30}
                duration = {400}
                initialOpacity={0}
                blur={false}
                resetKey={open.gauges}
              >
                <li>
                <label>
                  <input
                    type="checkbox"
                    className="cursor-pointer"
                    checked={subFilters.gauges.includes(label)}
                    onChange={() => toggleSubFilter("gauges", label)}
                  />{" "}
                  {label}
                </label>
              </li>
              </FadeAnimation>
            ))}

            <Collapsible open={!subFilters.gauges.includes("All Loggers")} duration = {700}>
              <ul className="ml-6">
                {["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"].map((label, idx) => (
                  <FadeAnimation
                    key={label}
                    delay={idx * 60}
                    duration={400}
                    initialOpacity={0}
                    blur={false}
                    resetKey={!subFilters.gauges.includes("All Loggers")}
                  >
                    <li>
                      <label>
                        <input
                          type="checkbox"
                          className="cursor-pointer"
                          checked={subFilters.gauges.includes(label)}
                          onChange={() => toggleSubFilter("gauges", label)}
                        />{" "}
                        {label}
                      </label>
                    </li>
                  </FadeAnimation>
                ))}
              </ul>
            </Collapsible>
          </ul>
        </Collapsible>
      </div>

      {/* Weather Data */}
      <div className="mb-4">
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox" className="cursor-pointer"
            checked={activeGroups.weather}
            onChange={() => toggleGroupMain("weather")}
          />
          <span>Weather Data</span>
        </label>
        <Collapsible open={open.weather}>
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            {[
              "Air Temperature", "Pressure", "Wind Speed", "Gust Speed", "Wind Direction",
              "Relative Humidity", "Dew Point", "Rainfall", "Water Content", "Solar Radiation", "Soil Temperature"
            ].map((label, idx) => (
              <FadeAnimation
                key={label}
                delay={idx * 60}
                duration={400}
                initialOpacity={0}
                blur={false}
                resetKey={open.weather}
              >
                <li>
                  <label>
                    <input
                      type="checkbox"
                      className="cursor-pointer"
                      checked={subFilters.weather.includes(label)}
                      onChange={() => toggleSubFilter("weather", label)}
                    />{" "}
                    {label}
                  </label>
                </li>
              </FadeAnimation>
            ))}
          </ul>
        </Collapsible>
      </div>

      {/* Water Quality */}
      <div>
        <label className="flex items-center space-x-2 font-semibold text-gray-800">
          <input
            type="checkbox" className="cursor-pointer"
            checked={activeGroups.quality}
            onChange={() => toggleGroupMain("quality")}
          />
          <span>Water Quality</span>
        </label>
        <Collapsible open={open.quality}>
          <ul className="mt-2 ml-6 space-y-1 text-sm text-gray-700">
            {[
              "Water Temperature", "Conductivity", "Salinity", "Total Dissolved Solids (TDS)",
              "Dissolved Oxygen (ODO)", "Dissolved Oxygen Saturation (ODOSat)",
              "Turbidity", "Total Suspended Solids (TSS)"
            ].map((label, idx) => (
                <FadeAnimation
                  key={label}
                  delay={idx * 60}
                  duration={400}
                  initialOpacity={0}
                  blur={false}
                  resetKey={open.quality}
                >
                <li>
                  <label>
                    <input
                      type="checkbox"
                      className="cursor-pointer"
                      checked={subFilters.quality.includes(label)}
                      onChange={() => toggleSubFilter("quality", label)}
                    />{" "}
                    {label}
                  </label>
                </li>
              </FadeAnimation>
            ))}
          </ul>
        </Collapsible>
      </div>
    </div>
  );
};

export default FilterPanel;
