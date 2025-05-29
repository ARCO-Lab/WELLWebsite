import { useMemo } from "react";
import useLatestMetrics from "@/hooks/useLatestMetrics";

interface QualityMetric {
  label: string;
  key: string; // this will match measurement_type
}

const metrics: QualityMetric[] = [
  { label: "Temperature", key: "Temperature" },
  { label: "Conductivity", key: "Conductivity" },
  { label: "Salinity", key: "Salinity" },
  { label: "Total Dissolved Solids (TDS)", key: "TDS" },
  { label: "Dissolved Oxygen (ODO)", key: "ODO" },
  { label: "Dissolved Oxygen Saturation (ODOSat)", key: "ODOSat" },
  { label: "Turbidity", key: "Turbidity" },
  { label: "Total Suspended Solids (TSS)", key: "TSS" },
];

const QualityMetrics = ({
  activeKeys,
  activeGroups,
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
}) => {
  const { metrics: allData } = useLatestMetrics();

  const qualityData = useMemo(() => {
    return allData.filter((d) => d.group_type === "Quality");
  }, [allData]);

  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow">
      <h2 className="mb-2 text-lg font-semibold text-black">Water Quality Metrics</h2>
      <ul className="space-y-1 text-sm text-gray-800">
        {metrics
          .filter(({ label }) => activeKeys.includes(label))
          .map(({ label, key }) => {
            const entry = qualityData.find((d) => d.measurement_type === key);
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

export default QualityMetrics;
