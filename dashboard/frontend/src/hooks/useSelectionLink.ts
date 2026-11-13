// Keeps what is ticked in the page's link, next to the dates (?from=&to=), so a shared link opens with the same groups:
//   ?groups=gauges,weather   the West Campus groups ticked
//   ?creeks=ancaster          the Ancaster Watershed creeks ticked
//   ?tab=sampling             the Ancaster Watershed tab (the West Campus tab is the default and isn't written)
// A group from a link is ticked as a click on it would tick it: with all its metrics and stations, its list open.
// The link is updated with replaceState, so it adds no history entries; parameters it doesn't own are kept.

import { useEffect, useRef } from "react";
import { SAMPLING_FILTER_CONFIG, SAMPLING_METRICS, SENSOR_FILTER_CONFIG } from "@/components/config/filters";
import { namesFromParam, searchWithSelection } from "@/utils/selectionLink";

type SensorGroup = keyof typeof SENSOR_FILTER_CONFIG;
type Creek = keyof typeof SAMPLING_FILTER_CONFIG;
type Setter<T> = React.Dispatch<React.SetStateAction<T>>;
type Flags<K extends string> = Record<K, boolean>;

const SENSOR_GROUPS = Object.keys(SENSOR_FILTER_CONFIG) as SensorGroup[];
const CREEKS = Object.keys(SAMPLING_FILTER_CONFIG) as Creek[];

interface SelectionState {
  activeTab: "sensor" | "sampling";
  setActiveTab: Setter<"sensor" | "sampling">;
  activeGroups: Flags<SensorGroup>;
  setActiveGroups: Setter<Flags<SensorGroup>>;
  setSubFilters: Setter<{ [key: string]: string[] }>;
  activeCreeks: Flags<Creek>;
  setActiveCreeks: Setter<Flags<Creek>>;
  setSamplingSubFilters: Setter<{ [key: string]: string[] }>;
  setOpen: Setter<Flags<SensorGroup | Creek>>;
  setChevronState: Setter<{ [key: string]: boolean }>;
}

export default function useSelectionLink(s: SelectionState) {
  const {
    activeTab, setActiveTab, activeGroups, setActiveGroups, setSubFilters, activeCreeks, setActiveCreeks,
    setSamplingSubFilters, setOpen, setChevronState,
  } = s;
  // The link is read once, on load; the first write waits until what it asked for has been ticked.
  const read = useRef(false);

  useEffect(() => {
    if (read.current) return;
    read.current = true;
    const q = new URLSearchParams(window.location.search);
    const groups = namesFromParam(q.get("groups"), SENSOR_GROUPS);
    const creeks = namesFromParam(q.get("creeks"), CREEKS);
    if (q.get("tab") === "sampling") setActiveTab("sampling");
    const opened = [...groups, ...creeks];
    if (opened.length === 0) return;
    setActiveGroups((prev) => ({ ...prev, ...Object.fromEntries(groups.map((g) => [g, true])) }));
    setSubFilters((prev) => ({
      ...prev,
      ...Object.fromEntries(groups.map((g) => [g, [...SENSOR_FILTER_CONFIG[g].metrics, SENSOR_FILTER_CONFIG[g].itemsLabel]])),
    }));
    setActiveCreeks((prev) => ({ ...prev, ...Object.fromEntries(creeks.map((c) => [c, true])) }));
    setSamplingSubFilters((prev) => ({
      ...prev,
      ...Object.fromEntries(creeks.map((c) => [c, [...SAMPLING_METRICS, "All Sites"]])),
    }));
    setOpen((prev) => ({ ...prev, ...Object.fromEntries(opened.map((k) => [k, true])) }));
    setChevronState((prev) => ({ ...prev, ...Object.fromEntries(opened.map((k) => [k, true])) }));
  }, [setActiveTab, setActiveGroups, setSubFilters, setActiveCreeks, setSamplingSubFilters, setOpen, setChevronState]);

  const groups = SENSOR_GROUPS.filter((g) => activeGroups[g]).join(",");
  const creeks = CREEKS.filter((c) => activeCreeks[c]).join(",");
  const firstWrite = useRef(true);
  useEffect(() => {
    // The first render still has the defaults, before the link's selection is ticked: writing them would drop it.
    if (firstWrite.current) {
      firstWrite.current = false;
      return;
    }
    const search = searchWithSelection(window.location.search, activeTab, groups ? groups.split(",") : [], creeks ? creeks.split(",") : []);
    if (search !== window.location.search) {
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${search}${window.location.hash}`);
    }
  }, [activeTab, groups, creeks]);
}
