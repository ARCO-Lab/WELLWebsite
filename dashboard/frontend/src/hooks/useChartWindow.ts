// useChartWindow: one chart's own time window and data (lib/chartController.ts), for a React component. Each card's
// chart has its own window; the charts share only the page's loader and its cache.
//
// The page provides, through ChartPageContext, the extent (the range picked under Filters: how far a chart can be
// moved, and what its navigator covers), the window charts start at, and whether they fit that window to where their
// series have readings (yes for picked days; no for a shared link's window, which is shown as it is).

import { createContext, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ChartController, type ChartSnapshot } from "@/lib/chartController";
import { seriesLoader } from "@/lib/seriesLoader";
import type { Range } from "@/utils/chartWindow";

export interface ChartPage {
  defaultWindow: Range; // where every chart starts (before fitting), and goes back to on Reset
  extent: Range; // the picked range, up to the current hour
  fit: boolean; // open on where the data is within the extent (see ChartController.setAutoFit)
  selection: string; // what the user chose (the picked days, or a link): when it changes, charts go to the new default
}

// How often a chart fetches its latest hour again while the page is open (as often as Latest Data refreshes)
export const LIVE_REFRESH_MS = 10 * 60_000;

export const ChartPageContext = createContext<ChartPage | null>(null);

// The charts on the page now, by id, so a chart opened in the larger view starts where its card's chart is.
const live = new Map<string, ChartController>();

/** Ask again for every chart on the page that failed to load: one Retry for all of them. */
export function retryAllCharts(): void {
  for (const c of live.values()) if (c.snapshot().error) c.retry();
}

/** One chart's controller. `id` is stable for the chart (e.g. "weather"; the larger view adds ":modal"),
 *  `seriesKeys` are "<group>|<station>|<measurement>". */
export function useChartWindow(id: string, seriesKeys: string[]): ChartController {
  const page = useContext(ChartPageContext);
  if (!page) throw new Error("useChartWindow needs a ChartPageContext provider");
  const [controller] = useState(() => {
    // In the larger view, start where the same chart on the page is
    const onPage = id.endsWith(":modal") ? live.get(id.slice(0, -":modal".length)) : undefined;
    const c = new ChartController(id, seriesKeys, page.defaultWindow, page.extent, seriesLoader());
    if (onPage) c.setWindow(onPage.window, "link"); // a user's window: it isn't fitted again
    return c;
  });

  useEffect(() => {
    live.set(id, controller);
    controller.activate();
    return () => {
      if (live.get(id) === controller) live.delete(id);
      controller.dispose();
    };
  }, [id, controller]);


  const fit = page.fit;
  useEffect(() => {
    controller.setAutoFit(fit);
  }, [controller, fit]);

  const keysId = seriesKeys.join("\n");
  useEffect(() => {
    controller.setKeys(keysId ? keysId.split("\n") : []);
  }, [controller, keysId]);

  const { start: es, end: ee } = page.extent;
  useEffect(() => {
    controller.setExtent({ start: es, end: ee });
  }, [controller, es, ee]);

  // Other days picked (or a link): every chart goes to the new default. The same choice with the clock moved on (the
  // hour, so today ends later): only the default moves; a window the user moved stays put.
  const { start: ds, end: de } = page.defaultWindow;
  const selection = page.selection;
  const shownDefault = useRef({ selection, ds, de });
  useEffect(() => {
    const was = shownDefault.current;
    if (was.selection === selection && was.ds === ds && was.de === de) return;
    shownDefault.current = { selection, ds, de };
    if (was.selection !== selection) controller.setDefault({ start: ds, end: de });
    else controller.updateDefault({ start: ds, end: de });
  }, [controller, selection, ds, de]);

  // A page left open keeps up: the latest hour is fetched again every LIVE_REFRESH_MS
  useEffect(() => {
    const id = window.setInterval(() => controller.refreshLive(), LIVE_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [controller]);

  return controller;
}

/** The parts of a chart's state the React tree shows (labels, badges, messages); not the per-frame drawing. */
export function useChartSnapshot(controller: ChartController): ChartSnapshot {
  return useSyncExternalStore(controller.subscribe, controller.snapshot, controller.snapshot);
}
