import { useMemo } from "react";
import useLatestMetrics from "@/hooks/useLatestMetrics";

interface LoggerMetric {
  label: string;
  key: string; // this will match measurement_type
}

const metrics: LoggerMetric[] = [
  { label: "Water Level", key: "Water Level" },
  { label: "Water Temperature", key: "Water Temperature" }
];

const LoggerMetrics = ({
  activeKeys,
  activeGroups,
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
}) => {
  const { metrics: allData } = useLatestMetrics();

  const loggerData = useMemo(() => {
    return allData.filter((d) => d.group_type === "Logger");
  }, [allData]);

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow">
      <h2 className="mb-2 text-lg font-semibold text-black">Water Logger Metrics</h2>
      <ul className="space-y-1 text-sm text-gray-800">
        {metrics
          .filter(({ label }) => activeKeys.includes(label))
          .map(({ label, key }) => {
            const entry = loggerData.find((d) => d.measurement_type === key);
            const value = entry?.value?.toFixed(2) ?? "--";
            const unit = entry?.unit ?? "";
            return (
              <li key={key}>
                <span className="font-medium">{label}:</span> {value} {unit}
              </li>
            );
          })}
      </ul>
    </div>
  );
};

export default LoggerMetrics;
