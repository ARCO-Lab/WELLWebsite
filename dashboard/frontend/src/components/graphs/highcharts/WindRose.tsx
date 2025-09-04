// This file defines the WindRose component for rendering wind rose diagrams using Highcharts.
// It bins wind speed and direction data, then displays frequency distributions in a polar column chart.

import React, { useEffect, useRef } from 'react';
import Highcharts from 'highcharts/highcharts-more';
import HighchartsReact from 'highcharts-react-official';
import { fabClasses } from '@mui/material';

const directions16 = [
  "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
];

const speedBins = [
  { name: "<0.5 m/s", from: 0, to: 0.5, color: '#3366CC' },
  { name: "0.5-2 m/s", from: 0.5, to: 2, color: '#DC3912' },
  { name: "2-4 m/s", from: 2, to: 4, color: '#FF9900' },
  { name: "4-6 m/s", from: 4, to: 6, color: '#109618' },
  { name: "6-8 m/s", from: 6, to: 8, color: '#990099' },
  { name: "8-10 m/s", from: 8, to: 10, color: '#0099C6' },
  { name: ">10 m/s", from: 10, to: Infinity, color: '#DD4477' }
];

interface WindDataPoint {
  direction: number;
  speed: number;
}

interface SpeedBin {
  name: string;
  from: number;
  to: number;
  color: string;
}

interface WindRoseSeries {
  name: string;
  color: string;
  data: number[];
  type: 'column';
}

function getWindRoseSeries(data: WindDataPoint[]): WindRoseSeries[] {
  // Bins wind data into direction and speed categories for charting
  const counts: number[][] = speedBins.map(() => Array(directions16.length).fill(0));
  let total = 0;

  data.forEach(({ direction, speed }) => {
    let dir = direction % 360;
    if (dir < 0) dir += 360;
    const dirIdx = Math.floor((dir + 11.25) / 22.5) % 16;
    const binIdx = speedBins.findIndex((bin: SpeedBin) => speed >= bin.from && speed < bin.to);

    if (binIdx !== -1) {
      counts[binIdx][dirIdx]++;
      total++;
    }
  });

  return speedBins.map((bin: SpeedBin, i: number) => ({
    name: bin.name,
    color: bin.color,
    data: counts[i].map((count: number) => total ? Math.round((count / total) * 100 * 10) / 10 : 0),
    type: 'column'
  }));
}

interface WindRoseProps {
  data: WindDataPoint[];
  title?: string;
  showLegend?: boolean;
}

const WindRose: React.FC<WindRoseProps> = ({ data, title, showLegend }) => {
  const series = getWindRoseSeries(data);

  const options = {
    chart: { 
      polar: true, 
      type: 'column',
      height: 400,
      style: { fontFamily: "'Poppins', Arial, sans-serif" }
    },
    title: {
      text: title || 'Wind Rose',
      style: { fontFamily: "'Poppins', Arial, sans-serif" }
    },
    subtitle: showLegend !== false
      ? {
          text: data.length > 0 ? `Based on ${data.length} observations` : 'No data available',
          style: { fontFamily: "'Poppins', Arial, sans-serif" }
        }
      : { text: "", style: { fontFamily: "'Poppins', Arial, sans-serif" } },
    xAxis: {
      categories: directions16,
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
