// This file defines the Download component for exporting filtered sensor or sampling data as a CSV file.
// It turns the active filters, groups, selected metrics/sites and dates into an export request; the backend builds
// the CSV. A small export downloads directly (/api/exports/sync); a large one is queued as a job that this
// component polls until its file is ready (/api/exports/jobs, through lib/exportJob). If the component leaves the
// page while it waits (switching tabs unmounts it), it stops polling, and when it comes back it says the export was
// left unfinished and Download Data picks the same job up again. A line under the button says which days it exports.

import React, { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Download as DownloadIcon, X } from "lucide-react";
import { Button } from "@/components/animations/button";
import {
  SENSOR_FILTER_CONFIG,
  SAMPLING_FILTER_CONFIG,
  CREEK_ID_MAP,
  SAMPLING_METRICS,
} from "@/components/config/filters";
import { dayStamp, siteDayBounds } from "@/utils/siteTime";
import { format } from "date-fns";
import {
  ExportError, ExportStopped, NetworkError, pollUntilReady, readError, readJson, request as requestWith,
} from "@/lib/exportJob";

const request = (input: string, init: RequestInit | undefined, signal: AbortSignal) =>
  requestWith((i, o) => fetch(i, o), input, init, signal);

// A queued export left unfinished when its Download button left the page, by tab, so the button can offer to pick
// it up when it comes back (as long as the filters and dates are still the same).
interface PendingJob { jobId: string; pollIntervalSeconds: number; selectionKey: string }
const leftUnfinished: Record<"sensor" | "sampling", PendingJob | null> = { sensor: null, sampling: null };

// For useSyncExternalStore's "is this the browser yet" (true in the browser, false on the server and in hydration)
const noSubscription = () => () => {};

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

// The picked day itself (toISOString() gave the UTC date, a day off for viewers east of UTC)
const formatDate = dayStamp;

