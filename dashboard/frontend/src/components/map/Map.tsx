// Map of the sensors (West Campus tab) and the sampling sites (Ancaster Watershed tab).
//
// MapLibre GL with OpenFreeMap's vector tiles (OpenStreetMap data, no API key, no cookies); Satellite uses
// Esri World Imagery. If the vector style can't be loaded, the map falls back to plain OpenStreetMap tiles.
// Clicking (or tapping) a marker shows or hides that sensor/site on the dashboard, in sync with the Filters panel,
// and pins a card with its details, a Show/Hide button and a Google Maps link. Hovering or focusing a marker
// previews the card. From the keyboard, Enter/Space on a marker opens the card and moves focus into it without
// changing the data; the card's Show/Hide button does that, and Escape closes the card and returns to the marker.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapGL, { Marker, Popup, NavigationControl, FullscreenControl, type MapRef } from "@vis.gl/react-maplibre";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CloudSun, ExternalLink, Eye, EyeOff, FlaskConical, LocateFixed, Waves, X, type LucideIcon } from "lucide-react";
import {
  SENSOR_FILTER_CONFIG,
  SAMPLING_FILTER_CONFIG,
  SAMPLING_METRICS,
  SENSOR_STATION_COORDINATES,
  SAMPLING_SITE_COORDINATES,
} from "@/components/config/filters";
import styles from "./Map.module.css";

// --- PROPS ---

// G is the shape of the on/off state for the marker groups: the sensor groups on the Sensors tab, the creeks
// on the sampling tab.
interface MapProps<G extends { [key: string]: boolean }> {
  activeGroups: { [key: string]: boolean };
  setActiveGroups: React.Dispatch<React.SetStateAction<G>>;
  subFilters: { [key: string]: string[] };
  setSubFilters: React.Dispatch<React.SetStateAction<{ [key: string]: string[] }>>;
  open: { [key: string]: boolean };
  setOpen: React.Dispatch<React.SetStateAction<{
    gauges: boolean;
    weather: boolean;
    quality: boolean;
    ancaster: boolean;
    tiffany: boolean;
    sulphur: boolean;
    coldwater: boolean;
    spencer: boolean;
  }>>
  chevronState: { [key: string]: boolean };
  setChevronState: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  isSampling?: boolean; // Flag to switch between sensor and sampling data
}

type Site = (typeof SENSOR_STATION_COORDINATES)[number] | (typeof SAMPLING_SITE_COORDINATES)[number];

// --- MAP STYLES ---

const STREETS_STYLE = "https://tiles.openfreemap.org/styles/liberty";

const rasterStyle = (tiles: string, attribution: string): StyleSpecification => ({
  version: 8,
  sources: { base: { type: "raster", tiles: [tiles], tileSize: 256, maxzoom: 19, attribution } },
  layers: [{ id: "base", type: "raster", source: "base" }],
});

const SATELLITE_STYLE = rasterStyle(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community",
);

// Used only if the vector style can't be loaded.
const FALLBACK_STYLE = rasterStyle(
  "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
);

// --- MARKER LOOK ---

// Colour and icon per marker group. Sensors get an icon for their type; sampling sites show their site number
// in their creek's colour.
const GROUP_LOOK: Record<string, { color: string; icon?: LucideIcon; name: string }> = {
  gauges: { color: "#0369a1", icon: Waves, name: "Water logger" },
  weather: { color: "#475569", icon: CloudSun, name: "Weather station" },
  quality: { color: "#be185d", icon: FlaskConical, name: "Water quality sensor" },
  ancaster: { color: "#c2410c", name: SAMPLING_FILTER_CONFIG.ancaster.label },
  tiffany: { color: "#a16207", name: SAMPLING_FILTER_CONFIG.tiffany.label },
  sulphur: { color: "#15803d", name: SAMPLING_FILTER_CONFIG.sulphur.label },
  coldwater: { color: "#1f2937", name: SAMPLING_FILTER_CONFIG.coldwater.label },
  spencer: { color: "#4338ca", name: SAMPLING_FILTER_CONFIG.spencer.label },
};

const lookOf = (group: string) => GROUP_LOOK[group] ?? { color: "#475569", name: group };

// Sites closer than this are drawn side by side instead of on top of each other
// (the water quality sensor sits ~4 m from Logger 3).
const OVERLAP_METRES = 25;

