// This file defines the FilterPanel component for rendering sensor and sampling filter groups with checkboxes and collapsible sections.
// It manages filter state, group toggling, and sub-filter logic for the dashboard UI.

import React from "react";
import { Checkbox } from "@/components/animations/Checkbox";
import { Label } from "@/components/animations/Label";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/animations/Collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import FadeAnimation from "@/components/animations/FadeAnimation";
import { SENSOR_FILTER_CONFIG, SAMPLING_FILTER_CONFIG, SAMPLING_METRICS } from "@/components/config/filters";

// ADD M asl (Metres above sea level) for water surface elevation

// --- PROPS ---
interface FilterPanelProps {
  activeTab: "sensor" | "sampling";
  activeGroups: { [key: string]: boolean };
  setActiveGroups: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  subFilters: { [key: string]: string[] };
  setSubFilters: React.Dispatch<React.SetStateAction<{ [key: string]: string[] }>>;
  activeCreeks: { [key: string]: boolean };
  setActiveCreeks: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  samplingSubFilters: { [key: string]: string[] };
  setSamplingSubFilters: React.Dispatch<React.SetStateAction<{ [key: string]: string[] }>>;
  open: { [key: string]: boolean };
  setOpen: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  chevronState: { [key: string]: boolean };
  setChevronState: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
}

