// This file defines the Download component for exporting filtered sensor or sampling data as a CSV file.
// It builds the CSV structure based on active filters, groups, and selected metrics/sites.

import React, { useEffect, useRef, useState } from "react";
import { Download as DownloadIcon, X } from "lucide-react";
import { Button } from "@/components/animations/button";
import {
  SENSOR_FILTER_CONFIG,
  SAMPLING_FILTER_CONFIG,
  CREEK_ID_MAP,
  SAMPLING_METRICS,
} from "@/components/config/filters";
import { pickedDaysRange } from "@/utils/chartWindow";

// An error whose message was written for the user; any other error is shown as a generic message.
class ExportError extends Error {}

// fetch() itself failed: the request got no reply (offline, DNS failure, connection reset).
class NetworkError extends ExportError {
  constructor() {
    super("Could not reach the server. Check your connection.");
  }
}

// Shown for a queued export that failed on the server. The job's own error_message isn't shown: the server
// keeps only safe text there, but this way nothing internal can reach the page whatever the backend stores.
const JOB_FAILED_MESSAGE = "The server couldn't build this export. Please try again later.";
const RETRYABLE_STATUSES = [502, 503, 504];
const POLL_RETRY_DELAYS_S = [2, 4, 8, 16]; // waits before each retry of a status check that failed
const POLL_MAX_MINUTES = 30; // stop waiting on a job after this long (Try again resumes it)

const sleep = (seconds: number) => new Promise((resolve) => setTimeout(resolve, seconds * 1000));

// fetch(), with the errors fetch() itself throws turned into a NetworkError.
async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new NetworkError();
  }
}

// The JSON body of a successful reply. A proxy or server error page can arrive with a 200 too.
async function readJson(res: Response) {
  try {
    return await res.json();
  } catch {
    throw new ExportError("The server sent an unexpected reply.");
  }
}

// The message for a failed API reply: the JSON body's `error` if there is one, otherwise the fallback and status.
// The proxies pass the backend's reply through, so an unexpected failure can be an HTML page instead of JSON.
async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.error === "string" && body.error) return body.error;
  } catch {
    // Not JSON; use the fallback.
  }
  return `${fallback} (HTTP ${res.status})`;
}

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

