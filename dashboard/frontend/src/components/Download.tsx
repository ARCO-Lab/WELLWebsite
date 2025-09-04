// This file defines the Download component for exporting filtered sensor or sampling data as a CSV file.
// It builds the CSV structure based on active filters, groups, and selected metrics/sites.

import React from "react";
import { Download as DownloadIcon } from "lucide-react";
import { Button } from "@/components/animations/button";
import {
  SENSOR_FILTER_CONFIG,
  SAMPLING_FILTER_CONFIG,
  CREEK_ID_MAP_REVERSE,
  SAMPLING_METRICS,
  SENSOR_STATION_COORDINATES,
  SAMPLING_SITE_COORDINATES,
} from "@/components/config/filters";

interface DownloadProps {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  subFilters: {
    weather: string[];
    quality: string[];
    gauges: string[];
  };
  activeCreeks?: { [key: string]: boolean };
  samplingSubFilters?: { [key: string]: string[] };
  startDate: Date | null;
  endDate: Date | null;
  data: {
    measurement_type: string;
    value: number;
    unit: string;
    recorded_at: string;
    group_type?: string;
    logger_id?: string;
    site_id?: string;
    station_id?: string;
    creek_id?: string;
  }[];
  isSampling?: boolean;
}

const METRIC_NAME_MAP: Record<string, string> = {
  Rainfall: "Rain",
  "Total Dissolved Solids (TDS)": "TDS",
  "Dissolved Oxygen (ODO)": "ODO",
  "Dissolved Oxygen Saturation (ODOSat)": "ODOSat",
  "Total Suspended Solids (TSS)": "TSS",
  // Add more as needed
};

const formatDate = (date: Date) => {
  return date.toISOString().split("T")[0].replace(/-/g, "");
};

const getLoggerLabel = (station_id: string) => {
  return SENSOR_FILTER_CONFIG.gauges.sites[station_id as keyof typeof SENSOR_FILTER_CONFIG.gauges.sites] || station_id;
};

const getSamplingLabel = (site_id: string) => {
  for (const creek of Object.values(SAMPLING_FILTER_CONFIG)) {
    if (
      typeof creek === "object" &&
      creek !== null &&
      "sites" in creek &&
      typeof (creek as any).sites === "object"
    ) {
      if ((creek as { sites: Record<string, string> }).sites[site_id]) {
        return (creek as { sites: Record<string, string> }).sites[site_id];
      }
    }
  }
  return site_id;
};

const getStationCoordinates = (station_id: string, group: string) => {
  if (group === "gauges") {
    const coords = SENSOR_STATION_COORDINATES.find(
      (coord) => coord.id === station_id && coord.group === "gauges"
    );
    return coords ? { lat: coords.lat, lng: coords.lng } : null;
  } else if (group === "weather") {
    const coords = SENSOR_STATION_COORDINATES.find((coord) => coord.group === "weather");
    return coords ? { lat: coords.lat, lng: coords.lng } : null;
  } else if (group === "quality") {
    const coords = SENSOR_STATION_COORDINATES.find((coord) => coord.group === "quality");
    return coords ? { lat: coords.lat, lng: coords.lng } : null;
  }
  return null;
};

const getSamplingCoordinates = (site_id: string) => {
  const coords = SAMPLING_SITE_COORDINATES.find((coord) => coord.id === site_id);
  return coords ? { lat: coords.lat, lng: coords.lng } : null;
};

