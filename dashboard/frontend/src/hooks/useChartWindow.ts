// useChartWindow: one chart's own time window and data (lib/chartController.ts), for a React component. Every
// chart has its own, so each one zooms and pans by itself; they share only the page's loader and its cache.
//
// The page provides, through ChartPageContext, the window charts start at and go back to on Reset (the picked days,
// or a shared link's window) and the extent of the data (the first day with data to the current hour). A card can
// link its charts (ChartLinkContext): while linked, moving one moves the others in that card.

import { createContext, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ChartController, type ChartSnapshot } from "@/lib/chartController";
import { seriesLoader } from "@/lib/seriesLoader";
import type { Range } from "@/utils/chartWindow";

export interface ChartPage {
  defaultWindow: Range; // where every chart starts, and goes back to on Reset
  extent: Range; // the data there can be: from the first day with data to the current hour
}

export const ChartPageContext = createContext<ChartPage | null>(null);

// The charts on the page now, by id, so a chart opened in the larger view starts where its card's chart is.
const live = new Map<string, ChartController>();

/** Charts in one card that may follow each other's window. */
export class ChartLinkGroup {
  linked = false;
  private members = new Set<ChartController>();
  private moving = false;
  private forwarding = false;

  add(c: ChartController): () => void {
    this.members.add(c);
    const off = c.onWindow((w, reason) => {
      if (!this.linked || this.moving || reason === "link" || reason === "default") return;
      this.moving = true;
      try {
        for (const other of this.members) if (other !== c) other.setWindow(w, "link");
      } finally {
        this.moving = false;
      }
    });
    // A gesture on one chart is a gesture on the ones following it too: they hold their requests and drop their
    // bands and accessibility layer while it lasts, as the leader does
    const offGesture = c.onGesture((active) => {
      if (!this.linked || this.forwarding) return;
      this.forwarding = true;
      try {
        for (const other of this.members) if (other !== c) (active ? other.beginGesture() : other.endGesture());
      } finally {
        this.forwarding = false;
      }
    });
    return () => {
      off();
      offGesture();
      this.members.delete(c);
    };
  }

  /** Link (and line every chart up with `leader`, or the first chart) or unlink. */
  setLinked(linked: boolean, leader?: ChartController): void {
    this.linked = linked;
    const first = leader ?? this.members.values().next().value;
    if (linked && first) for (const other of this.members) if (other !== first) other.setWindow(first.window, "link");
  }
}

export const ChartLinkContext = createContext<ChartLinkGroup | null>(null);

/** One chart's controller. `id` is stable for the chart (e.g. "logger-2577531"; the larger view adds ":modal"),
 *  `seriesKeys` are "<group>|<station>|<measurement>". */
export function useChartWindow(id: string, seriesKeys: string[]): ChartController {
  const page = useContext(ChartPageContext);
  if (!page) throw new Error("useChartWindow needs a ChartPageContext provider");
  const links = useContext(ChartLinkContext);
  const [controller] = useState(() => {
    // In the larger view, start where the same chart on the page is
    const onPage = id.endsWith(":modal") ? live.get(id.slice(0, -":modal".length)) : undefined;
    const c = new ChartController(id, seriesKeys, page.defaultWindow, page.extent, seriesLoader());
    if (onPage) c.setWindow(onPage.window, "link");
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

  useEffect(() => links?.add(controller), [links, controller]);

  const keysId = seriesKeys.join("\n");
  useEffect(() => {
    controller.setKeys(keysId ? keysId.split("\n") : []);
  }, [controller, keysId]);

  const { start: es, end: ee } = page.extent;
  useEffect(() => {
    controller.setExtent({ start: es, end: ee });
  }, [controller, es, ee]);

  // New picked days (or a link): every chart goes to them. Not on the first run: the chart starts there already
  // (or, in the larger view, where its card's chart is).
  const { start: ds, end: de } = page.defaultWindow;
  const shownDefault = useRef({ ds, de });
  useEffect(() => {
    if (shownDefault.current.ds === ds && shownDefault.current.de === de) return;
    shownDefault.current = { ds, de };
    controller.setDefault({ start: ds, end: de });
  }, [controller, ds, de]);

  return controller;
}

/** The parts of a chart's state the React tree shows (labels, badges, messages); not the per-frame drawing. */
export function useChartSnapshot(controller: ChartController): ChartSnapshot {
  return useSyncExternalStore(controller.subscribe, controller.snapshot, controller.snapshot);
}
