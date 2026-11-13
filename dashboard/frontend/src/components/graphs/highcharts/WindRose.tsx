// This file defines the WindRose component: how often the wind blew from each of 16 directions at each speed, as a
// stacked polar column chart. The counts come binned from /api/windrose (see hooks/useWindRose), so no raw readings
// are downloaded for it. Its legend (the speed classes), its scale and the period it covers are always shown: a rose
// without them can't be read.

import React, { useEffect, useState } from 'react';
import Highcharts from 'highcharts/highcharts-more';
import HighchartsReact from 'highcharts-react-official';
import type { WindRoseResponse } from '@/hooks/useWindRose';

// One colour per speed class, slowest first (the backend's speed_classes, in order)
const CLASS_COLORS = ['#3366CC', '#DC3912', '#FF9900', '#109618', '#990099', '#0099C6', '#DD4477'];

interface WindRoseProps {
  data: WindRoseResponse | null;
  speed: 'Wind Speed' | 'Gust Speed';
  title?: string;
  period?: string; // the dates it covers, e.g. "Nov 10 00:00 – Nov 11 16:00"
}

const WindRose: React.FC<WindRoseProps> = ({ data, speed, title, period }) => {
  const rose = data?.roses[speed];
  const total = rose?.total ?? 0;
  const series = (data?.speed_classes ?? []).map((c, i) => ({
    name: c.name,
    color: CLASS_COLORS[i % CLASS_COLORS.length],
    data: rose?.percent[i] ?? [],
    type: 'column' as const,
  }));
  const [chartHeight, setChartHeight] = useState(400);
  const [narrow, setNarrow] = useState(false); // the legend goes under the rose on a phone

  useEffect(() => {
    const updateHeight = () => {
      if (typeof window === 'undefined') return;
      setNarrow(window.innerWidth < 640);
      if (window.innerWidth < 480) {
        setChartHeight(380);
      } else if (window.innerWidth < 768) {
        setChartHeight(320);
      } else {
        setChartHeight(400);
      }
    };

    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, []);

  const options = {
    chart: { 
      polar: true, 
      type: 'column',
      height: chartHeight,
      style: { fontFamily: "'Poppins', Arial, sans-serif" }
    },
    title: {
      text: title || 'Wind Rose',
      style: { fontFamily: "'Poppins', Arial, sans-serif" }
    },
    credits: { enabled: false },
    subtitle: {
      text: [period, total > 0 ? `${total.toLocaleString('en-US')} readings` : 'No readings in this period'].filter(Boolean).join(' · '),
      style: { fontFamily: "'Poppins', Arial, sans-serif" }
    },
    xAxis: {
      categories: data?.sectors ?? [],
      tickmarkPlacement: 'on',
      lineWidth: 0,
      labels: { style: { fontFamily: "'Poppins', Arial, sans-serif" } }
    },
    yAxis: {
      min: 0,
      endOnTick: false,
      showLastLabel: true,
      title: { text: 'Frequency (%)', style: { fontFamily: "'Poppins', Arial, sans-serif" } },
      labels: { format: '{value}%', style: { fontFamily: "'Poppins', Arial, sans-serif" } },
      reversedStacks: false,
    },
    legend: {
      enabled: true,
      align: narrow ? 'center' : 'right',
      verticalAlign: narrow ? 'bottom' : 'top',
      y: narrow ? 0 : 100,
      layout: narrow ? 'horizontal' : 'vertical',
      itemStyle: { fontFamily: "'Poppins', Arial, sans-serif" }
    },
    tooltip: { 
      valueSuffix: '%',
      shared: false
    },
    plotOptions: {
      series: {
        stacking: 'normal',
        shadow: false,
        groupPadding: 0,
        pointPlacement: 'on',
        allowPointSelection: true,
        states: {
          inactive: {
            opacity: 0.15
          }
        }

      }
    },
    series: series
  };

  return (
    <div>
      <HighchartsReact
        highcharts={Highcharts}
        options={options}
      />
    </div>
  );
};

export default WindRose;
