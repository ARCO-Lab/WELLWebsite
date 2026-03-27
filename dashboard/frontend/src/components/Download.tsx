// This file defines the Download component for exporting filtered sensor or sampling data as a CSV file.
// It builds the CSV structure based on active filters, groups, and selected metrics/sites.

import React, { useState } from "react";
import { Download as DownloadIcon } from "lucide-react";
import { Button } from "@/components/animations/button";
import {
  SENSOR_FILTER_CONFIG,
  SAMPLING_FILTER_CONFIG,
  CREEK_ID_MAP,
  SAMPLING_METRICS,
} from "@/components/config/filters";

interface DownloadProps {
  activeGroups: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  subFilters: {
    weather: string[];
    quality: string[];
    gauges: string[];
  };
  activeCreeks?: { [key: string]: boolean };
  samplingSubFilters?: { [key: string]: string[] };
  startDate: Date | null;
  endDate: Date | null;
  data: {
    measurement_type: string;
    value: number;
    unit: string;
    recorded_at: string;
    group_type?: string;
    logger_id?: string;
    site_id?: string;
    station_id?: string;
    creek_id?: string;
  }[];
  isSampling?: boolean;
}

const METRIC_NAME_MAP: Record<string, string> = {
  Rainfall: "Rain",
  "Total Dissolved Solids (TDS)": "TDS",
  "Dissolved Oxygen (ODO)": "ODO",
  "Dissolved Oxygen Saturation (ODOSat)": "ODOSat",
  "Total Suspended Solids (TSS)": "TSS",
  // Add more as needed
};

const formatDate = (date: Date) => {
  return date.toISOString().split("T")[0].replace(/-/g, "");
};

