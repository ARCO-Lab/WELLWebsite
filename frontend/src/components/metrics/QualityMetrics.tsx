interface QualityMetric {
  label: string;
  key: string;
}

const metrics: QualityMetric[] = [
  { label: "Total Dissolved Solids (TDS)", key: "TDS" },
  { label: "Dissolved Oxygen (ODO)", key: "ODO" },
  { label: "Dissolved Oxygen Saturation (ODOSat)", key: "ODOSat" },
  { label: "Total Suspended Solids (TSS)", key: "TSS" },
  // Add more as needed
];

const QualityMetrics = ({
  activeKeys,
  activeGroups,
  metrics: qualityData = [],
  loading = false,
}: {
  activeKeys: string[];
  activeGroups: { weather: boolean; quality: boolean; gauges: boolean };
  metrics?: any[];
  loading?: boolean;
}) => {
  return (
    <div className="w-full h-full p-4 overflow-y-auto bg-white rounded shadow ">
      <h2 className="mb-2 text-lg font-semibold text-black">Quality Metrics</h2>
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