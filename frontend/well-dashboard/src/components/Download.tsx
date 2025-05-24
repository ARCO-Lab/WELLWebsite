import React from "react";

interface DownloadProps {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  startDate: Date | null;
  endDate: Date | null;
}

const formatDate = (date: Date) => {
  return date.toISOString().split("T")[0].replace(/-/g, "");
};

const Download: React.FC<DownloadProps> = ({ activeGroups, startDate, endDate }) => {
  const getFileName = () => {
    const parts = ["WELL"];
    if (activeGroups.gauges) parts.push("WaterLogger");
    if (activeGroups.quality) parts.push("WaterQuality");
    if (activeGroups.weather) parts.push("WeatherStation");

    const from = formatDate(startDate ?? new Date);
    const to = formatDate(endDate ?? new Date());

    return `${parts.join("_")}_${from}_${to}.csv`;
  };

  const handleDownload = () => {
    const headers = ["Sensor", "Value", "Unit", "Timestamp"];
    const rows: string[][] = [];

    // TODO: Replace this with real data fetching and formatting logic from database
    // Example: rows.push(["Temperature", "12.3", "°C", "2025-03-14 12:00:00"]);

    const csvContent = [headers, ...rows]
      .map((row) => row.join(","))
      .join("\n");

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
      className="w-full py-2 text-white bg-yellow-500 rounded hover:bg-green-600"
    >
      Download
    </button>
  );
};

export default Download;