const Download: React.FC<DownloadProps> = ({
  activeGroups,
  subFilters,
  activeCreeks = {},
  samplingSubFilters = {},
  startDate,
  endDate,
  isSampling = false,
}) => {
  const tab = isSampling ? "sampling" : "sensor";
  const [isExporting, setIsExporting] = useState(false);
  const [statusText, setStatusText] = useState<string>("");
  // The last export's failure, shown under the button until it is dismissed or a new export starts. It is not hidden
  // on a timer: exports can take a while, and someone who looked away would never learn why no file arrived.
  const [errorText, setErrorText] = useState<string>("");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  // The queued export still being waited on, kept so Try again can resume it instead of queueing a duplicate.
  const resumeJobRef = useRef<PendingJob | null>(null);
  // Aborted when the component unmounts, which stops the export it is running.
  const abortRef = useRef<AbortController | null>(null);
  // The selection of an export left unfinished on an earlier visit to this tab (see leftUnfinished): while it is still
  // the selection, a note says the export can be picked up.
  const [unfinishedKey, setUnfinishedKey] = useState<string | null>(() => leftUnfinished[tab]?.selectionKey ?? null);

  // Changes whenever the filters or dates change. (The parent passes new objects on every render, so the props
  // themselves can't be compared.)
  const selectionKey = JSON.stringify([
    isSampling,
    activeGroups,
    subFilters,
    activeCreeks,
    samplingSubFilters,
    startDate?.getTime() ?? null,
    endDate?.getTime() ?? null,
  ]);

  // A failure can arrive after the page was scrolled on (exports take a while), or the message can open below the
  // window's bottom edge: bring it into view.
  useEffect(() => {
    if (!errorText || isExporting) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    errorRef.current?.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [errorText, isExporting]);

  // An error about the previous selection no longer applies once the selection changes.
  useEffect(() => {
    setErrorText("");
  }, [selectionKey]);

  // Coming back to a tab whose export was left unfinished: offer to pick it up. Leaving: stop waiting, and remember
  // the queued job (if there is one) for next time.
  useEffect(() => {
    // handleDownload resumes it only while the selection is the same
    if (leftUnfinished[tab]) resumeJobRef.current = leftUnfinished[tab];
    leftUnfinished[tab] = null;
    return () => {
      if (abortRef.current && !abortRef.current.signal.aborted) {
        abortRef.current.abort();
        leftUnfinished[tab] = resumeJobRef.current;
      }
    };
  }, [tab]);

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
    if (!startDate || !endDate) {
      throw new ExportError("Start and end date are required");
    }

    // The picked days in Toronto time, wherever the viewer is
    const { start, end } = siteDayBounds(startDate, endDate);

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
        start,
        end,
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

    const weatherSelection = subFilters.weather || [];
    const qualitySelection = subFilters.quality || [];

    let selectedWeatherMetrics = activeGroups.weather
      ? weatherSelection
          .filter((label) => SENSOR_FILTER_CONFIG.weather.metrics.includes(label))
      : [];

    if (
      activeGroups.weather &&
      selectedWeatherMetrics.length === 0 &&
      (
        weatherSelection.length === 0 ||
        weatherSelection.includes(SENSOR_FILTER_CONFIG.weather.itemsLabel)
      )
    ) {
      selectedWeatherMetrics = SENSOR_FILTER_CONFIG.weather.metrics;
    }

    let selectedQualityMetrics = activeGroups.quality
      ? qualitySelection
          .filter((label) => SENSOR_FILTER_CONFIG.quality.metrics.includes(label))
      : [];

    if (
      activeGroups.quality &&
      selectedQualityMetrics.length === 0 &&
      (
        qualitySelection.length === 0 ||
        qualitySelection.includes(SENSOR_FILTER_CONFIG.quality.itemsLabel)
      )
    ) {
      selectedQualityMetrics = SENSOR_FILTER_CONFIG.quality.metrics;
    }

    const selectedLoggerMetrics = activeGroups.gauges
      ? gaugeSelection
          .filter((label) => SENSOR_FILTER_CONFIG.gauges.metrics.includes(label))
      : [];

    const toCanonicalMetric = (label: string) => METRIC_NAME_MAP[label] || label;
    const weatherMetricKeys = selectedWeatherMetrics.map(toCanonicalMetric);
    const qualityMetricKeys = selectedQualityMetrics.map(toCanonicalMetric);
    const loggerMetricKeys = selectedLoggerMetrics.map(toCanonicalMetric);

    const selectedMetrics = new Set<string>([
      ...weatherMetricKeys,
      ...qualityMetricKeys,
      ...loggerMetricKeys,
    ]);

    const groupMeasurementTypes: Record<string, string[]> = {};
    if (activeGroups.weather) groupMeasurementTypes.Weather = weatherMetricKeys;
    if (activeGroups.quality) groupMeasurementTypes.Quality = qualityMetricKeys;
    if (activeGroups.gauges) groupMeasurementTypes.Logger = loggerMetricKeys;

    const payload = {
      domain: "sensor",
      start,
      end,
      group_types: groupTypes,
      station_ids: selectedStationIds,
      measurement_types: Array.from(selectedMetrics),
      group_measurement_types: groupMeasurementTypes,
    };
    return payload;
  };

  const triggerDownload = async (response: Response, fallbackFileName: string, signal: AbortSignal) => {
    if (!response.ok) {
      throw new ExportError(await readError(response, "Failed to download export"));
    }

    let blob: Blob;
    try {
      blob = await response.blob();
    } catch {
      if (signal.aborted) throw new ExportStopped();
      throw new NetworkError(); // the connection dropped while the file was arriving
    }
    if (signal.aborted) throw new ExportStopped(); // left the page meanwhile: no download out of nowhere
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
    // Revoked later: Safari can cancel a download whose URL is revoked straight after the click
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  const handleDownload = async () => {
    if (isExporting) return; // the button stays focusable while busy, so guard against a second export
    const controller = new AbortController();
    abortRef.current = controller;
    const { signal } = controller;
    try {
      setIsExporting(true);
      setErrorText("");
      setUnfinishedKey(null);

      // A queued export whose progress checks failed is picked up again rather than queued twice,
      // as long as the filters and dates haven't changed since.
      let job = resumeJobRef.current?.selectionKey === selectionKey ? resumeJobRef.current : null;

      if (job) {
        setStatusText("Checking on the export");
      } else {
        setStatusText("Estimating export size");

        const payload = buildExportPayload();

        const estimateRes = await request("/api/exports/estimate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }, signal);

        if (!estimateRes.ok) {
          throw new ExportError(await readError(estimateRes, "Failed to estimate export size"));
        }

        const estimate = await readJson(estimateRes);
        const recommendedMode = estimate.recommended_mode || "async";

        if (recommendedMode === "sync") {
          setStatusText("Generating file");
          const syncRes = await request("/api/exports/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }, signal);
          await triggerDownload(syncRes, getFileName(), signal);
          return;
        }

        setStatusText("Queueing export job");
        const createJobRes = await request("/api/exports/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }, signal);

        if (!createJobRes.ok) {
          throw new ExportError(await readError(createJobRes, "Failed to queue export job"));
        }

        const created = await readJson(createJobRes);
        job = {
          jobId: String(created.job_id),
          pollIntervalSeconds: Number(created.poll_interval_seconds || 3),
          selectionKey,
        };
        resumeJobRef.current = job;
      }

      try {
        await pollUntilReady(job.jobId, job.pollIntervalSeconds, {
          fetchImpl: (i, o) => fetch(i, o),
          signal,
          onStatus: setStatusText,
        });
      } catch (error) {
        if (error instanceof ExportError && error.jobGone) resumeJobRef.current = null;
        throw error;
      }

      setStatusText("Downloading file");
      const downloadRes = await request(`/api/exports/jobs/${encodeURIComponent(job.jobId)}/download`, undefined, signal);
      // 404/410: the job or its file is gone (expired or cleaned up), so Try again must start a new export.
      if (downloadRes.status === 404 || downloadRes.status === 410) resumeJobRef.current = null;
      await triggerDownload(downloadRes, getFileName(), signal);
      resumeJobRef.current = null;
    } catch (error) {
      if (error instanceof ExportStopped || signal.aborted) return; // unmounted: nothing is shown any more
      console.error("[Download] ERROR:", error);
      // Only messages written for the user are shown; anything else (a bug, an odd reply) gets a plain one.
      setErrorText(error instanceof ExportError ? error.message : "Something went wrong. Please try again.");
    } finally {
      if (!signal.aborted) {
        setIsExporting(false);
        setStatusText("");
      }
      if (abortRef.current === controller) abortRef.current = null;
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

  // The days the export covers, in words: the picked days, not what a zoomed chart shows. Only once mounted: the page
  // is prerendered at build time with that day's default dates, and the browser's first render must match it.
  const mounted = useSyncExternalStore(noSubscription, () => true, () => false);
  const rangeText = mounted && startDate && endDate
    ? (dayStamp(startDate) === dayStamp(endDate)
      ? format(startDate, "MMM d, yyyy")
      : `${format(startDate, startDate.getFullYear() === endDate.getFullYear() ? "MMM d" : "MMM d, yyyy")} – ${format(endDate, "MMM d, yyyy")}`)
    : null;
  const rangeId = `download-range-${tab}`;

  // Moves focus back to the Download button when the alert (and the control in it that had focus) goes away.
  const focusButton = () => buttonRef.current?.focus();

  return (
    <div className="space-y-2">
      {/* Busy is aria-disabled rather than disabled: a disabled button can't hold focus, and Try again moves focus here */}
      <Button
        ref={buttonRef}
        onClick={handleDownload}
        disabled={!hasActiveData}
        aria-disabled={isExporting || undefined}
        aria-busy={isExporting || undefined}
        aria-describedby={rangeText ? rangeId : undefined}
        className="btn-mcmaster-primary w-full aria-disabled:pointer-events-none aria-disabled:opacity-50"
      >
        <DownloadIcon className="h-4 w-4 mr-2" />
        {isExporting ? statusText || "Preparing export" : "Download Data"}
      </Button>
      {rangeText && (
        <p id={rangeId} className="text-center text-xs text-muted">
          Exports {rangeText} (Eastern Time), the picked days, not a chart’s zoom
        </p>
      )}
      {unfinishedKey === selectionKey && !isExporting && (
        <p role="status" className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          An export was still being prepared when you left this tab. Press Download Data to pick it up.
        </p>
      )}
      {errorText && !isExporting && (
        <div
          ref={errorRef}
          className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          role="alert"
        >
          <div className="min-w-0 flex-1 break-words">
            <p className="font-medium">Download failed</p>
            <p>{errorText}</p>
            {hasActiveData && (
              <button
                type="button"
                onClick={() => {
                  focusButton();
                  handleDownload();
                }}
                className="mt-1 font-medium underline underline-offset-2 hover:text-red-900"
              >
                Try again
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              setErrorText("");
              focusButton();
            }}
            aria-label="Dismiss error"
            className="-m-1 shrink-0 rounded p-1 hover:bg-red-100 hover:text-red-900"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
};

export default Download;
