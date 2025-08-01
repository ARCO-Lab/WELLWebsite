import React, { useState } from "react";
import { Checkbox } from "@/components/animations/Checkbox";
import { Label } from "@/components/animations/Label";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/animations/Collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
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
    <div className="space-y-4">
      {/* Water Loggers */}
      <Collapsible open={open.gauges} onOpenChange={(isOpen) => setOpen(prev => ({ ...prev, gauges: isOpen }))}>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="gauges"
            checked={activeGroups.gauges}
            onCheckedChange={() => toggleGroupMain('gauges')}
            className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
          />
          <CollapsibleTrigger className="flex items-center space-x-2 flex-1 text-left ">
            <Label htmlFor="gauges" className="font-poppins font-semibold text-primary cursor-pointer">
              Water Loggers
            </Label>
            {open.gauges ? <ChevronDown className="h-4 w-4 cursor-pointer hover:opacity-80" /> : <ChevronRight className="h-4 w-4 cursor-pointer hover:opacity-80" />}
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="ml-6 mt-2 space-y-2 animate-accordion-down">
          {["Water Level", "Water Temperature", "All Loggers"].map((label, idx) => (
            <FadeAnimation
              key={label}
              delay={idx * 30}
              duration={400}
              initialOpacity={0}
              blur={false}
              resetKey={open.gauges}
            >
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`gauges-${label}`}
                  checked={subFilters.gauges.includes(label)}
                  onCheckedChange={() => toggleSubFilter('gauges', label)}
                  className="data-[state=checked]:bg-accent data-[state=checked]:border-accent"
                />
                <Label htmlFor={`gauges-${label}`} className="mcmaster-body cursor-pointer">
                  {label}
                </Label>
              </div>
            </FadeAnimation>
          ))}

          {/* Individual Loggers - only show when All Loggers is not selected */}
          {!subFilters.gauges.includes("All Loggers") && (
            <div className="ml-6 space-y-2 mt-2">
              {["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"].map((label, idx) => (
                <FadeAnimation
                  key={label}
                  delay={idx * 60}
                  duration={400}
                  initialOpacity={0}
                  blur={false}
                  resetKey={!subFilters.gauges.includes("All Loggers")}
                >
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id={`gauges-${label}`}
                      checked={subFilters.gauges.includes(label)}
                      onCheckedChange={() => toggleSubFilter('gauges', label)}
                      className="data-[state=checked]:bg-accent data-[state=checked]:border-accent"
                    />
                    <Label htmlFor={`gauges-${label}`} className="mcmaster-body cursor-pointer text-sm">
                      {label}
                    </Label>
                  </div>
                </FadeAnimation>
              ))}
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>

      {/* Weather Data */}
      <Collapsible open={open.weather} onOpenChange={(isOpen) => setOpen(prev => ({ ...prev, weather: isOpen }))}>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="weather"
            checked={activeGroups.weather}
            onCheckedChange={() => toggleGroupMain('weather')}
            className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
          />
          <CollapsibleTrigger className="flex items-center space-x-2 flex-1 text-left">
            <Label htmlFor="weather" className="font-poppins font-semibold text-primary cursor-pointer">
              Weather Data
            </Label>
            {open.weather ? <ChevronDown className="h-4 w-4 cursor-pointer hover:opacity-80" /> : <ChevronRight className="h-4 w-4 cursor-pointer hover:opacity-80" />}
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="ml-6 mt-2 space-y-2 animate-accordion-down">
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
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`weather-${label}`}
                  checked={subFilters.weather.includes(label)}
                  onCheckedChange={() => toggleSubFilter('weather', label)}
                  className="data-[state=checked]:bg-accent data-[state=checked]:border-accent"
                />
                <Label htmlFor={`weather-${label}`} className="mcmaster-body cursor-pointer">
                  {label}
                </Label>
              </div>
            </FadeAnimation>
          ))}
        </CollapsibleContent>
      </Collapsible>

      {/* Water Quality */}
      <Collapsible open={open.quality} onOpenChange={(isOpen) => setOpen(prev => ({ ...prev, quality: isOpen }))}>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="quality"
            checked={activeGroups.quality}
            onCheckedChange={() => toggleGroupMain('quality')}
            className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
          />
          <CollapsibleTrigger className="flex items-center space-x-2 flex-1 text-left">
            <Label htmlFor="quality" className="font-poppins font-semibold text-primary cursor-pointer">
              Water Quality
            </Label>
            {open.quality ? <ChevronDown className="h-4 w-4 cursor-pointer hover:opacity-80" /> : <ChevronRight className="h-4 w-4 cursor-pointer hover:opacity-80" />}
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="ml-6 mt-2 space-y-2 animate-accordion-down">
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
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`quality-${label}`}
                  checked={subFilters.quality.includes(label)}
                  onCheckedChange={() => toggleSubFilter('quality', label)}
                  className="data-[state=checked]:bg-accent data-[state=checked]:border-accent"
                />
                <Label htmlFor={`quality-${label}`} className="mcmaster-body cursor-pointer">
                  {label}
                </Label>
              </div>
            </FadeAnimation>
          ))}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

export default FilterPanel;