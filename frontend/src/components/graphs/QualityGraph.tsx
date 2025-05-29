import { useMemo } from "react";
import useFilteredData from "@/hooks/useFilteredData";

interface Props {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  subFilters: {
    gauges: string[];
    weather: string[];
    quality: string[];
  };
  startDate: Date | null;
  endDate: Date | null;
}

const QualityGraph = ({ activeGroups, subFilters, startDate, endDate }: Props) => {
  const { data, loading, error } = useFilteredData(activeGroups, startDate, endDate);

  const qualityData = useMemo(() => {
    return data.filter(
      (d) =>
        d.group_type === "Quality" &&
        subFilters.quality.includes(d.measurement_type)
    );
  }, [data, subFilters]);

  return (
    <div className="p-4 bg-white rounded shadow">
      <h2 className="mb-2 text-lg font-semibold text-black">Water Quality</h2>
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <pre className="overflow-x-auto text-sm text-gray-700 whitespace-pre-wrap">
          {JSON.stringify(qualityData, null, 2)}
        </pre>
      )}
    </div>
  );
};

export default QualityGraph;
