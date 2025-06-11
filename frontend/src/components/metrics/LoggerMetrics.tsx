import { useMemo } from "react";

interface LoggerMetric {
  label: string;
  key: string; // Matches measurement_type
}

const metricOptions: LoggerMetric[] = [
  { label: "Water Level", key: "Water Level" },
  { label: "Water Temperature", key: "Water Temperature" },
];

const LoggerMetrics = ({
  activeKeys,
  activeGroups,
  metrics: allData = [],
  loading = false,
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
  metrics?: any[];
  loading?: boolean;
}) => {
  const loggerData = useMemo(() => {
    return allData.filter((d) => d.group_type === "Logger");
  }, [allData]);

  // Determine which loggers to show
  const showAllLoggers = activeKeys.includes("All Loggers");
  const visibleLoggers = showAllLoggers
    ? ["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"]
    : activeKeys
        .filter((k) => k.startsWith("Logger"))
        .sort((a, b) => {
          const numA = parseInt(a.split(" ")[1]);
          const numB = parseInt(b.split(" ")[1]);
          return numA - numB;
        });

  // Determine which metrics to show
  const visibleMetrics = metricOptions.filter(({ label }) => activeKeys.includes(label));

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow">
      <h2 className="mb-2 text-lg font-semibold text-black">Water Logger Metrics</h2>
      {visibleLoggers.map((logger) => (
        <div key={logger} className="mb-3">
          <h3 className="font-medium text-black">{logger}:</h3>
          <ul className="ml-4 space-y-1 text-sm text-gray-800">
            {visibleMetrics.map(({ label, key }) => {
              const match = loggerData.find(
                (d) =>
                  d.measurement_type === key &&
                  d.group_type === "Logger" &&
                  d.group_name === logger // <-- likely should be group_name, not group_type
              );
              const value = match?.value?.toFixed(2) ?? "--";
              const unit = match?.unit ?? "";
              return (
                <li key={key}>
                  <span className="font-medium">{label}:</span> {value} {unit}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
};

export default LoggerMetrics;