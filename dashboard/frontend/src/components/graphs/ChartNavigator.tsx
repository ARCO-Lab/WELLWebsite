// A thin overview strip under the window bar in the larger view: one series across all the picked days, with the
// part the charts show left clear and the rest shaded. Drag across it to show that part; click it to move the
// window there. It draws the overview the charts already have, so it makes no request of its own. The range
// buttons in the bar do the same from the keyboard, so the strip itself is hidden from screen readers.

import React, { useEffect, useMemo, useRef, useState } from "react";
import Highcharts from "highcharts";
import HighchartsReact from "highcharts-react-official";
import { useChartView } from "@/hooks/useChartSeries";
import { TIME_ZONE, composePoints } from "@/utils/chartWindow";
import { seriesColor } from "@/utils/chartStyle";

// The series each group's strip draws, first one found wins.
const PREFERRED: Record<string, { group: string; measurements: string[] }> = {
  weather: { group: "Weather", measurements: ["Air Temperature", "Relative Humidity", "Pressure"] },
  quality: { group: "Quality", measurements: ["Water Temperature", "ODO", "Conductivity"] },
  gauges: { group: "Logger", measurements: ["Water Surface Elevation", "Water Temperature"] },
};

const SHADE = "rgba(15, 23, 42, 0.12)";

const ChartNavigator: React.FC<{ group: "weather" | "quality" | "gauges" }> = ({ group }) => {
  const view = useChartView();
  const chartRef = useRef<HighchartsReact.RefObject>(null);
  const showRef = useRef(view.showWindow);
  showRef.current = view.showWindow;
  const shownRef = useRef(view.viewWindow ?? view.range);
  shownRef.current = view.viewWindow ?? view.range;

  const pick = PREFERRED[group];
  const series = useMemo(() => {
    const ov = view.overview;
    if (!ov) return null;
    const ofGroup = ov.series.filter((s) => s.group_type === pick.group);
    for (const m of pick.measurements) {
      const s = ofGroup.find((x) => x.measurement_type === m);
      if (s) return { name: m, data: composePoints(s, ov.bucketS) };
    }
    const s = ofGroup[0];
    return s ? { name: s.measurement_type, data: composePoints(s, ov.bucketS) } : null;
  }, [view.overview, pick]);

  const [options] = useState<Highcharts.Options>(() => ({
    time: { timezone: TIME_ZONE },
    accessibility: { enabled: false }, // the bar's buttons do this for keyboards and screen readers
    chart: {
      height: 64,
      spacing: [4, 8, 4, 8],
      animation: false,
      style: { fontFamily: "Poppins, Arial, sans-serif" },
      zooming: { type: "x", resetButton: { theme: { style: { display: "none" } } } },
      events: {
        selection(e) {
          if (e.xAxis?.[0]) showRef.current({ start: e.xAxis[0].min, end: e.xAxis[0].max });
          return false;
        },
        click(e) {
          // Move the window (keeping its width) so it is centred where the strip was clicked
          const x = (e as unknown as { xAxis: { value: number }[] }).xAxis?.[0]?.value;
          const w = shownRef.current;
          if (x === undefined || !w) return;
          const half = (w.end - w.start) / 2;
          showRef.current({ start: x - half, end: x + half });
        },
      },
    },
    title: { text: undefined },
    credits: { enabled: false },
    legend: { enabled: false },
    tooltip: { enabled: false },
    xAxis: {
      type: "datetime", tickLength: 0, lineColor: "#d1d5db", labels: { style: { fontSize: "9px" } },
      dateTimeLabelFormats: { hour: "%H:%M", day: "%b %e", week: "%b %e", month: "%b '%y" },
    },
    yAxis: { visible: false },
    plotOptions: {
      series: { animation: false, enableMouseTracking: false, lineWidth: 1, marker: { enabled: false } },
      area: { threshold: null }, // scaled to the data, not filled down from 0
    },
    series: [],
  }));

  useEffect(() => {
    const chart = chartRef.current?.chart;
    if (!chart) return;
    chart.update({
      series: series ? [{ type: "area", name: series.name, data: series.data, color: seriesColor(series.name), fillOpacity: 0.15 }] : [],
    }, true, true, false);
  }, [series]);

  const range = view.range;
  const win = view.viewWindow;
  useEffect(() => {
    const axis = chartRef.current?.chart?.xAxis[0];
    if (!axis || !range) return;
    // The picked days (as options: Axis.update would drop extremes set with setExtremes), with what is outside the
    // window shaded
    axis.update({
      min: range.start,
      max: range.end,
      plotBands: win
        ? [{ from: range.start, to: win.start, color: SHADE }, { from: win.end, to: range.end, color: SHADE }]
        : [],
      plotLines: win
        ? [{ value: win.start, color: "#64748b", width: 1 }, { value: win.end, color: "#64748b", width: 1 }]
        : [],
    }, true);
  }, [range, win, series]);

  if (!range || !view.overview) return null;
  return (
    <div className="mt-2" aria-hidden="true" data-testid="chart-navigator">
      <p className="mb-0.5 text-[11px] text-muted">
        Overview{series ? `: ${series.name}` : ""} · <span className="pointer-coarse:hidden">drag or click to pick the time shown</span>
        <span className="hidden pointer-coarse:inline">tap to move the time shown</span>
      </p>
      <HighchartsReact highcharts={Highcharts} options={options} allowChartUpdate={false} ref={chartRef}
        containerProps={{ style: { height: "64px", cursor: "crosshair" } }} />
    </div>
  );
};

export default ChartNavigator;
