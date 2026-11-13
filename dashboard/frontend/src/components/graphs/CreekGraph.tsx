// This file defines the CreekGraph component for rendering time series charts for creek sampling sites.
// It groups data by site and displays a SampleChart for each selected site and metric, under one legend for the card
// that shows each measurement's colour, line and marker and can show or hide it in every chart.

import dynamic from 'next/dynamic';
import { useMemo, useState } from 'react';
import { SAMPLING_METRICS, SAMPLING_FILTER_CONFIG } from '@/components/config/filters';
import type { SampledData } from '@/hooks/useSampledData';
import { displayUnit } from '@/utils/chartStyle';
import { SVG_DASH, samplingStyle, type SamplingStyle } from '@/utils/samplingStyle';

const SampleChart = dynamic(() => import("@/components/graphs/highcharts/SampleChart"), {
  ssr: false,
});

interface Props {
  creekKey: keyof typeof SAMPLING_FILTER_CONFIG;
  subFilters: string[];
  startDate: Date | null;
  endDate: Date | null;
  modalOpen?: boolean;
  data: SampledData[];
  loading?: boolean;
  error?: Error | null;
}

// A legend swatch: the measurement's line, dashes and marker, as drawn in the charts.
function Swatch({ style }: { style: SamplingStyle }) {
  const c = style.color;
  const shapes: Record<SamplingStyle["marker"], React.ReactNode> = {
    circle: <circle cx="11" cy="6" r="3.5" fill={c} />,
    square: <rect x="7.5" y="2.5" width="7" height="7" fill={c} />,
    diamond: <polygon points="11,1.5 15.5,6 11,10.5 6.5,6" fill={c} />,
    triangle: <polygon points="11,2 15,10 7,10" fill={c} />,
    "triangle-down": <polygon points="7,2 15,2 11,10" fill={c} />,
  };
  return (
    <svg width="22" height="12" viewBox="0 0 22 12" aria-hidden className="shrink-0">
      <line x1="0" y1="6" x2="22" y2="6" stroke={c} strokeWidth="2" strokeDasharray={SVG_DASH[style.dash]} />
      {shapes[style.marker]}
    </svg>
  );
}

const CreekGraph = ({
  creekKey,
  subFilters,
  startDate,
  endDate,
  modalOpen,
  data,
  loading = false,
  error = null,
}: Props) => {
  // 1. Determine which metrics and site IDs are selected
  const { metrics, sites } = useMemo(() => {
    const selectedMetrics: string[] = [];
    const selectedSites: string[] = [];
    const creekConfig = SAMPLING_FILTER_CONFIG[creekKey];
    const allSiteIdsForCreek = Object.keys(creekConfig.sites);

    if (subFilters.includes('All Sites')) {
      selectedSites.push(...allSiteIdsForCreek);
    } else {
      subFilters.forEach(filter => {
        if (allSiteIdsForCreek.includes(filter)) {
          selectedSites.push(filter);
        }
      });
    }
    

    subFilters.forEach(filter => {
      if (SAMPLING_METRICS.includes(filter)) {
        selectedMetrics.push(filter);
      }
    });

    return { metrics: selectedMetrics, sites: selectedSites };
  }, [subFilters, creekKey]);

  // 2. Group the raw data by site_id for efficient filtering
  const dataBySite = useMemo(() => {
    if (!data || !data.length) return {};
    return data.reduce((acc, curr) => {
        const siteId = String(curr.site_id);
        if (!acc[siteId]) acc[siteId] = [];
        acc[siteId].push(curr);
        return acc;
    }, {} as Record<string, SampledData[]>);
  }, [data]);

  // The legend: the selected measurements this card has rows for, in the filter's order, with the unit the data
  // names. Hidden ones stay listed (struck through) so they can be shown again.
  const legend = useMemo(() => {
    const units = new Map<string, string>();
    for (const row of data ?? []) {
      if (!units.has(row.measurement_type) && sites.includes(String(row.site_id))) units.set(row.measurement_type, row.unit);
    }
    return metrics.filter((m) => units.has(m)).map((m) => ({ metric: m, unit: displayUnit(units.get(m) ?? '') }));
  }, [data, metrics, sites]);
  const [hidden, setHidden] = useState<string[]>([]);
  const toggle = (metric: string) =>
    setHidden((prev) => (prev.includes(metric) ? prev.filter((m) => m !== metric) : [...prev, metric]));

  return (
    <div className="p-4 bg-white rounded shadow">
      <h3 className="font-bold text-lg mb-2">{SAMPLING_FILTER_CONFIG[creekKey].label}</h3>
      {legend.length > 0 && (
        <div className="mb-3">
          <p className="sr-only">Measurements shown: press one to show or hide it in every chart of this creek.</p>
          <ul className="flex flex-wrap gap-x-2 gap-y-1">
            {legend.map(({ metric, unit }) => {
              const off = hidden.includes(metric);
              return (
                <li key={metric}>
                  <button
                    type="button"
                    aria-pressed={!off}
                    onClick={() => toggle(metric)}
                    title={off ? `Show ${metric}` : `Hide ${metric}`}
                    className={`flex min-h-8 items-center gap-1.5 rounded px-1.5 text-left text-xs hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${off ? "text-muted line-through opacity-70" : "text-foreground"}`}
                  >
                    <Swatch style={samplingStyle(metric)} />
                    <span>{metric}{unit ? ` (${unit})` : ""}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {/* One announcement for the card; each chart's spinner is hidden from screen readers */}
      <p className="sr-only" role="status" aria-live="polite">{loading ? "Loading data…" : ""}</p>
      
      {/* 3. Map over the selected sites and render a chart for each one */}
      {sites.map((siteId, index) => {
        const siteConfig = SAMPLING_FILTER_CONFIG[creekKey].sites;
        const siteName = siteConfig[siteId as keyof typeof siteConfig] || `Site ${siteId}`;
        const siteData = dataBySite[siteId] || [];


        return (
          <div key={siteId} className={index > 0 ? "mt-6 border-t pt-4" : ""}>
            <SampleChart
              siteName={siteName}
              subFilters={metrics}
              hiddenMetrics={hidden}
              height={300} // Reduced height for vertical stacking
              startDate={startDate}
              endDate={endDate}
              data={siteData} // Pass only this site's data
              loading={loading}
              error={error}
              modalOpen={modalOpen}
            />
          </div>
        );
      })}
    </div>
  );
};

export default CreekGraph;