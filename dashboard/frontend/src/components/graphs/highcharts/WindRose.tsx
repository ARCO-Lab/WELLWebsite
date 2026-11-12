// This file defines the WindRose component: how often the wind blew from each of 16 directions at each speed, as a
// stacked polar column chart. The counts come binned from /api/windrose (see hooks/useWindRose), so no raw readings
// are downloaded for it.

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
  showLegend?: boolean;
}

const WindRose: React.FC<WindRoseProps> = ({ data, speed, title, showLegend }) => {
  const rose = data?.roses[speed];
  const total = rose?.total ?? 0;
  const series = (data?.speed_classes ?? []).map((c, i) => ({
    name: c.name,
    color: CLASS_COLORS[i % CLASS_COLORS.length],
    data: rose?.percent[i] ?? [],
    type: 'column' as const,
  }));
  const [chartHeight, setChartHeight] = useState(400);

  useEffect(() => {
    const updateHeight = () => {
      if (typeof window === 'undefined') return;
      if (window.innerWidth < 480) {
        setChartHeight(280);
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
    subtitle: showLegend !== false
      ? {
          text: total > 0 ? `Based on ${total.toLocaleString('en-US')} observations` : 'No data available',
          style: { fontFamily: "'Poppins', Arial, sans-serif" }
        }
      : { text: "", style: { fontFamily: "'Poppins', Arial, sans-serif" } },
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
      visible: showLegend !== false,
    },
    legend: {
      enabled: showLegend !== false,
      align: 'right',
      verticalAlign: 'top',
      y: 100,
      layout: 'vertical',
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