const Download: React.FC<DownloadProps> = ({
  activeGroups,
  subFilters,
  activeCreeks = {},
  samplingSubFilters = {},
  startDate,
  endDate,
  data,
  isSampling = false,
}) => {
  const getFileName = () => {
    if (isSampling) {
      const activeCreekLabels = Object.entries(activeCreeks)
        .filter(([_, active]) => active)
        .map(([creekKey, _]) => {
          const creek = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
          return creek?.label || creekKey;
        });

      const parts = ["WELLAncasterWatershed", ...activeCreekLabels];
      const from = formatDate(startDate ?? new Date());
      const to = formatDate(endDate ?? new Date());
      return `${parts.join("_")}_${from}_${to}.csv`;
    }

    const parts = ["WELLWestCampus"];
    if (activeGroups.gauges) parts.push("WaterLogger");
    if (activeGroups.quality) parts.push("WaterQuality");
    if (activeGroups.weather) parts.push("WeatherStation");
    const from = formatDate(startDate ?? new Date());
    const to = formatDate(endDate ?? new Date());
    return `${parts.join("_")}_${from}_${to}.csv`;
  };

  const handleDownload = () => {
    // Build and trigger CSV download based on current filters and data
    if (!data || data.length === 0) {
      console.warn("No data available to download.");
      return;
    }

    const mappedSubFilters = {
      weather: subFilters.weather.map((label) => METRIC_NAME_MAP[label] || label),
      quality: subFilters.quality.map((label) => METRIC_NAME_MAP[label] || label),
      gauges: subFilters.gauges.map((label) => METRIC_NAME_MAP[label] || label),
    };

    // 1. Filter relevant entries
    const filtered = data.filter((entry) => {
      if (isSampling) {
        const creekKey = CREEK_ID_MAP_REVERSE[entry.creek_id || ""];
        if (!creekKey || !activeCreeks[creekKey]) return false;
        const creekFilters = samplingSubFilters[creekKey] || [];
        if (creekFilters.length === 0) return false;
        const creekConfig = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
        const allSites = Object.keys(creekConfig?.sites || {});
        if (creekFilters.includes("All Sites")) return true;
        if (creekFilters.includes(entry.site_id || "")) return true;
        if (creekFilters.includes(entry.measurement_type)) return true;
        return false;
      } else {
        if (entry.group_type === "Weather" && activeGroups.weather) {
          return mappedSubFilters.weather.includes(entry.measurement_type);
        }
        if (entry.group_type === "Quality" && activeGroups.quality) {
          return mappedSubFilters.quality.includes(entry.measurement_type);
        }
        if (entry.group_type === "Logger" && activeGroups.gauges) {
          return mappedSubFilters.gauges.includes(entry.measurement_type);
        }
        return false;
      }
    });

    const timestamps = [...new Set(filtered.map((d) => d.recorded_at))].sort();

    // --- SECTION CONFIGURATION ---
    const sectionConfigs: Array<{
      label: string;
      type: "weather" | "quality" | "logger" | "sampling";
      metrics: string[];
      sites?: Array<{ id: string; label: string; coords: { lat: number; lng: number } | null }>;
    }> = [];

    if (isSampling) {
      Object.entries(activeCreeks)
        .filter(([_, active]) => active)
        .forEach(([creekKey, _]) => {
          const creek = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
          const creekFilters = samplingSubFilters[creekKey] || [];
          const allSiteIds = Object.keys((creek && creek.sites) || {});
          let selectedSites: string[] = [];
          if (creekFilters.includes("All Sites")) {
            selectedSites = allSiteIds;
          } else {
            selectedSites = creekFilters.filter((f) => allSiteIds.includes(f));
          }
          // Only sites with *actual data* for the selected metrics
          const selectedMetrics = creekFilters.filter((f) => SAMPLING_METRICS.includes(f));
          const sitesWithData = selectedSites.filter((siteId) =>
            selectedMetrics.some((metric) =>
              filtered.some(
                (d) =>
                  CREEK_ID_MAP_REVERSE[d.creek_id || ""] === creekKey &&
                  d.site_id === siteId &&
                  d.measurement_type === metric
              )
            )
          );
          if (sitesWithData.length > 0 && selectedMetrics.length > 0) {
            sectionConfigs.push({
              label: creek?.label || creekKey,
              type: "sampling",
              metrics: selectedMetrics,
              sites: sitesWithData.map((siteId) => ({
                id: siteId,
                label: getSamplingLabel(siteId),
                coords: getSamplingCoordinates(siteId),
              })),
            });
          }
        });
    } else {
      // Weather
      if (activeGroups.weather) {
        const weatherMetrics = [
          ...new Set(filtered.filter((d) => d.group_type === "Weather").map((d) => d.measurement_type)),
        ].sort();
        if (weatherMetrics.length > 0) {
          sectionConfigs.push({
            label: "Weather",
            type: "weather",
            metrics: weatherMetrics,
            sites: [
              {
                id: "weather",
                label: "West Campus",
                coords: getStationCoordinates("", "weather"),
              },
            ],
          });
        }
      }
      // Quality
      if (activeGroups.quality) {
        const qualityMetrics = [
          ...new Set(filtered.filter((d) => d.group_type === "Quality").map((d) => d.measurement_type)),
        ].sort();
        if (qualityMetrics.length > 0) {
          sectionConfigs.push({
            label: "Quality",
            type: "quality",
            metrics: qualityMetrics,
            sites: [
              {
                id: "quality",
                label: "West Campus",
                coords: getStationCoordinates("", "quality"),
              },
            ],
          });
        }
      }
      // Logger(s)
      if (activeGroups.gauges) {
        let effectiveGaugeFilters = [...subFilters.gauges];
        if (subFilters.gauges.includes("All Loggers")) {
          effectiveGaugeFilters = effectiveGaugeFilters.filter((f) => f !== "All Loggers").concat(Object.keys(SENSOR_FILTER_CONFIG.gauges.sites));
        }
        // Only valid gauge metrics (order matches metrics in SENSOR_FILTER_CONFIG, not random set)
        const validGaugeMetrics = SENSOR_FILTER_CONFIG.gauges.metrics;
        const loggerMetrics = [
          ...new Set(
            filtered
              .filter((d) => d.group_type === "Logger" && validGaugeMetrics.includes(d.measurement_type))
              .map((d) => d.measurement_type)
          ),
        ].sort();
        // Only loggers that have *any* data for the chosen metrics
        const loggersWithData = effectiveGaugeFilters.filter((siteId) =>
          loggerMetrics.some((metric) =>
            filtered.some(
              (d) =>
                d.group_type === "Logger" &&
                (d.station_id || d.logger_id || d.site_id) === siteId &&
                d.measurement_type === metric
            )
          )
        );
        if (loggerMetrics.length > 0 && loggersWithData.length > 0) {
          sectionConfigs.push({
            label: "Logger",
            type: "logger",
            metrics: loggerMetrics,
            sites: loggersWithData.map((siteId) => ({
              id: siteId,
              label: getLoggerLabel(siteId),
              coords: getStationCoordinates(siteId, "gauges"),
            })),
          });
        }
      }
    }

    // --- HEADERS: identical structure for logger and sampling ---
    const headers = ["ID", "Timestamp"];
    sectionConfigs.forEach((section, sectionIdx) => {
      if (sectionIdx > 0) headers.push(""); // Section separator
      if (section.type === "sampling") {
        headers.push("Creek");
        section.sites?.forEach((site, siteIdx) => {
          headers.push("Site");
          headers.push("Latitude");
          headers.push("Longitude");
          section.metrics.forEach((metric) => {
            const unit = filtered.find((d) => d.measurement_type === metric)?.unit || "";
            headers.push(unit ? `${metric}: ${unit}` : metric);
          });
        });
      } else if (section.type === "logger") {
        headers.push("Group");
        section.sites?.forEach((site) => {
          headers.push("Sensor");
          headers.push("Latitude");
          headers.push("Longitude");
          section.metrics.forEach((metric) => {
            const unit = filtered.find((d) => d.measurement_type === metric)?.unit || "";
            headers.push(unit ? `${metric}: ${unit}` : metric);
          });
        });
      } else {
        // weather/quality: single site
        headers.push("Group");
        headers.push("Latitude");
        headers.push("Longitude");
        section.metrics.forEach((metric) => {
          const unit = filtered.find((d) => d.measurement_type === metric)?.unit || "";
          headers.push(unit ? `${metric}: ${unit}` : metric);
        });
      }
    });

    // --- ROWS: ensure one value per header, no extras!
    const csvRows = [headers.join(",")];
    timestamps.forEach((timestamp, index) => {
      const csvRow = [index + 1, timestamp];
      sectionConfigs.forEach((section, sectionIdx) => {
        if (sectionIdx > 0) csvRow.push("");
        if (section.type === "sampling") {
          csvRow.push(section.label);
          section.sites?.forEach((site) => {
            csvRow.push(site.label);
            csvRow.push(site.coords?.lat?.toString() || "");
            csvRow.push(site.coords?.lng?.toString() || "");
            section.metrics.forEach((metric) => {
              const creekConfigKey = Object.keys(SAMPLING_FILTER_CONFIG).find(
                (key) =>
                  SAMPLING_FILTER_CONFIG[key as keyof typeof SAMPLING_FILTER_CONFIG]?.label === section.label
              );
              const match = filtered.find(
                (d) =>
                  CREEK_ID_MAP_REVERSE[d.creek_id || ""] === creekConfigKey &&
                  d.site_id === site.id &&
                  d.measurement_type === metric &&
                  d.recorded_at === timestamp
              );
              csvRow.push(match ? match.value.toFixed(2) : "");
            });
          });
        } else if (section.type === "logger") {
          csvRow.push(section.label); // "Logger"
          section.sites?.forEach((site) => {
            csvRow.push(site.label);
            csvRow.push(site.coords?.lat?.toString() || "");
            csvRow.push(site.coords?.lng?.toString() || "");
            section.metrics.forEach((metric) => {
              const match = filtered.find(
                (d) =>
                  d.group_type === "Logger" &&
                  (d.station_id || d.logger_id || d.site_id) === site.id &&
                  d.measurement_type === metric &&
                  d.recorded_at === timestamp
              );
              csvRow.push(match ? match.value.toFixed(2) : "");
            });
          });
        } else {
          // weather/quality
          csvRow.push(section.label);
          const site = section.sites?.[0];
          if (site) {
            csvRow.push(site.coords?.lat?.toString() || "");
            csvRow.push(site.coords?.lng?.toString() || "");
            section.metrics.forEach((metric) => {
              const match = filtered.find(
                (d) =>
                  d.group_type === section.label &&
                  d.measurement_type === metric &&
                  d.recorded_at === timestamp
              );
              csvRow.push(match ? match.value.toFixed(2) : "");
            });
          }
        }
      });
      csvRows.push(csvRow.join(","));
    });

    // --- SAVE ---
    const csvContent = csvRows.join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", getFileName());
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Only allow download if at least one group or creek has active data
  const hasActiveData =
    !!startDate &&
    !!endDate &&
    (() => {
      if (isSampling) {
        return Object.entries(activeCreeks).some(
          ([creekKey, active]) => active && (samplingSubFilters[creekKey]?.length || 0) > 0
        );
      } else {
        return (Object.keys(activeGroups) as Array<keyof typeof activeGroups>).some(
          (group) => activeGroups[group] && subFilters[group].length > 0
        );
      }
    })();

  return (
    <Button
      onClick={handleDownload}
      disabled={!hasActiveData}
      className="btn-mcmaster-primary w-full"
    >
      <DownloadIcon className="h-4 w-4 mr-2" />
      Download Data
    </Button>
  );
};

export default Download;
