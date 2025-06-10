import React from "react";

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
    recorded_at: string; // change to timestamp once other api ready and inject_historical is done too
    group_type: string;
  }[];
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

const Download: React.FC<DownloadProps> = ({
  activeGroups,
  subFilters,
  startDate,
  endDate,
  data,
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

    // 4. Build rows
    const rows = timestamps.map((timestamp, index) => {
      const row: any = {
        id: index + 1,
        timestamp,
        group_type:"",
      };

      metricKeys.forEach((key) => {
        const match = filtered.find(
          (d) => d.recorded_at === timestamp && d.measurement_type === key
        );
        if(match) {
          row[key] = match ? match.value.toFixed(2) : "";
          if (!row.group_type) row.group_type = match.group_type;
        } else {
          row[key] = "";
        }
      });

      return row;
    });

    // 5. Construct CSV headers and rows
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
        headers.push("Sensor");
        headers.push(...section.keys.map((key) => metricLabelMap[key]));
      }
    });

    const csvRows = [headers.join(",")];

    rows.forEach((row) => {
      const csvRow = [row.id, row.timestamp];
      sensorSections.forEach((section, idx) => {
        if (section.active) {
          if (idx !== 0) csvRow.push(""); // Blank before each section except the first
          csvRow.push(section.label);
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

  return (
    <button
      onClick={handleDownload}
      className="w-full py-2 text-white bg-yellow-500 rounded cursor-pointer hover:bg-green-600"
    >
      Download
    </button>
  );
};

export default Download;