// --- COMPONENT ---
const FilterPanel: React.FC<FilterPanelProps> = ({
  activeTab,
  activeGroups, setActiveGroups, subFilters, setSubFilters,
  activeCreeks, setActiveCreeks, samplingSubFilters, setSamplingSubFilters,
  open, setOpen,
  chevronState, setChevronState
}) => {

  // Handles chevron toggle for collapsible groups
  const handleChevronClick = (groupKey: string) => {
    const newChevronState = !chevronState[groupKey];
    setChevronState(prev => ({ ...prev, [groupKey]: newChevronState }));
    setOpen(prev => ({ ...prev, [groupKey]: newChevronState }));
  };

  // Handles toggling the main group checkbox (select/deselect all)
  const handleMainToggle = (groupKey: string) => {
    const isSensor = activeTab === 'sensor';
    const setActive = isSensor ? setActiveGroups : setActiveCreeks;
    const setSubs = isSensor ? setSubFilters : setSamplingSubFilters;
    
    // Correctly get config based on tab
    const config = isSensor 
      ? SENSOR_FILTER_CONFIG[groupKey as keyof typeof SENSOR_FILTER_CONFIG] 
      : { ...SAMPLING_FILTER_CONFIG[groupKey as keyof typeof SAMPLING_FILTER_CONFIG], metrics: SAMPLING_METRICS, itemsLabel: "All Sites" };

    const currentlyActive = isSensor ? activeGroups[groupKey] : activeCreeks[groupKey];

    // Update chevron based on your cases
    if (!currentlyActive) {
      // Case 1 & 2: active group = false -> chevron = true
      setChevronState(prev => ({ ...prev, [groupKey]: true }));
      setOpen(prev => ({ ...prev, [groupKey]: true }));
    } else {
      // Case 3 & 4: active group = true -> chevron = false
      setChevronState(prev => ({ ...prev, [groupKey]: false }));
      setOpen(prev => ({ ...prev, [groupKey]: false }));
    }

    const isOpening = !currentlyActive;

    setActive((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));

    // When opening a group, select all metrics and "All Items" (if it exists)
    if (isOpening) {
      const allMetrics = config.metrics || [];
      const itemsLabel = (config as any).itemsLabel;
      const allFilters = itemsLabel ? [...allMetrics, itemsLabel] : allMetrics;
      
      setSubs(prev => ({
        ...prev,
        [groupKey]: allFilters,
      }));
    } else {
      // When closing, clear all filters
      setSubs(prev => ({
        ...prev,
        [groupKey]: [],
      }));
    }
  };

  // Handles toggling individual sub-filters (metrics, items, "All" toggles)
  const handleSubToggle = (groupKey: string, value: string) => {
    const isSensor = activeTab === 'sensor';
    const setSubs = isSensor ? setSubFilters : setSamplingSubFilters;
    
    const config = isSensor 
      ? SENSOR_FILTER_CONFIG[groupKey as keyof typeof SENSOR_FILTER_CONFIG] 
      : { 
          ...SAMPLING_FILTER_CONFIG[groupKey as keyof typeof SAMPLING_FILTER_CONFIG], 
          metrics: SAMPLING_METRICS, 
          itemsLabel: "All Sites",
          items: Object.keys((SAMPLING_FILTER_CONFIG[groupKey as keyof typeof SAMPLING_FILTER_CONFIG] as any).sites || {})
        };

    setSubs(prev => {
      const currentSubs = new Set(prev[groupKey] || []);
      
      // Use type-safe property access
      const allItems = 'items' in config && config.items && config.items.length > 0
        ? config.items
        : 'sites' in config && config.sites 
          ? Object.keys(config.sites)
          : [];
      
      const itemsLabel = 'itemsLabel' in config ? config.itemsLabel : undefined;
      const isMetric = config.metrics.includes(value);

      // Case 1: Toggling a metric (e.g., "Water Level", "E. coli")
      if (isMetric) {
        if (currentSubs.has(value)) {
          currentSubs.delete(value);
        } else {
          currentSubs.add(value);
        }
      }
      // Case 2: Toggling the "All Items" checkbox itself
      else if (itemsLabel && value === itemsLabel) {
        if (currentSubs.has(itemsLabel)) {
          currentSubs.delete(itemsLabel); // Uncheck "All"
        } else {
          currentSubs.add(itemsLabel); // Check "All"
          allItems.forEach(item => currentSubs.delete(item)); // and uncheck all individuals
        }
      }
      // Case 3: Toggling an individual item (e.g., "Logger 4", "Site 2")
      else {
        // If "All" is currently checked, we need to expand it first
        if (itemsLabel && currentSubs.has(itemsLabel)) {
          currentSubs.delete(itemsLabel); // Uncheck "All"
          allItems.forEach(item => currentSubs.add(item)); // and check all individuals
        }

        // Now, toggle the specific item that was clicked
        if (currentSubs.has(value)) {
          currentSubs.delete(value);
        } else {
          currentSubs.add(value);
        }

        // After toggling, check if all individual items are now selected
        const allIndividualItemsSelected = allItems.length > 0 && allItems.every(item => currentSubs.has(item));

        // If they are, switch to the "All" state
        if (allIndividualItemsSelected && itemsLabel) {
          allItems.forEach(item => currentSubs.delete(item));
          currentSubs.add(itemsLabel);
        }
      }
      
      return { ...prev, [groupKey]: Array.from(currentSubs) };
    });
  };

  // Renders a filter group with metrics and item checkboxes
  const renderFilterGroup = (groupKey: string, config: any, subs: string[]) => {
    // Use type-safe property access
    const items = 'items' in config && config.items 
      ? config.items 
      : 'sites' in config && config.sites 
        ? Object.keys(config.sites) 
        : [];
    
    const showSubItems = items.length > 1;

    // Create a unified list of [id, name] pairs for rendering.
    const itemsToRender = 'items' in config && config.items 
      ? config.items.map((item: string) => [item, item]) 
      : 'sites' in config && config.sites
        ? Object.entries(config.sites)
        : [];

    // Get current chevron state
    const currentChevron = chevronState[groupKey] || false; // false = right, true = down

    const itemsLabel = 'itemsLabel' in config ? config.itemsLabel : undefined;

    return (
      <Collapsible key={groupKey} open={open[groupKey]} onOpenChange={(isOpen) => handleChevronClick(groupKey)}>
        <div className="flex items-center space-x-2">
          <Checkbox
            id={groupKey}
            checked={activeTab === 'sensor' ? activeGroups[groupKey] : activeCreeks[groupKey]}
            onCheckedChange={() => handleMainToggle(groupKey)}
            className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
          />
          <CollapsibleTrigger className="flex items-center space-x-2 flex-1 text-left">
            <Label htmlFor={groupKey} className="font-poppins font-semibold text-primary cursor-pointer">{config.label}</Label>
            {currentChevron ? <ChevronDown className="h-4 w-4 cursor-pointer" /> : <ChevronRight className="h-4 w-4 cursor-pointer" />}
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="ml-6 mt-2 space-y-2 animate-accordion-down">
          {/* Render metrics first */}
          {config.metrics.map((label: string, idx: number) => (
            <FadeAnimation key={label} delay={idx * 30} duration={400} resetKey={open[groupKey]}>
              <div className="flex items-center space-x-2">
                <Checkbox id={`${groupKey}-${label}`} checked={subs.includes(label)} onCheckedChange={() => handleSubToggle(groupKey, label)} className="data-[state=checked]:bg-accent" />
                <Label htmlFor={`${groupKey}-${label}`} className="mcmaster-body cursor-pointer">{label}</Label>
              </div>
            </FadeAnimation>
          ))}
          
          {/* Only show "All Items" and individual items if it's a multi-item group */}
          {showSubItems && itemsLabel && (
            <>
              {/* "All Items" Toggle */}
              <FadeAnimation delay={config.metrics.length * 30} duration={400} resetKey={open[groupKey]}>
                <div className="flex items-center space-x-2">
                  <Checkbox id={`${groupKey}-${itemsLabel}`} checked={subs.includes(itemsLabel)} onCheckedChange={() => handleSubToggle(groupKey, itemsLabel)} className="data-[state=checked]:bg-accent" />
                  <Label htmlFor={`${groupKey}-${itemsLabel}`} className="mcmaster-body cursor-pointer">{itemsLabel}</Label>
                </div>
              </FadeAnimation>

              {/* Individual Items (Loggers or Sites) */}
              {!subs.includes(itemsLabel) && (
                <div className="ml-6 space-y-2 mt-2">
                  {itemsToRender.map(([id, name]: [string, string], idx: number) => (
                    <FadeAnimation key={id} delay={idx * 30} duration={400} resetKey={!subs.includes(itemsLabel)}>
                      <div className="flex items-center space-x-2">
                        <Checkbox id={`${groupKey}-${id}`} checked={subs.includes(id)} onCheckedChange={() => handleSubToggle(groupKey, id)} className="data-[state=checked]:bg-accent" />
                        <Label htmlFor={`${groupKey}-${id}`} className="mcmaster-body cursor-pointer text-sm">{name}</Label>
                      </div>
                    </FadeAnimation>
                  ))}
                </div>
              )}
            </>
          )}
        </CollapsibleContent>
      </Collapsible>
    );
  };
  
  return (
    <div className="space-y-4">
      {activeTab === 'sensor' && Object.entries(SENSOR_FILTER_CONFIG).map(([key, config]) =>
        renderFilterGroup(key, config, subFilters[key] || [])
      )}
      {activeTab === 'sampling' && Object.entries(SAMPLING_FILTER_CONFIG).map(([key, config]) =>
        renderFilterGroup(key, { ...config, metrics: SAMPLING_METRICS, itemsLabel: "All Sites" }, samplingSubFilters[key] || [])
      )}
    </div>
  );
};

export default FilterPanel;