// YYYYMMDD of a picked day. The date pickers hand over Dates whose own calendar day is the day picked, so read that
// day, not the UTC one (toISOString gave the day before in Tokyo, where local midnight is still yesterday in UTC).
const formatDate = (date: Date) =>
  `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, "0")}${String(date.getDate()).padStart(2, "0")}`;

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
  // The last export's failure, shown under the button until it is dismissed or a new export starts. It is not hidden
  // on a timer: exports can take a while, and someone who looked away would never learn why no file arrived.
  const [errorText, setErrorText] = useState<string>("");
  const buttonRef = useRef<HTMLButtonElement>(null);
  // The queued export still being waited on, kept so Try again can resume it instead of queueing a duplicate.
  const resumeJobRef = useRef<{ jobId: string; pollIntervalSeconds: number; selectionKey: string } | null>(null);

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

  // An error about the previous selection no longer applies once the selection changes.
  useEffect(() => {
    setErrorText("");
  }, [selectionKey]);

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

    // The picked days in site time (Toronto midnight to the last millisecond of the last day), whatever the
    // browser's time zone: local midnight in Tokyo or London is a different instant.
    const days = pickedDaysRange(startDate, endDate);
    const start = new Date(days.start);
    const end = new Date(days.end - 1);

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
      start: start.toISOString(),
      end: end.toISOString(),
      group_types: groupTypes,
      station_ids: selectedStationIds,
      measurement_types: Array.from(selectedMetrics),
      group_measurement_types: groupMeasurementTypes,
    };
    return payload;
  };

  const triggerDownload = async (response: Response, fallbackFileName: string) => {
    if (!response.ok) {
      throw new ExportError(await readError(response, "Failed to download export"));
    }

    let blob: Blob;
    try {
      blob = await response.blob();
    } catch {
      throw new NetworkError(); // the connection dropped while the file was arriving
    }
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

  // Waits for a queued export to finish. A status check that gets no reply or a 502/503/504 (the server
  // restarting or briefly overloaded) is retried with growing waits, since the job keeps running meanwhile;
  // a 404 or a failed/expired job is final.
  const pollUntilReady = async (jobId: string, pollIntervalSeconds: number) => {
    const deadline = Date.now() + POLL_MAX_MINUTES * 60_000;
    let retries = 0;
    for (;;) {
      if (Date.now() > deadline) {
        throw new ExportError("The export is taking longer than expected. Press Try again to keep waiting for it.");
      }

      let statusRes: Response | null = null;
      try {
        statusRes = await request(`/api/exports/jobs/${encodeURIComponent(jobId)}`);
      } catch (error) {
        if (!(error instanceof NetworkError)) throw error;
      }
      if (!statusRes || RETRYABLE_STATUSES.includes(statusRes.status)) {
        if (retries >= POLL_RETRY_DELAYS_S.length) {
          throw statusRes
            ? new ExportError(await readError(statusRes, "Failed to check the export's progress"))
            : new NetworkError();
        }
        setStatusText("Reconnecting");
        await sleep(POLL_RETRY_DELAYS_S[retries++]);
        continue;
      }
      if (!statusRes.ok) {
        if (statusRes.status === 404) resumeJobRef.current = null;
        throw new ExportError(await readError(statusRes, "Failed to check the export's progress"));
      }
      retries = 0;

      const status = await readJson(statusRes);
      const progress = typeof status.progress_pct === "number" ? status.progress_pct.toFixed(1) : "0.0";
      setStatusText(`Preparing export (${status.status}${status.status === "running" ? ` ${progress}%` : ""})`);

      if (status.status === "ready") {
        return;
      }
      if (status.status === "failed") {
        resumeJobRef.current = null;
        throw new ExportError(JOB_FAILED_MESSAGE);
      }
      if (status.status === "expired") {
        resumeJobRef.current = null;
        throw new ExportError("Export expired before download");
      }

      await sleep(Math.max(1, pollIntervalSeconds));
    }
  };

  const handleDownload = async () => {
    if (isExporting) return; // the button stays focusable while busy, so guard against a second export
    try {
      setIsExporting(true);
      setErrorText("");

      // A queued export whose progress checks failed is picked up again rather than queued twice,
      // as long as the filters and dates haven't changed since.
      let job = resumeJobRef.current?.selectionKey === selectionKey ? resumeJobRef.current : null;

      if (job) {
        setStatusText("Checking on the export");
      } else {
        setStatusText("Estimating export size");
        console.log("[Download] Starting export...");

        const payload = buildExportPayload();
        console.log("[Download] Payload:", payload);

        const estimateRes = await request("/api/exports/estimate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        console.log("[Download] Estimate response status:", estimateRes.status);

        if (!estimateRes.ok) {
          throw new ExportError(await readError(estimateRes, "Failed to estimate export size"));
        }

        const estimate = await readJson(estimateRes);
        console.log("[Download] Estimate result:", estimate);
        const recommendedMode = estimate.recommended_mode || "async";

        if (recommendedMode === "sync") {
          setStatusText("Generating file");
          console.log("[Download] Using SYNC mode");
          const syncRes = await request("/api/exports/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          console.log("[Download] Sync response status:", syncRes.status);
          await triggerDownload(syncRes, getFileName());
          return;
        }

        console.log("[Download] Using ASYNC mode");
        setStatusText("Queueing export job");
        const createJobRes = await request("/api/exports/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        console.log("[Download] Create job response status:", createJobRes.status);

        if (!createJobRes.ok) {
          throw new ExportError(await readError(createJobRes, "Failed to queue export job"));
        }

        const created = await readJson(createJobRes);
        console.log("[Download] Job created:", created);
        job = {
          jobId: String(created.job_id),
          pollIntervalSeconds: Number(created.poll_interval_seconds || 3),
          selectionKey,
        };
        resumeJobRef.current = job;
      }

      await pollUntilReady(job.jobId, job.pollIntervalSeconds);

      setStatusText("Downloading file");
      const downloadRes = await request(`/api/exports/jobs/${encodeURIComponent(job.jobId)}/download`);
      // 404/410: the job or its file is gone (expired or cleaned up), so Try again must start a new export.
      if (downloadRes.status === 404 || downloadRes.status === 410) resumeJobRef.current = null;
      await triggerDownload(downloadRes, getFileName());
      resumeJobRef.current = null;
    } catch (error) {
      console.error("[Download] ERROR:", error);
      // Only messages written for the user are shown; anything else (a bug, an odd reply) gets a plain one.
      setErrorText(error instanceof ExportError ? error.message : "Something went wrong. Please try again.");
    } finally {
      setIsExporting(false);
      setStatusText("");
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
        className="btn-mcmaster-primary w-full aria-disabled:pointer-events-none aria-disabled:opacity-50"
      >
        <DownloadIcon className="h-4 w-4 mr-2" />
        {isExporting ? statusText || "Preparing export" : "Download Data"}
      </Button>
      {errorText && !isExporting && (
        <div
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
