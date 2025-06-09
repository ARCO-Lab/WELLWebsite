import React, { useEffect, useRef, useState } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';

interface SensorData {
  measurement_type: string;
  unit: string;
  recorded_at: string | Date;
  value: number;
}

interface MetricChartProps {
  activeGroup: 'gauges' | 'weather' | 'quality';
  subFilters: string[];
  height?: number;
  startDate: Date | null;
  endDate: Date | null;
  data: SensorData[];
  loading: boolean;
  error: Error | null;
}

const graphColors = ['#0866AB', '#50B748', '#F79425', '#E90D8B', '#88D1D9', '#7F488D', '#F1C232', '#CB2027'];

const MetricChart: React.FC<MetricChartProps> = ({
  activeGroup,
  subFilters,
  height = 500,
  startDate,
  endDate,
  data,
  loading,
  error,
}) => {
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const [chartOptions, setChartOptions] = useState<any>({});

  useEffect(() => {
    if (!data || loading) return;

    const seriesMap: Map<string, { name: string; unit: string; data: [number, number][] }> = new Map();

    data.forEach((item) => {
      if (subFilters.includes(item.measurement_type)) {
        const key = `${item.measurement_type}_${item.unit}`;
        if (!seriesMap.has(key)) {
          seriesMap.set(key, {
            name: `${item.measurement_type} (${item.unit})`,
            unit: item.unit,
            data: [],
          });
        }
        const series = seriesMap.get(key)!;
        const timestamp = new Date(item.recorded_at).getTime();
        series.data.push([timestamp, item.value]);
      }
    });

    const series = Array.from(seriesMap.values()).map((s, index) => ({
      type: 'line' as const,
      name: s.name,
      data: s.data.sort((a, b) => a[0] - b[0]),
      color: graphColors[index % graphColors.length],
    }));

    const yAxes = Array.from(seriesMap.values()).map((s, index) => ({
      title: {
        text: s.unit,
      },
      opposite: index % 2 === 1,
    }));

    setChartOptions({
      chart: {
        zoomType: 'x',
        height,
      },
      title: {
        text: `${activeGroup.charAt(0).toUpperCase() + activeGroup.slice(1)} Data`,
      },
      credits: {
        enabled: false,
      },
      legend: {
        enabled: series.length > 1,
      },
      tooltip: {
        shared: true,
        followPointer: true,
      },
      xAxis: {
        type: 'datetime',
      },
      yAxis: yAxes,
      series,
    });
  }, [data, loading, activeGroup, subFilters]);

  return (
    <div className="relative">
      {error && <div className="text-red-500">Error: {error.message}</div>}
      {loading && <div className="text-center"></div>}
      <HighchartsReact
        highcharts={Highcharts}
        options={chartOptions}
        ref={chartRef}
        containerProps={{ style: { height: `${height}px` } }}
      />
    </div>
  );
};

export default MetricChart;
