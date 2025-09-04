// This file defines the CreekGraph component for rendering time series charts for creek sampling sites.
// It groups data by site and displays a MetricChart for each selected site and metric.

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { SAMPLING_METRICS, SAMPLING_FILTER_CONFIG } from '@/components/config/filters';

const MetricChart = dynamic(() => import("@/components/graphs/highcharts/MetricChart"), {
  ssr: false,
});

interface Props {
  creekKey: keyof typeof SAMPLING_FILTER_CONFIG;
  subFilters: string[];
  startDate: Date | null;
  endDate: Date | null;
  modalOpen?: boolean;
  data: any[];
  loading?: boolean;
  error?: any;
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
    }, {} as Record<string, any[]>);
  }, [data]);

  return (
    <div className="p-4 bg-white rounded shadow">
      <h3 className="font-bold text-lg mb-2">{SAMPLING_FILTER_CONFIG[creekKey].label}</h3>
      
      {/* 3. Map over the selected sites and render a chart for each one */}
      {sites.map((siteId, index) => {
        const siteConfig = SAMPLING_FILTER_CONFIG[creekKey].sites;
        const siteName = siteConfig[siteId as keyof typeof siteConfig] || `Site ${siteId}`;
        const siteData = dataBySite[siteId] || [];


        return (
          <div key={siteId} className={index > 0 ? "mt-6 border-t pt-4" : ""}>
            <MetricChart
              activeGroup={siteName} // Use site name for the chart's context
              subFilters={metrics}
              height={300} // Reduced height for vertical stacking
              startDate={startDate}
              endDate={endDate}
              data={siteData} // Pass only this site's data
              loading={loading}
              error={error}
              modalOpen={modalOpen}
              showLegend={index === sites.length - 1} // Only show legend for the last chart
            />
          </div>
        );
      })}
    </div>
  );
};

export default CreekGraph;