function metresBetween(a: Site, b: Site) {
  const dy = (a.lat - b.lat) * 110_540;
  const dx = (a.lng - b.lng) * 111_320 * Math.cos((a.lat * Math.PI) / 180);
  return Math.hypot(dx, dy);
}

const siteKey = (site: Site) => `${site.group}-${site.id}`;

const googleMapsUrl = (site: Site) => `https://www.google.com/maps/search/?api=1&query=${site.lat},${site.lng}`;

// Card offsets for every side MapLibre may open it on (it picks the side with room), including a marker's
// sideways shift.
const MARKER_RADIUS = 22;
function cardOffset(dx: number) {
  const r = MARKER_RADIUS;
  return {
    center: [dx, 0], top: [dx, r], "top-left": [dx, r], "top-right": [dx, r],
    bottom: [dx, -r], "bottom-left": [dx, -r], "bottom-right": [dx, -r], left: [dx + r, 0], right: [dx - r, 0],
  } as Record<"center" | "top" | "top-left" | "top-right" | "bottom" | "bottom-left" | "bottom-right" | "left" | "right", [number, number]>;
}

// Served from our own site; see scripts/copy-maplibre-worker.mjs.
const WORKER_URL = "/maplibre/maplibre-gl-worker.mjs";

// --- COMPONENT ---

