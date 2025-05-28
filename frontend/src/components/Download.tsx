import React from "react";

interface DownloadProps {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  startDate: Date | null;
  endDate: Date | null;
  data: {
    measurement_type: string;
    value: number;
    unit: string;
    recorded_at: string;
    group_type: string;
  }[];
}

const formatDate = (date: Date) => {
  return date.toISOString().split("T")[0].replace(/-/g, "");
};

const Download: React.FC<DownloadProps> = ({ activeGroups, startDate, endDate, data }) => {
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
    if (!data || data.length === 0) {
      console.warn("No data available to download.");
      return;
    }
    
    const headers = ["Sensor", "Value", "Unit", "Timestamp"];
    const filtered = data.filter((entry) => {
      if (entry.group_type === "Weather" && activeGroups.weather) return true;
      if (entry.group_type === "Quality" && activeGroups.quality) return true;
      if (entry.group_type === "Logger" && activeGroups.gauges) return true;
      return false;
    });

    const sorted = filtered.sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
    const rows = sorted.map((entry) => [
      entry.measurement_type,
      entry.value.toString(),
      entry.unit ?? "",
      entry.recorded_at,
    ]);

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
      className="w-full py-2 text-white bg-yellow-500 rounded cursor-pointer hover:bg-green-600"
    >
      Download
    </button>
  );
};

export default Download;
