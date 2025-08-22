import React from "react";
import { Download as DownloadIcon } from "lucide-react";
import { Button } from "@/components/animations/button";
import { SENSOR_FILTER_CONFIG, SAMPLING_FILTER_CONFIG } from "@/components/config/filters";

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
  startDate: Date | null;
  endDate: Date | null;
  data: {
    measurement_type: string;
    value: number;
    unit: string;
    recorded_at: string;
    group_type: string;
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
  startDate,
  endDate,
  data,
  isSampling = false,
}) => {
  const getFileName = () => {
    const parts = ["WELL"];
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

    const mappedSubFilters = {
      weather: subFilters.weather.map(label => METRIC_NAME_MAP[label] || label),
      quality: subFilters.quality.map(label => METRIC_NAME_MAP[label] || label),
      gauges: subFilters.gauges.map(label => METRIC_NAME_MAP[label] || label),
    };

    // 1. Filter based on activeGroups and subFilters
    const filtered = data.filter((entry) => {
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
    });

    const weatherKeys = [
      ...new Set(filtered.filter(d => d.group_type === "Weather").map(d => d.measurement_type))
    ].sort();
    const qualityKeys = [
      ...new Set(filtered.filter(d => d.group_type === "Quality").map(d => d.measurement_type))
    ].sort();
    const loggerKeys = [
      ...new Set(filtered.filter(d => d.group_type === "Logger").map(d => d.measurement_type))
    ].sort();

    // 2. Identify unique timestamps and metrics
    const timestamps = [...new Set(filtered.map((d) => d.recorded_at))].sort();
    const metricKeys = [...weatherKeys, ...qualityKeys, ...loggerKeys];

    // 3. Build a map of metric name → unit-suffixed label
    const metricLabelMap: Record<string, string> = {};
    metricKeys.forEach((key) => {
      const sample = filtered.find((d) => d.measurement_type === key);
      const unit = sample?.unit ?? "";
      metricLabelMap[key] = unit ? `${key}: ${unit}` : key;
    });

    // 4. Build rows with sensor/location info
    const rows = timestamps.map((timestamp, index) => {
      const row: any = {
        id: index + 1,
        timestamp,
        group_type: "",
      };

      // Store sensor info for each group type
      const sensorInfo: Record<string, string> = {
        Weather: "West Campus",
        Quality: "West Campus", 
        Logger: ""
      };

      metricKeys.forEach((key) => {
        const match = filtered.find(
          (d) => d.recorded_at === timestamp && d.measurement_type === key
        );
        if (match) {
          row[key] = match.value.toFixed(2);
          if (!row.group_type) row.group_type = match.group_type;
          
          // Extract sensor/station ID for Logger group
          if (match.group_type === "Logger") {
            const stationId = match.station_id || match.logger_id || match.site_id || "Unknown";
            sensorInfo.Logger = getLoggerLabel(stationId);
          }
        } else {
          row[key] = "";
        }
      });

      // Add sensor info to row
      row.sensorInfo = sensorInfo;

      return row;
    });

    // 5. Construct CSV headers and rows with the original blank column logic
    const headers = ["ID", "Timestamp"];
    const sensorSections: Array<{
      active: boolean;
      label: string;
      keys: string[];
    }> = [
      { active: activeGroups.weather, label: "Weather", keys: weatherKeys },
      { active: activeGroups.quality, label: "Quality", keys: qualityKeys },
      { active: activeGroups.gauges, label: "Logger", keys: loggerKeys },
    ];

    sensorSections.forEach((section, idx) => {
      if (section.active) {
        if (idx !== 0) headers.push(""); // Blank before each section except the first
        headers.push("Group");
        
        // Only add location header for Logger sections
        if (section.label === "Logger") {
          headers.push("Sensor");
        }
        
        headers.push(...section.keys.map((key) => metricLabelMap[key]));
      }
    });

    const csvRows = [headers.join(",")];

    rows.forEach((row) => {
      const csvRow = [row.id, row.timestamp];
      sensorSections.forEach((section, idx) => {
        if (section.active) {
          if (idx !== 0) csvRow.push(""); // Blank before each section except the first
          
          // Add sensor type
          csvRow.push(section.label);
          
          // Only add location for Logger sections
          if (section.label === "Logger") {
            const location = row.sensorInfo.Logger || "Unknown";
            csvRow.push(location);
          }
          
          // Add metric values
          csvRow.push(...section.keys.map((key) => row[key] ?? ""));
        }
      });
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

  const hasActiveData =
    !!startDate &&
    !!endDate &&
    (Object.keys(activeGroups) as Array<keyof typeof activeGroups>).some(
      (group) => activeGroups[group] && subFilters[group].length > 0
    );

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