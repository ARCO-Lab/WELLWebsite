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
    timestamp: string;
    group_type: string;
  }[];
}

const formatDate = (date: Date) => {
  return date.toISOString().split("T")[0].replace(/-/g, "");
};

const Download: React.FC<DownloadProps> = ({
  activeGroups,
  subFilters,
  startDate,
  endDate,
  data
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

  // 1. Filter by active groups and subfilters
  const filtered = data.filter((entry) => {
    if (entry.group_type === "Weather" && activeGroups.weather) {
      return subFilters.weather.includes(entry.measurement_type);
    }
    if (entry.group_type === "Quality" && activeGroups.quality) {
      return subFilters.quality.includes(entry.measurement_type);
    }
    if (entry.group_type === "Logger" && activeGroups.gauges) {
      return subFilters.gauges.includes(entry.measurement_type);
    }
    return false;
  });

  // 2. Identify unique timestamps and metrics
  const timestamps = [...new Set(filtered.map((d) => d.timestamp))].sort();
  const metricKeys = [
    ...new Set(filtered.map((d) => d.measurement_type)),
  ].sort();

  // 3. Build rows
  const rows = timestamps.map((timestamp, index) => {
    const row: any = {
      id: index + 1,
      timestamp,
    };

    metricKeys.forEach((key) => {
      const match = filtered.find(
        (d) => d.timestamp === timestamp && d.measurement_type === key
      );
      row[key] = match ? match.value.toFixed(2) : "";
    });

    return row;
  });

  // 4. Construct CSV headers and rows
  const headers = ["ID", "Timestamp", ...metricKeys];
  const csvRows = [headers.join(",")];

  rows.forEach((row) => {
    const csvRow = headers.map((header) => row[header] ?? "").join(",");
    csvRows.push(csvRow);
  });

  // 5. Download as CSV
  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
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
