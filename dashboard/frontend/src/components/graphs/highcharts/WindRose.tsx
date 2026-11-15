// This file defines the WindRose component: how often the wind blew from each of 16 directions at each speed, as a
// stacked polar column chart. The counts come binned from /api/windrose (see hooks/useWindRose), so no raw readings
// are downloaded for it. Its legend (the speed classes), its scale and the period it covers are always shown: a rose
// without them can't be read.
//
// Look: one sequential ramp, light (calm) to dark (strong), so faster wind reads as darker; a faint grid; the four
// cardinal points in bold; the share of calm readings (the slowest class, which has no real direction) in the middle;
// a tooltip per direction listing each speed class; and a short grow-in, skipped with reduced motion. The numbers
// are the API's, unchanged.

import React, { useEffect, useState } from 'react';
import Highcharts from 'highcharts/highcharts-more';
import HighchartsReact from 'highcharts-react-official';
import type { WindRoseResponse } from '@/hooks/useWindRose';
import { calmPercent } from '@/utils/windRose';

const FONT = "'Poppins', Arial, sans-serif";
// Slowest to fastest: light sky blue to deep navy, each step visibly darker. Every band also has a dark hairline
// (see plotOptions), so even the lightest stands out at 3:1 or more against the pale pane behind the rose.
const RAMP = ['#8cc8e6', '#5fb0d8', '#3a96c6', '#2a7bb0', '#1c6096', '#13487a', '#0b3157'];
const CARDINAL = new Set(['N', 'E', 'S', 'W']);

interface WindRoseProps {
  data: WindRoseResponse | null;
  speed: 'Wind Speed' | 'Gust Speed';
  title?: string;
  period?: string; // the dates it covers, e.g. "Nov 10 00:00 – Nov 11 16:00"
}

const reducedMotion = () => typeof window !== 'undefined' && (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);


const WindRose: React.FC<WindRoseProps> = ({ data, speed, title, period }) => {
  const rose = data?.roses[speed];
  const total = rose?.total ?? 0;
  const calm = calmPercent(data, speed);
  const series = (data?.speed_classes ?? []).map((c, i) => ({
    name: c.name,
    color: RAMP[Math.min(i, RAMP.length - 1)],
    data: rose?.percent[i] ?? [],
    type: 'column' as const,
  }));
  const [chartHeight, setChartHeight] = useState(400);
  const [narrow, setNarrow] = useState(false); // the legend goes under the rose on a phone

  useEffect(() => {
    const updateHeight = () => {
      if (typeof window === 'undefined') return;
      setNarrow(window.innerWidth < 640);
      setChartHeight(window.innerWidth < 480 ? 400 : window.innerWidth < 768 ? 340 : 420);
    };
    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, []);

  const options: Highcharts.Options = {
    chart: {
      polar: true,
      type: 'column',
      height: chartHeight,
      style: { fontFamily: FONT },
      backgroundColor: 'transparent',
      events: {
        // The calm share, centred in the rose (redrawn with it, so it stays centred when the size changes)
        render(this: Highcharts.Chart & { calmLabel?: Highcharts.SVGElement }) {
          this.calmLabel?.destroy();
          this.calmLabel = undefined;
          if (calm === null) return;
          const cx = this.plotLeft + this.plotWidth / 2, cy = this.plotTop + this.plotHeight / 2;
          this.calmLabel = this.renderer
            .text(`<tspan style="font-size:14px;font-weight:600">${calm.toFixed(calm < 10 ? 1 : 0)}%</tspan><tspan x="0" dy="12" style="font-size:9px">calm</tspan>`, 0, 0)
            .attr({ align: 'center', zIndex: 6 })
            .css({ color: '#374151', fontFamily: FONT })
            .add();
          this.calmLabel.attr({ x: cx, y: cy - 1 });
        },
      },
    },
    title: { text: title || 'Wind Rose', style: { fontFamily: FONT, fontSize: '15px', fontWeight: '600', color: '#111827' } },
    subtitle: {
      text: [period, total > 0 ? `${total.toLocaleString('en-US')} readings` : 'No readings in this period'].filter(Boolean).join(' · '),
      style: { fontFamily: FONT, color: '#4b5563' },
    },
    credits: { enabled: false },
    // A hole in the middle for the calm share; a faint disc behind the rose
    pane: { size: '82%', innerSize: '18%', background: [{ backgroundColor: '#f9fafb', borderWidth: 0, outerRadius: '100%', innerRadius: '18%' }] },
    xAxis: {
      categories: data?.sectors ?? [],
      tickmarkPlacement: 'on',
      lineWidth: 0,
      gridLineColor: '#e5e7eb',
      gridLineDashStyle: 'Dot',
      labels: {
        distance: 12,
        // N, E, S and W in bold and dark; the 12 between them smaller and grey
        formatter() {
          const v = String(this.value);
          return CARDINAL.has(v)
            ? `<span style="font-weight:700;font-size:13px;fill:#111827">${v}</span>`
            : `<span style="font-size:10px;fill:#6b7280">${v}</span>`;
        },
      },
    },
    yAxis: {
      min: 0,
      endOnTick: false,
      showLastLabel: true,
      gridLineColor: '#e5e7eb',
      title: { text: undefined },
      labels: { format: '{value}%', style: { fontFamily: FONT, fontSize: '9px', color: '#6b7280' } },
      reversedStacks: false,
    },
    legend: {
      enabled: true,
      title: { text: 'Speed', style: { fontFamily: FONT, fontSize: '11px', fontWeight: '600', color: '#374151' } },
      align: narrow ? 'center' : 'right',
      verticalAlign: narrow ? 'bottom' : 'middle',
      layout: narrow ? 'horizontal' : 'vertical',
      symbolRadius: 2,
      itemMarginBottom: 3,
      itemStyle: { fontFamily: FONT, fontSize: '11px', fontWeight: 'normal', color: '#374151' },
    },
    // One tooltip per direction: its total share, then each speed class's share there
    tooltip: {
      shared: true,
      useHTML: true,
      backgroundColor: 'rgba(255,255,255,0.97)',
      borderColor: '#d1d5db',
      borderRadius: 6,
      shadow: false,
      style: { fontFamily: FONT, fontSize: '12px' },
      formatter(this: Highcharts.Point) {
        const all = this.points ?? [this];
        const sum = all.reduce((a, p) => a + (p.y ?? 0), 0);
        const rows = all.filter((p) => (p.y ?? 0) > 0).map((p) =>
          `<tr><td><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${p.color};margin-right:6px"></span>${p.series.name}</td>`
          + `<td style="text-align:right;padding-left:12px">${(p.y ?? 0).toFixed(1)}%</td></tr>`).join('');
        return `<div style="font-weight:600;margin-bottom:4px">From ${String(this.key ?? this.x)}: ${sum.toFixed(1)}%</div><table>${rows}</table>`;
      },
    },
    plotOptions: {
      column: {
        stacking: 'normal',
        shadow: false,
        groupPadding: 0,
        pointPadding: 0.04,
        borderWidth: 0.6,
        borderColor: '#1f3f5c', // a hairline around each band (3:1 or more against the pane)
        pointPlacement: 'on',
        animation: reducedMotion() ? false : { duration: 700 },
        states: { inactive: { opacity: 0.25 } },
      },
    },
    series,
  };

  return (
    <div>
      <HighchartsReact highcharts={Highcharts} options={options} />
    </div>
  );
};

export default WindRose;
