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

    // 1. Filter based on activeGroups and subFilters
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

    // 2. Get unique timestamps
    const timestamps = [...new Set(filtered.map((d) => d.recorded_at))].sort();

    // 3. Collect all metric keys based on activeGroups and subFilters
    const metricKeys: string[] = [
      ...(activeGroups.weather ? subFilters.weather : []),
      ...(activeGroups.quality ? subFilters.quality : []),
      ...(activeGroups.gauges ? subFilters.gauges : []),
    ];

    // 4. Map rows
    const rows = timestamps.map((timestamp, index) => {
      const row: any = {
        ID: index + 1,
        Timestamp: timestamp,
      };

      metricKeys.forEach((metric) => {
        const match = filtered.find(
          (d) => d.recorded_at === timestamp && d.measurement_type === metric
        );
        row[metric] = match ? match.value.toFixed(2) : "";
      });

      return row;
    });

    // 5. Create CSV
    const headers = ["ID", "Timestamp", ...metricKeys];
    const csvLines = [headers.join(",")];

    rows.forEach((row) => {
      const line = headers.map((header) => row[header] ?? "").join(",");
      csvLines.push(line);
    });

    const csvContent = csvLines.join("\n");
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