const Download: React.FC<DownloadProps> = ({
  activeGroups,
  subFilters,
  activeCreeks = {},
  samplingSubFilters = {},
  startDate,
  endDate,
  data,
  isSampling = false,
}) => {
  const [isExporting, setIsExporting] = useState(false);
  const [statusText, setStatusText] = useState<string>("");

  const getFileName = () => {
    if (isSampling) {
      const activeCreekLabels = Object.entries(activeCreeks)
        .filter(([_, active]) => active)
        .map(([creekKey]) => {
          const creek = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
          return creek?.label || creekKey;
        });

      const parts = ["WELLAncasterWatershed", ...activeCreekLabels];
      const from = formatDate(startDate ?? new Date());
      const to = formatDate(endDate ?? new Date());
      return `${parts.join("_")}_${from}_${to}.csv`;
    }

    const parts = ["WELLWestCampus"];
    if (activeGroups.gauges) parts.push("WaterLogger");
    if (activeGroups.quality) parts.push("WaterQuality");
    if (activeGroups.weather) parts.push("WeatherStation");
    const from = formatDate(startDate ?? new Date());
    const to = formatDate(endDate ?? new Date());
    return `${parts.join("_")}_${from}_${to}.csv`;
  };

  const buildExportPayload = () => {
    console.log("[buildExportPayload] called");
    console.log("[buildExportPayload] activeGroups state:", activeGroups);
    console.log("[buildExportPayload] subFilters state:", subFilters);
    if (!startDate || !endDate) {
      throw new Error("Start and end date are required");
    }

    const start = new Date(startDate);
    start.setHours(0, 0, 0, 0);

    const end = new Date(endDate);
    end.setHours(23, 59, 59, 999);

    if (isSampling) {
      const selectedCreeks = Object.entries(activeCreeks)
        .filter(([_, active]) => active)
        .map(([creekKey]) => creekKey);

      const siteIds = new Set<string>();
      const measurementTypes = new Set<string>();

      selectedCreeks.forEach((creekKey) => {
        const filters = samplingSubFilters[creekKey] || [];
        const creekConfig = SAMPLING_FILTER_CONFIG[creekKey as keyof typeof SAMPLING_FILTER_CONFIG];
        const allSites = Object.keys(creekConfig?.sites || {});

        if (filters.includes("All Sites")) {
          allSites.forEach((site) => siteIds.add(site));
        } else {
          filters.filter((f) => allSites.includes(f)).forEach((site) => siteIds.add(site));
        }

        filters.filter((f) => SAMPLING_METRICS.includes(f)).forEach((metric) => measurementTypes.add(metric));
      });

      return {
        domain: "sampling",
        start: start.toISOString(),
        end: end.toISOString(),
        creek_ids: selectedCreeks.map((creekKey) => CREEK_ID_MAP[creekKey as keyof typeof CREEK_ID_MAP]),
        site_ids: Array.from(siteIds),
        measurement_types: Array.from(measurementTypes),
      };
    }

    const groupTypes: string[] = [];
    if (activeGroups.weather) groupTypes.push("Weather");
    if (activeGroups.quality) groupTypes.push("Quality");
    if (activeGroups.gauges) groupTypes.push("Logger");

    const knownLoggerIds = Object.keys(SENSOR_FILTER_CONFIG.gauges.sites);
    const gaugeSelection = subFilters.gauges || [];
    const selectedStationIds = gaugeSelection.includes("All Loggers")
      ? knownLoggerIds
      : gaugeSelection.filter((entry) => knownLoggerIds.includes(entry));

    const selectedWeatherMetrics = activeGroups.weather
      ? (subFilters.weather || [])
          .filter((label) => SENSOR_FILTER_CONFIG.weather.metrics.includes(label))
          .map((label) => METRIC_NAME_MAP[label] || label)
      : [];

    const selectedQualityMetrics = activeGroups.quality
      ? (subFilters.quality || [])
          .filter((label) => SENSOR_FILTER_CONFIG.quality.metrics.includes(label))
          .map((label) => METRIC_NAME_MAP[label] || label)
      : [];

    const selectedLoggerMetrics = activeGroups.gauges
      ? gaugeSelection
          .filter((label) => SENSOR_FILTER_CONFIG.gauges.metrics.includes(label))
          .map((label) => METRIC_NAME_MAP[label] || label)
      : [];

    const selectedMetrics = new Set<string>([
      ...selectedWeatherMetrics,
      ...selectedQualityMetrics,
      ...selectedLoggerMetrics,
    ]);

    const groupMeasurementTypes: Record<string, string[]> = {};
    if (activeGroups.weather) groupMeasurementTypes.Weather = selectedWeatherMetrics;
    if (activeGroups.quality) groupMeasurementTypes.Quality = selectedQualityMetrics;
    if (activeGroups.gauges) groupMeasurementTypes.Logger = selectedLoggerMetrics;

    return {
      domain: "sensor",
      start: start.toISOString(),
      end: end.toISOString(),
      group_types: groupTypes,
      station_ids: selectedStationIds,
      measurement_types: Array.from(selectedMetrics),
      group_measurement_types: groupMeasurementTypes,
    };
  };

  const triggerDownload = async (response: Response, fallbackFileName: string) => {
    if (!response.ok) {
      let err = "Failed to download export";
      try {
        const payload = await response.json();
        err = payload.error || err;
      } catch {
        // Keep fallback error.
      }
      throw new Error(err);
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const fileNameMatch = disposition.match(/filename="?([^";]+)"?/i);
    const fileName = fileNameMatch?.[1] || fallbackFileName;

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const pollUntilReady = async (jobId: string, pollIntervalSeconds: number) => {
    for (;;) {
      const statusRes = await fetch(`/api/exports/jobs/${encodeURIComponent(jobId)}`);
      if (!statusRes.ok) {
        throw new Error("Failed to poll export job status");
      }

      const status = await statusRes.json();
      const progress = typeof status.progress_pct === "number" ? status.progress_pct.toFixed(1) : "0.0";
      setStatusText(`Preparing export (${status.status}${status.status === "running" ? ` ${progress}%` : ""})`);

      if (status.status === "ready") {
        return;
      }
      if (status.status === "failed") {
        throw new Error(status.error_message || "Export failed");
      }
      if (status.status === "expired") {
        throw new Error("Export expired before download");
      }

      await new Promise((resolve) => setTimeout(resolve, Math.max(1, pollIntervalSeconds) * 1000));
    }
  };

  const handleDownload = async () => {
    try {
      setIsExporting(true);
      setStatusText("Estimating export size");
      console.log("[Download] Starting export...");

      const payload = buildExportPayload();
      console.log("[Download] Payload:", payload);

      console.log("[Download] Calling /api/exports/estimate...");
      const estimateRes = await fetch("/api/exports/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      console.log("[Download] Estimate response status:", estimateRes.status);

      if (!estimateRes.ok) {
        const estimateError = await estimateRes.json();
        throw new Error(estimateError.error || "Failed to estimate export size");
      }

      const estimate = await estimateRes.json();
      console.log("[Download] Estimate result:", estimate);
      const recommendedMode = estimate.recommended_mode || "async";

      if (recommendedMode === "sync") {
        setStatusText("Generating file");
        console.log("[Download] Using SYNC mode");
        const syncRes = await fetch("/api/exports/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        console.log("[Download] Sync response status:", syncRes.status);
        await triggerDownload(syncRes, getFileName());
        setStatusText("");
        return;
      }

      console.log("[Download] Using ASYNC mode");
      setStatusText("Queueing export job");
      const createJobRes = await fetch("/api/exports/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      console.log("[Download] Create job response status:", createJobRes.status);

      if (!createJobRes.ok) {
        const createErr = await createJobRes.json();
        throw new Error(createErr.error || "Failed to queue export job");
      }

      const created = await createJobRes.json();
      console.log("[Download] Job created:", created);
      const jobId = created.job_id as string;
      const pollInterval = Number(created.poll_interval_seconds || 3);
      await pollUntilReady(jobId, pollInterval);

      setStatusText("Downloading file");
      const downloadRes = await fetch(`/api/exports/jobs/${encodeURIComponent(jobId)}/download`);
      await triggerDownload(downloadRes, getFileName());
      setStatusText("");
    } catch (error: any) {
      console.error("[Download] ERROR:", error);
      console.error("[Download] Error message:", error?.message);
      setStatusText(error?.message || "Download failed");
      window.setTimeout(() => setStatusText(""), 6000);
    } finally {
      setIsExporting(false);
    }
  };

  // Only allow download if at least one group or creek has active data
  const hasActiveData =
    !!startDate &&
    !!endDate &&
    (() => {
      if (isSampling) {
        return Object.entries(activeCreeks).some(
          ([creekKey, active]) => active && (samplingSubFilters[creekKey]?.length || 0) > 0
        );
      } else {
        return (Object.keys(activeGroups) as Array<keyof typeof activeGroups>).some(
          (group) => activeGroups[group] && subFilters[group].length > 0
        );
      }
    })();

  return (
    <Button
      onClick={handleDownload}
      disabled={!hasActiveData || isExporting}
      className="btn-mcmaster-primary w-full"
    >
      <DownloadIcon className="h-4 w-4 mr-2" />
      {isExporting ? statusText || "Preparing export" : "Download Data"}
    </Button>
  );
};

export default Download;