function Map<G extends { [key: string]: boolean }>({
  activeGroups, setActiveGroups, subFilters, setSubFilters, open, setOpen,
  chevronState, setChevronState, isSampling = false
}: MapProps<G>) {
  const mapRef = useRef<MapRef>(null);
  const [satellite, setSatellite] = useState(false);
  const [vectorFailed, setVectorFailed] = useState(false);
  const styleLoaded = useRef(false);

  // The card shown for a marker: on hover/focus it follows the pointer; a click (or Enter/Space) pins it until
  // the map is clicked, it's closed or Escape is pressed. `focus` asks for focus to move into the card.
  const [card, setCard] = useState<{ site: Site; pinned: boolean; focus?: boolean } | null>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const showHideRef = useRef<HTMLButtonElement | null>(null);
  const markerRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  // Set while focus goes back to a marker after its card closed, so that focus doesn't reopen the card.
  const returningFocus = useRef(false);

  const sites: Site[] = isSampling ? SAMPLING_SITE_COORDINATES : SENSOR_STATION_COORDINATES;
  const containerId = isSampling ? "well-map-sampling" : "well-map-sensors";

  // On phone-sized screens the card is a panel along the bottom of the map instead of a popup on the marker,
  // which wouldn't fit next to the marker on such a small map.
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.innerWidth < 640);
  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth < 640);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const bounds = useMemo(() => {
    const lngs = sites.map((s) => s.lng);
    const lats = sites.map((s) => s.lat);
    return [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]] as [[number, number], [number, number]];
  }, [sites]);
  // Less padding on phones, where the map is small and the sensors sit close together.
  const fitOptions = useMemo(() => ({
    padding: typeof window !== "undefined" && window.innerWidth < 640 ? 24 : 48,
    maxZoom: isSampling ? 13 : 16.5,
  }), [isSampling]);

  // Pixel offsets that spread out markers sitting (almost) on the same spot.
  const offsets = useMemo(() => sites.map((site, i) => {
    const neighbours = sites.slice(0, i).filter((other) => metresBetween(site, other) < OVERLAP_METRES).length;
    return [neighbours * 34, 0] as [number, number];
  }), [sites]);

  const mapStyle = satellite ? SATELLITE_STYLE : vectorFailed ? FALLBACK_STYLE : STREETS_STYLE;

  const cancelHide = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = null;
  }, []);

  const scheduleHide = useCallback(() => {
    cancelHide();
    hideTimer.current = setTimeout(() => setCard((c) => (c && !c.pinned ? null : c)), 180);
  }, [cancelHide]);

  useEffect(() => () => cancelHide(), [cancelHide]);

  // Closes the card; if focus was in it, focus goes back to its marker.
  const closeCard = useCallback(() => {
    const site = card?.site;
    const focusWasInCard = !!cardRef.current?.contains(document.activeElement);
    setCard(null);
    if (site && focusWasInCard) {
      returningFocus.current = true;
      markerRefs.current[siteKey(site)]?.focus();
      returningFocus.current = false;
    }
  }, [card]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeCard(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeCard]);

  // A card opened from the keyboard takes focus, on its Show/Hide button.
  useEffect(() => {
    if (!card?.focus) return;
    const id = requestAnimationFrame(() => showHideRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [card]);

  // Business and transit points of interest only clutter a map of a creek; hide them.
  const tidyStyle = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    for (const layer of map.getStyle()?.layers ?? []) {
      if (/^poi|transit|aerodrome/i.test(layer.id)) map.setLayoutProperty(layer.id, "visibility", "none");
    }
  }, []);

  const isActive = (site: Site) => {
    const groupIsActive = activeGroups[site.group] ?? false;
    if (site.group === "weather" || site.group === "quality") return groupIsActive;
    const groupSubFilters = subFilters[site.group] || [];
    const allItemsLabel = isSampling ? "All Sites" : "All Loggers";
    return groupIsActive && (groupSubFilters.includes(allItemsLabel) || groupSubFilters.includes(site.id));
  };

  // Shows or hides a site on the dashboard, keeping the Filters panel in sync (same behaviour as before).
  const handleMarkerClick = (marker: Site) => {
    const group = marker.group;
    const id = marker.id;
    const currentlyActive = activeGroups[group];

    // Single-item groups: toggle the whole group, with all its metrics selected when it turns on.
    if (group === 'weather' || group === 'quality') {
      setChevronState(prev => ({ ...prev, [group]: !currentlyActive }));
      setOpen(prev => ({ ...prev, [group]: !currentlyActive }));
      setActiveGroups(prev => ({ ...prev, [group]: !prev[group] }));
      setSubFilters(prev => ({
        ...prev,
        [group]: currentlyActive ? [] : [...SENSOR_FILTER_CONFIG[group as 'weather' | 'quality'].metrics],
      }));
      return;
    }

    if (!currentlyActive) {
      // Turn the group on with every metric and only the clicked logger/site.
      setChevronState(prev => ({ ...prev, [group]: true }));
      setOpen(prev => ({ ...prev, [group]: true }));
      setActiveGroups(prev => ({ ...prev, [group]: true }));
      const allMetrics = isSampling
        ? SAMPLING_METRICS
        : SENSOR_FILTER_CONFIG[group as keyof typeof SENSOR_FILTER_CONFIG]?.metrics || [];
      setSubFilters(prev => ({ ...prev, [group]: [...allMetrics, id] }));
      return;
    }

    // Group already on: toggle just this item, collapsing to "All …" when every item is selected.
    setSubFilters(prev => {
      const currentSubs = new Set(prev[group] || []);
      const allItemsInGroup = sites.filter(m => m.group === group).map(m => m.id);
      const allItemsLabel = isSampling ? "All Sites" : "All Loggers";

      if (currentSubs.has(allItemsLabel)) {
        currentSubs.delete(allItemsLabel);
        allItemsInGroup.forEach(item => currentSubs.add(item));
      }

      if (currentSubs.has(id)) currentSubs.delete(id);
      else currentSubs.add(id);

      if (allItemsInGroup.length > 0 && allItemsInGroup.every(item => currentSubs.has(item))) {
        currentSubs.add(allItemsLabel);
        allItemsInGroup.forEach(item => currentSubs.delete(item));
      }

      // Hiding the group's last logger/site turns the whole group off (otherwise it would stay on with only
      // metrics ticked, which shows every site, or none).
      if (!currentSubs.has(allItemsLabel) && !allItemsInGroup.some(item => currentSubs.has(item))) {
        setActiveGroups(prevActive => ({ ...prevActive, [group]: false }));
        setChevronState(prevChevron => ({ ...prevChevron, [group]: false }));
        setOpen(prevOpen => ({ ...prevOpen, [group]: false }));
        return { ...prev, [group]: [] };
      }

      return { ...prev, [group]: Array.from(currentSubs) };
    });
  };

  const legendGroups = Array.from(new Set(sites.map((s) => s.group)));
  const cardSite = card?.site;
  const cardLook = cardSite ? lookOf(cardSite.group) : null;
  const cardActive = cardSite ? isActive(cardSite) : false;

  // The details card for a site: name, type and position, whether it's shown, Show/Hide and a Google Maps link.
  // `compact` (the phone panel) drops the status line: the Show/Hide label and the filled marker already say it.
  const siteCard = (site: Site, look: ReturnType<typeof lookOf>, active: boolean, compact = false) => (
    <div ref={cardRef} role="dialog" aria-label={site.label} className="relative text-left"
      onMouseEnter={cancelHide} onMouseLeave={scheduleHide} onFocus={cancelHide}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); closeCard(); }}
        className="absolute right-1.5 top-1.5 grid h-7 w-7 place-items-center rounded-md text-muted transition-colors hover:bg-black/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        aria-label="Close"
      >
        <X aria-hidden className="h-4 w-4" />
      </button>
      <div className={`flex items-center gap-3 pr-10 ${compact ? "p-2.5" : "p-3"}`}>
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-bold text-white"
          style={{ background: look.color }} aria-hidden>
          {look.icon ? <look.icon className="h-4 w-4" strokeWidth={2.25} /> : site.id}
        </span>
        <div className="min-w-0">
          <p className="truncate font-poppins text-sm font-semibold text-foreground">{site.label}</p>
          <p className="truncate text-xs text-muted">{look.name} · {site.lat.toFixed(4)}, {site.lng.toFixed(4)}</p>
        </div>
      </div>
      <p className={`items-center gap-2 border-t border-input-border px-3 py-2 text-xs ${compact ? "hidden" : "flex"}`}>
        <span className={`h-2 w-2 shrink-0 rounded-full ${active ? "bg-emerald-600" : "bg-gray-300"}`} aria-hidden />
        <span className={active ? "font-medium text-emerald-700" : "text-muted"}>
          {active ? "Shown on the dashboard" : "Not shown on the dashboard"}
        </span>
      </p>
      <div className="grid grid-cols-2 gap-2 border-t border-input-border p-2">
        <button
          ref={showHideRef}
          type="button"
          onClick={(e) => { e.stopPropagation(); handleMarkerClick(site); setCard({ site, pinned: true }); }}
          className="inline-flex min-h-8 items-center justify-center gap-1.5 rounded-md border border-input-border px-2 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {active ? <EyeOff aria-hidden className="h-3.5 w-3.5" /> : <Eye aria-hidden className="h-3.5 w-3.5" />}
          {active ? "Hide" : "Show"}
        </button>
        <a
          href={googleMapsUrl(site)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-8 items-center justify-center gap-1.5 rounded-md bg-primary px-2 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
        >
          Google Maps
          <ExternalLink aria-hidden className="h-3.5 w-3.5" />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      </div>
    </div>
  );

  return (
    <div id={containerId} className={`${styles.map} flex h-full min-h-[14rem] w-full flex-col overflow-hidden rounded-lg border border-input-border`}>
      <div className="relative min-h-0 flex-1">
      <MapGL
        ref={mapRef}
        workerUrl={WORKER_URL}
        initialViewState={{ bounds, fitBoundsOptions: fitOptions }}
        mapStyle={mapStyle}
        style={{ width: "100%", height: "100%" }}
        cooperativeGestures
        dragRotate={false}
        touchPitch={false}
        pitchWithRotate={false}
        maxZoom={19}
        attributionControl={{ compact: true }}
        onLoad={(e) => {
          styleLoaded.current = true;
          tidyStyle();
          // On narrow maps, start with the map credits folded into their (i) button, as MapLibre does itself
          // after the first pan; otherwise the text covers much of a phone-sized map.
          const container = e.target.getContainer();
          if (container.clientWidth < 640) {
            container.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
          }
        }}
        onStyleData={tidyStyle}
        onError={(e) => {
          // Only a failure to load the style itself switches to the fallback tiles: the style document, or a
          // source's TileJSON while the style is still loading. A missing tile, sprite or font isn't worth
          // swapping the whole map for.
          if (styleLoaded.current || satellite) return;
          const failed = e as typeof e & { sourceId?: string; tile?: unknown };
          const url = (e.error as { url?: string } | undefined)?.url;
          const styleFailed = url === STREETS_STYLE
            || (!!failed.sourceId && !failed.tile && !e.target.isStyleLoaded());
          if (styleFailed) setVectorFailed(true);
        }}
        onClick={() => setCard(null)}
        onTouchEnd={(e) => {
          // A tap on the map itself (not on a marker or the card) closes the card on touch screens too.
          if ((e.originalEvent.target as HTMLElement | null)?.classList?.contains("maplibregl-canvas")) setCard(null);
        }}
      >
        <NavigationControl position="top-right" showCompass={false} />
        {/* Full screen takes the whole block, so the type switch, legend and reset button come along. */}
        <FullscreenControl position="top-right" containerId={containerId} />

        {sites.map((site, i) => {
          const look = lookOf(site.group);
          const Icon = look.icon;
          const active = isActive(site);
          return (
            <Marker key={siteKey(site)} longitude={site.lng} latitude={site.lat} offset={offsets[i]}
              style={{ zIndex: cardSite === site ? 3 : active ? 2 : 1 }}>
              <button
                ref={(el) => { markerRefs.current[siteKey(site)] = el; }}
                type="button"
                className={`${styles.marker} ${active ? styles.markerActive : ""}`}
                style={{ ["--marker-color" as string]: look.color }}
                aria-haspopup="dialog"
                aria-expanded={!!card?.pinned && cardSite === site}
                aria-label={`${site.label} (${look.name}). ${active ? "Shown" : "Not shown"} on the dashboard. Press for its details and a ${active ? "Hide" : "Show"} button.`}
                onMouseEnter={() => { cancelHide(); setCard((c) => (c?.pinned ? c : { site, pinned: false })); }}
                onMouseLeave={scheduleHide}
                onFocus={() => {
                  cancelHide();
                  if (!returningFocus.current) setCard((c) => (c?.pinned ? c : { site, pinned: false }));
                }}
                onBlur={scheduleHide}
                onClick={(e) => {
                  e.stopPropagation();
                  cancelHide();
                  // A click from the keyboard (Enter/Space, detail 0) only opens the card and moves focus into
                  // it; a mouse click or tap also shows or hides the data, as before.
                  if (e.detail === 0) {
                    setCard({ site, pinned: true, focus: true });
                    return;
                  }
                  handleMarkerClick(site);
                  setCard({ site, pinned: true });
                }}
              >
                {Icon ? <Icon aria-hidden className="h-4 w-4" strokeWidth={2.25} /> : <span aria-hidden>{site.id}</span>}
              </button>
            </Marker>
          );
        })}

        {cardSite && cardLook && !narrow && (
          <Popup
            longitude={cardSite.lng}
            latitude={cardSite.lat}
            offset={cardOffset(offsets[sites.indexOf(cardSite)]?.[0] ?? 0)}
            closeButton={false}
            closeOnClick={false}
            focusAfterOpen={false}
            maxWidth="none"
            className={styles.popup}
          >
            <div className="w-64">{siteCard(cardSite, cardLook, cardActive)}</div>
          </Popup>
        )}
      </MapGL>

      {cardSite && cardLook && narrow && (
        <div className="absolute inset-x-2 bottom-2 z-20 overflow-hidden rounded-xl bg-card shadow-lg ring-1 ring-black/5">
          {siteCard(cardSite, cardLook, cardActive, true)}
        </div>
      )}

      {/* Map / Satellite */}
      <div className="absolute left-2 top-2 z-10 flex overflow-hidden rounded-md border border-black/10 bg-white text-xs font-medium shadow-sm" role="group" aria-label="Map type">
        {[["Map", false], ["Satellite", true]].map(([name, value]) => (
          <button
            key={name as string}
            type="button"
            aria-pressed={satellite === value}
            onClick={() => { setSatellite(value as boolean); }}
            className={`px-3 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary ${satellite === value ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-black/5"}`}
          >
            {name as string}
          </button>
        ))}
      </div>

      {/* Back to all sites */}
      <button
        type="button"
        onClick={() => mapRef.current?.fitBounds(bounds, { ...fitOptions, duration: 600 })}
        className="absolute right-[10px] top-[117px] z-10 grid h-[29px] w-[29px] place-items-center rounded-md border border-black/10 bg-white text-foreground shadow-sm transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        aria-label="Show all sites"
        title="Show all sites"
      >
        <LocateFixed aria-hidden className="h-4 w-4" />
      </button>
      </div>

      {/* Legend, under the map so it never covers markers or the map credits */}
      <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-input-border bg-card px-2.5 py-1.5" aria-label="Legend">
        {legendGroups.map((group) => {
          const look = lookOf(group);
          const Icon = look.icon;
          return (
            <li key={group} className="flex items-center gap-1.5 text-xs text-foreground">
              <span className="grid h-4 w-4 place-items-center rounded-full text-white" style={{ background: look.color }} aria-hidden>
                {Icon ? <Icon className="h-2.5 w-2.5" strokeWidth={2.5} /> : null}
              </span>
              {look.name}
            </li>
          );
        })}
        <li className="ml-auto text-[11px] text-muted">Filled = shown</li>
      </ul>
    </div>
  );
}

export default Map;
