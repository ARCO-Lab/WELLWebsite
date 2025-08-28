import React from "react";
import { Download as DownloadIcon } from "lucide-react";
import { Button } from "@/components/animations/button";
import { SENSOR_FILTER_CONFIG, SAMPLING_FILTER_CONFIG, CREEK_ID_MAP_REVERSE, SAMPLING_METRICS } from "@/components/config/filters";

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
  // Sampling props
  activeCreeks?: {
    [key: string]: boolean;
  };
  samplingSubFilters?: {
    [key: string]: string[];
  };
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
  "Rainfall": "Rain",
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
    if (typeof creek === "object" && creek !== null && "sites" in creek && typeof (creek as any).sites === "object") {
      if ((creek as { sites: Record<string, string> }).sites[site_id]) {
        return (creek as { sites: Record<string, string> }).sites[site_id];
      }
    }
  }
  return site_id;
};

const getCreekLabel = (creek_id: string) => {
  const creek = SAMPLING_FILTER_CONFIG[creek_id as keyof typeof SAMPLING_FILTER_CONFIG];
  return creek?.label || creek_id;
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
    if (!data || data.length === 0) {
      console.warn("No data available to download.");
      return;
    }

    // Debug logging for sampling mode
    if (isSampling) {
      console.log("Sampling Mode Debug:");
      console.log("activeCreeks:", activeCreeks);
      console.log("samplingSubFilters:", samplingSubFilters);
      console.log("Sample data entries:", data.slice(0, 3));
      console.log("CREEK_ID_MAP_REVERSE:", CREEK_ID_MAP_REVERSE);
      
      // Test the filtering logic
      const testEntry = data[0];
      if (testEntry) {
        const creekKey = CREEK_ID_MAP_REVERSE[testEntry.creek_id || ''];
        console.log("Test entry creek_id:", testEntry.creek_id, "-> creekKey:", creekKey);
        console.log("Creek active?", activeCreeks[creekKey]);
        console.log("Creek filters:", samplingSubFilters[creekKey]);
      }
    }

    const mappedSubFilters = {
      weather: subFilters.weather.map(label => METRIC_NAME_MAP[label] || label),
      quality: subFilters.quality.map(label => METRIC_NAME_MAP[label] || label),
      gauges: subFilters.gauges.map(label => METRIC_NAME_MAP[label] || label),
    };

    // 1. Filter based on activeGroups/activeCreeks and subFilters/samplingSubFilters
    const filtered = data.filter((entry) => {
      if (isSampling) {
        // For sampling data, use creek_id to find the creek key
        const creekKey = CREEK_ID_MAP_REVERSE[entry.creek_id || ''];
        
        // Check if this creek is active
        if (!creekKey || !activeCreeks[creekKey]) return false;
        
        const creekFilters = samplingSubFilters[creekKey] || [];
        
        // Check if any filters are selected for this creek
        if (creekFilters.length === 0) return false;
        
        // Get the creek config to access sites
        const creekConfig = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
        const allSites = Object.keys(creekConfig?.sites || {});
        
        // Handle "All Sites" logic - if "All Sites" is selected, include all measurements from this creek
        const hasAllSites = creekFilters.includes("All Sites");
        if (hasAllSites) return true;
        
        // Check if the specific site is selected
        const hasSpecificSite = creekFilters.includes(entry.site_id || '');
        if (hasSpecificSite) return true;
        
        // Check if the specific measurement type (metric) is selected
        const hasMetric = creekFilters.includes(entry.measurement_type);
        if (hasMetric) return true;
        
        return false;
      } else {
        // Original sensor logic
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

    // 2. Identify unique timestamps and metrics
    const timestamps = [...new Set(filtered.map((d) => d.recorded_at))].sort();
    
    let metricKeys: string[];
    let sectionKeys: Array<{ active: boolean; label: string; keys: string[]; creekKey?: string; sites?: string[] }>;

    if (isSampling) {
      metricKeys = [...new Set(filtered.map(d => d.measurement_type))].sort();
      
      // Build sectionKeys: one per creek (not per creek-site combination)
      sectionKeys = Object.entries(activeCreeks)
        .filter(([_, active]) => active)
        .map(([creekKey, _]) => {
          const creek = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
          const creekFilters = samplingSubFilters[creekKey] || [];
          const allSiteIds = Object.keys(creek?.sites || {});

          // Get selected sites
          let selectedSites: string[] = [];
          if (creekFilters.includes('All Sites')) {
            selectedSites = allSiteIds;
          } else {
            selectedSites = creekFilters.filter(f => allSiteIds.includes(f));
          }

          // Get selected metrics
          const selectedMetrics = creekFilters.filter(f => SAMPLING_METRICS.includes(f));

          return {
            active: true,
            label: creek?.label || creekKey,
            keys: selectedMetrics,
            creekKey,
            sites: selectedSites,
          };
        });
    } else {
      const weatherKeys = [
        ...new Set(filtered.filter(d => d.group_type === "Weather").map(d => d.measurement_type))
      ].sort();
      const qualityKeys = [
        ...new Set(filtered.filter(d => d.group_type === "Quality").map(d => d.measurement_type))
      ].sort();
      const loggerKeys = [
        ...new Set(filtered.filter(d => d.group_type === "Logger").map(d => d.measurement_type))
      ].sort();

      metricKeys = [...weatherKeys, ...qualityKeys, ...loggerKeys];
      sectionKeys = [
        { active: activeGroups.weather, label: "Weather", keys: weatherKeys },
        { active: activeGroups.quality, label: "Quality", keys: qualityKeys },
        { active: activeGroups.gauges, label: "Logger", keys: loggerKeys },
      ];
    }

    // 3. Build a map of metric name → unit-suffixed label
    const metricLabelMap: Record<string, string> = {};
    metricKeys.forEach((key) => {
      const sample = filtered.find((d) => d.measurement_type === key);
      const unit = sample?.unit ?? "";
      metricLabelMap[key] = unit ? `${key}: ${unit}` : key;
    });

    // 4. Build rows - one row per timestamp with all sites/metrics
    const rows = timestamps.map((timestamp, index) => {
      const row: any = {
        id: index + 1,
        timestamp,
      };

      if (isSampling) {
        // For sampling: organize data by creek -> site -> metric
        sectionKeys.forEach((section) => {
          section.sites?.forEach((siteId) => {
            const siteLabel = getSamplingLabel(siteId);
            section.keys.forEach(metric => {
              // Find data for this creek, site, metric, and timestamp
              const match = filtered.find(
                d =>
                  CREEK_ID_MAP_REVERSE[d.creek_id || ''] === section.creekKey &&
                  d.site_id === siteId &&
                  d.measurement_type === metric &&
                  d.recorded_at === timestamp
              );
              
              const key = `${section.label}_${siteLabel}_${metric}`;
              row[key] = match ? match.value.toFixed(2) : "";
            });
          });
        });
      } else {
        // For sensors: organize data by group -> site -> metric
        sectionKeys.forEach((section) => {
          if (section.label === "Logger") {
            // FIXED: Only use the selected logger IDs from subFilters.gauges
            const selectedLoggerIds = subFilters.gauges.sort();
            
            selectedLoggerIds.forEach(siteId => {
              const siteLabel = getLoggerLabel(siteId);
              section.keys.forEach(metric => {
                const match = filtered.find(d => 
                  d.group_type === "Logger" &&
                  (d.station_id || d.logger_id || d.site_id) === siteId && 
                  d.measurement_type === metric &&
                  d.recorded_at === timestamp
                );
                const key = `${section.label}_${siteLabel}_${metric}`;
                row[key] = match ? match.value.toFixed(2) : "";
              });
            });
          } else {
            // Weather and Quality - single site
            const siteLabel = "West Campus";
            section.keys.forEach(metric => {
              const match = filtered.find(d => 
                d.group_type === section.label && 
                d.measurement_type === metric && 
                d.recorded_at === timestamp
              );
              const key = `${section.label}_${siteLabel}_${metric}`;
              row[key] = match ? match.value.toFixed(2) : "";
            });
          }
        });
      }

      return row;
    });

    // 5. Build dynamic headers and CSV structure
    const headers = ["ID", "Timestamp"];
    const activeSensorSections = sectionKeys.filter(section => section.active);

    // Build headers dynamically based on the structure
    if (isSampling) {
      activeSensorSections.forEach((section, sectionIdx) => {
        if (sectionIdx !== 0) headers.push(""); // Blank separator between sections
        headers.push("Creek"); // Creek header
        headers.push("Site");  // Site header
        
        // Sort sites for consistent ordering and add metric headers for each site
        const sortedSites = (section.sites || []).sort();
        
        // Only include sites that have selected metrics and data
        const selectedSites = sortedSites.filter(siteId => {
          // Check if this site has data for any of the selected metrics
          return section.keys.some(metric => {
            return filtered.some(d => 
              CREEK_ID_MAP_REVERSE[d.creek_id || ''] === section.creekKey &&
              d.site_id === siteId &&
              d.measurement_type === metric
            );
          });
        });
        
        selectedSites.forEach((siteId, siteIdx) => {
          if (siteIdx > 0) {
            headers.push("Site"); // Add "Site" header before each additional site
          }
          // Add metric columns for this site
          section.keys.forEach(metric => {
            headers.push(metricLabelMap[metric] || metric);
          });
        });
      });
    } else {
      activeSensorSections.forEach((section, sectionIdx) => {
        if (sectionIdx !== 0) headers.push(""); // Blank separator between sections
        headers.push("Group"); // Group header
        
        if (section.label === "Logger") {
          headers.push("Sensor"); // Sensor header for first logger
          
          // FIXED: Only use the selected logger IDs from subFilters.gauges
          const selectedLoggerIds = subFilters.gauges.sort();
          
          // Add metric headers for each selected logger
          selectedLoggerIds.forEach((siteId, siteIdx) => {
            // Add metric headers for this logger
            section.keys.forEach(metric => {
              headers.push(metricLabelMap[metric] || metric);
            });
            
            // Add "Sensor" header for next logger (if there is one)
            if (siteIdx < selectedLoggerIds.length - 1) {
              headers.push("Sensor");
            }
          });
        } else {
          // Weather/Quality - just add metrics after Group
          section.keys.forEach(metric => {
            headers.push(metricLabelMap[metric] || metric);
          });
        }
      });
    }

    // 6. Build CSV rows
    const csvRows = [headers.join(",")];

    rows.forEach((row) => {
      const csvRow = [row.id, row.timestamp];
      
      if (isSampling) {
        activeSensorSections.forEach((section, sectionIdx) => {
          if (sectionIdx !== 0) csvRow.push(""); // Blank separator between sections
          
          csvRow.push(section.label); // Actual creek name (e.g., "Ancaster Creek")
          
          // Sort sites for consistent ordering, but only include selected sites with data
          const sortedSites = (section.sites || []).sort();
          const selectedSites = sortedSites.filter(siteId => {
            // Check if this site has data for any of the selected metrics
            return section.keys.some(metric => {
              return filtered.some(d => 
                CREEK_ID_MAP_REVERSE[d.creek_id || ''] === section.creekKey &&
                d.site_id === siteId &&
                d.measurement_type === metric
              );
            });
          });
          
          selectedSites.forEach((siteId, siteIdx) => {
            const siteLabel = getSamplingLabel(siteId);
            
            if (siteIdx === 0) {
              // First site - site name goes in the Site column after Creek
              csvRow.push(siteLabel);
            } else {
              // Additional sites - add site name in new Site column
              csvRow.push(siteLabel);
            }
            
            // Add metric values for this site
            section.keys.forEach(metric => {
              const key = `${section.label}_${siteLabel}_${metric}`;
              csvRow.push(row[key] || "");
            });
          });
        });
      } else {
        activeSensorSections.forEach((section, sectionIdx) => {
          if (sectionIdx !== 0) csvRow.push(""); // Blank separator between sections
          csvRow.push(section.label); // Actual group name (e.g., "Logger", "Weather")
          
          if (section.label === "Logger") {
            // FIXED: Only use the selected logger IDs from subFilters.gauges
            const selectedLoggerIds = subFilters.gauges.sort();
            
            // Add first logger name
            if (selectedLoggerIds.length > 0) {
              const firstSiteLabel = getLoggerLabel(selectedLoggerIds[0]);
              csvRow.push(firstSiteLabel);
            }
            
            // Add each selected logger and its metrics
            selectedLoggerIds.forEach((siteId, siteIdx) => {
              const siteLabel = getLoggerLabel(siteId);
              
              // Add metric values for this logger
              section.keys.forEach(metric => {
                const key = `${section.label}_${siteLabel}_${metric}`;
                csvRow.push(row[key] || "");
              });
              
              // Add next logger name (if there is one)
              if (siteIdx < selectedLoggerIds.length - 1) {
                const nextSiteLabel = getLoggerLabel(selectedLoggerIds[siteIdx + 1]);
                csvRow.push(nextSiteLabel);
              }
            });
          } else {
            // Weather/Quality - just add metrics after Group (no sensor names)
            section.keys.forEach(metric => {
              const key = `${section.label}_West Campus_${metric}`;
              csvRow.push(row[key] || "");
            });
          }
        });
      }
      
      csvRows.push(csvRow.join(","));
    });

    // 6. Download as CSV
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

  const hasActiveData = !!startDate && !!endDate && (() => {
    if (isSampling) {
      return Object.entries(activeCreeks).some(([creekKey, active]) => 
        active && (samplingSubFilters[creekKey]?.length || 0) > 0
      );
    } else {
      return (Object.keys(activeGroups) as Array<keyof typeof activeGroups>).some(
        (group) => activeGroups[group] && subFilters[group].length > 0
      );
    }
  })();

  console.log({
    isSampling,
    startDate,
    endDate,
    activeCreeks,
    samplingSubFilters,
    hasActiveData
  });

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