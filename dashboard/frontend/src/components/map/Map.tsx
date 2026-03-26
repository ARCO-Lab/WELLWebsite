// This file defines the Map component for displaying sensor and sampling site markers on a Google Map.
// It handles marker selection, info windows, and filter state updates for the dashboard.

import { GoogleMap, Marker, useLoadScript, InfoWindow } from "@react-google-maps/api";
import { FC, useState } from "react";
import { MapPin, ExternalLink, Navigation } from "lucide-react";
import { Button } from "@/components/animations/button";
import getConfig from "next/config";
import { SENSOR_FILTER_CONFIG, SAMPLING_METRICS, SENSOR_STATION_COORDINATES, SAMPLING_SITE_COORDINATES } from "@/components/config/filters";

// --- PROPS ---

interface MapProps {
  activeGroups: { [key: string]: boolean };
  setActiveGroups: React.Dispatch<React.SetStateAction<{ gauges: boolean; weather: boolean; quality: boolean }>>;
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

// --- DATA DEFINITIONS ---

const sensorCenter = { lat: 43.2655, lng: -79.9291 };
const samplingCenter = { lat: 43.24, lng: -79.96 };

const sensorMarkers = SENSOR_STATION_COORDINATES;

const samplingMarkers = SAMPLING_SITE_COORDINATES

const containerStyle = {
  width: "100%",
  height: "100%", // Use full height of parent
};

// --- COMPONENT ---

const Map: FC<MapProps> = ({ 
  activeGroups, setActiveGroups, subFilters, setSubFilters, open, setOpen, 
  chevronState, setChevronState, isSampling = false 
}) => {
  const { publicRuntimeConfig } = getConfig();
  const { basePath } = publicRuntimeConfig;

  const { isLoaded } = useLoadScript({
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!,
  });

  const [selectedMarker, setSelectedMarker] = useState<any>(null);
  const [hoverTimeout, setHoverTimeout] = useState<NodeJS.Timeout | null>(null);
  const [isInfoWindowHovered, setIsInfoWindowHovered] = useState(false);

  if (!isLoaded) return <div>Loading...</div>;

  const markersToDisplay = isSampling ? samplingMarkers : sensorMarkers;
  const mapCenter = isSampling ? samplingCenter : sensorCenter;
  const mapZoom = isSampling ? 12 : 16;
  
  // Helper to determine marker color and background based on group
  const getMarkerTypeInfo = (group: string) => {
    switch (group) {
      // Sensor groups
      case "weather": return { color: "text-blue-600", bgColor: "bg-blue-50 border-blue-200" };
      case "quality": return { color: "text-pink-600", bgColor: "bg-pink-50 border-pink-200" };
      case "gauges": return { color: "text-cyan-600", bgColor: "bg-cyan-50 border-cyan-200" };
      // Sampling groups (creeks)
      case "ancaster": return { color: "text-red-600", bgColor: "bg-red-50 border-red-200" };
      case "tiffany": return { color: "text-green-600", bgColor: "bg-green-50 border-green-200" };
      case "sulphur": return { color: "text-yellow-600", bgColor: "bg-yellow-50 border-yellow-200" };
      case "coldwater": return { color: "text-indigo-600", bgColor: "bg-indigo-50 border-indigo-200" };
      case "spencer": return { color: "text-purple-600", bgColor: "bg-purple-50 border-purple-200" };
      default: return { color: "text-muted-foreground", bgColor: "bg-muted border-border" };
    }
  };

  // Handles marker click: toggles group and subfilter state
  const handleMarkerClick = (marker: typeof markersToDisplay[0]) => {
    const group = marker.group;
    const id = marker.id;
    const currentlyActive = activeGroups[group];

    // For single-item groups, apply chevron logic and toggle the main active state
    if (group === 'weather' || group === 'quality') {
      // Update chevron based on your cases
      if (!currentlyActive) {
        // Case 1 & 2: active group = false -> chevron = true
        setChevronState(prev => ({ ...prev, [group]: true }));
        setOpen(prev => ({ ...prev, [group]: true }));
      } else {
        // Case 3 & 4: active group = true -> chevron = false
        setChevronState(prev => ({ ...prev, [group]: false }));
        setOpen(prev => ({ ...prev, [group]: false }));
      }

      const isOpening = !currentlyActive;
      setActiveGroups(prev => ({ ...prev, [group]: !prev[group] }));

      // When opening, select all metrics; when closing, clear all filters
      if (isOpening) {
        // Get config to determine all metrics for this group
        const config = isSampling 
          ? { metrics: ["E. coli", "Phosphorus", "Nitrates"], itemsLabel: "All Sites" }
          : (group === 'weather' 
              ? { metrics: ["Air Temperature", "Pressure", "Wind Speed", "Gust Speed", "Wind Direction", "Relative Humidity", "Dew Point", "Rainfall", "Water Content", "Solar Radiation", "Soil Temperature"] }
              : { metrics: ["Water Temperature", "Conductivity", "Salinity", "Total Dissolved Solids (TDS)", "Dissolved Oxygen (ODO)", "Dissolved Oxygen Saturation (ODOSat)", "Turbidity", "Total Suspended Solids (TSS)"] });
        
        const allMetrics = config.metrics || [];
        setSubFilters(prev => ({ ...prev, [group]: allMetrics }));
      } else {
        setSubFilters(prev => ({ ...prev, [group]: [] }));
      }
      return;
    }

    // For multi-item groups, apply the advanced logic with chevron updates
    const isOpening = !currentlyActive;
      
    if (isOpening) {
      // Open the group and chevron
      setChevronState(prev => ({ ...prev, [group]: true }));
      setOpen(prev => ({ ...prev, [group]: true }));
      setActiveGroups(prev => ({ ...prev, [group]: true }));

      // Only select the metrics and the clicked logger
      const allMetrics = isSampling
        ? SAMPLING_METRICS
        : SENSOR_FILTER_CONFIG[group as keyof typeof SENSOR_FILTER_CONFIG]?.metrics || [];
      setSubFilters(prev => ({
        ...prev,
        [group]: [...allMetrics, id], // Only the clicked logger, not "All Loggers"
      }));
    } else {
      // For multi-item groups, just toggle the specific item without affecting group state
      setSubFilters(prev => {
        const currentSubs = new Set(prev[group] || []);
        
        // Get all item IDs for the current group from the full marker list
        const allItemsInGroup = markersToDisplay
            .filter(m => m.group === group)
            .map(m => m.id);
        
        const allItemsLabel = isSampling ? "All Sites" : "All Loggers";

        // If "All" is currently checked, we need to expand it first
        if (currentSubs.has(allItemsLabel)) {
          currentSubs.delete(allItemsLabel); // Uncheck "All"
          allItemsInGroup.forEach(item => currentSubs.add(item)); // and check all individuals
        }

        // Now, toggle the specific item that was clicked
        if (currentSubs.has(id)) {
          currentSubs.delete(id);
        } else {
          currentSubs.add(id);
        }

        // After toggling, check if all individual items are now selected
        const allIndividualItemsSelected = allItemsInGroup.length > 0 && allItemsInGroup.every(item => currentSubs.has(item));

        // If they are, switch to the "All" state
        if (allIndividualItemsSelected) {
          currentSubs.add(allItemsLabel); // Check "All"
          allItemsInGroup.forEach(item => currentSubs.delete(item)); // and uncheck all individuals
        }

        // If this action resulted in no selected items for this group, deactivate the main group and update chevron
        if (currentSubs.size === 0) {
          setActiveGroups(prevActive => ({ ...prevActive, [group]: false }));
          setChevronState(prev => ({ ...prev, [group]: false }));
          setOpen(prev => ({ ...prev, [group]: false }));
        }

        return { ...prev, [group]: Array.from(currentSubs) };
      });
    }
  };


  return (
    <GoogleMap mapContainerStyle={containerStyle} center={mapCenter} zoom={mapZoom}>
      {markersToDisplay.map((marker, index) => {
        const groupIsActive = activeGroups[marker.group] ?? false;
        const groupSubFilters = subFilters[marker.group] || [];
        
        let isActive;
        // Special handling for single-item groups
        if (marker.group === 'weather' || marker.group === 'quality') {
          isActive = groupIsActive;
        } else {
          // Standard logic for multi-item groups (gauges and sampling sites)
          const allItemsLabel = isSampling ? "All Sites" : "All Loggers";
          const isAllSelected = groupSubFilters.includes(allItemsLabel);
          const isIndividuallySelected = groupSubFilters.includes(marker.id);
          isActive = groupIsActive && (isAllSelected || isIndividuallySelected);
        }

        return (
          <Marker
            key={index}
            position={{ lat: marker.lat, lng: marker.lng }}
            icon={{
              url: `${basePath || ''}/icons/${marker.group}Icon.png`,
              scaledSize: new google.maps.Size(32, 32),
            }}
            opacity={isActive ? 1.0 : 0.4}
            onMouseOver={() => {
              if (hoverTimeout) clearTimeout(hoverTimeout);
              setSelectedMarker(marker);
            }}
            onMouseOut={() => {
              const timeout = setTimeout(() => {
                if (!isInfoWindowHovered) setSelectedMarker(null);
              }, 200);
              setHoverTimeout(timeout);
            }}
            onClick={() => handleMarkerClick(marker)}
          />
        );
      })}

      {selectedMarker && (
        <InfoWindow
          position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }}
          onCloseClick={() => setSelectedMarker(null)}
          options={{ pixelOffset: new google.maps.Size(0, -40), disableAutoPan: true }}
        >
          <div
            className="m-0 w-[min(280px,calc(100vw-48px))] p-0"
            onMouseEnter={() => {
              if (hoverTimeout) clearTimeout(hoverTimeout);
              setIsInfoWindowHovered(true);
            }}
            onMouseLeave={() => {
              setIsInfoWindowHovered(false);
              const timeout = setTimeout(() => setSelectedMarker(null), 100);
              setHoverTimeout(timeout);
            }}
          >
            <div className={`rounded-lg border shadow-lg bg-card overflow-hidden animate-in fade-in-0 zoom-in-95 duration-200 ${getMarkerTypeInfo(selectedMarker.group).bgColor}`}>
              <div className={`p-4 border-b ${getMarkerTypeInfo(selectedMarker.group).bgColor}`}>
                <div className="flex items-center space-x-2">
                  <MapPin className={`h-5 w-5 ${getMarkerTypeInfo(selectedMarker.group).color}`} />
                  <h3 className="font-semibold text-lg text-foreground">{selectedMarker.label}</h3>
                </div>
              </div>
              <div className="p-4 bg-card space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">Latitude:</span>
                    <p className="font-mono text-foreground">{selectedMarker.lat.toFixed(6)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Longitude:</span>
                    <p className="font-mono text-foreground">{selectedMarker.lng.toFixed(6)}</p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full hover-scale"
                  onClick={() => window.open(`https://maps.google.com/?q=${selectedMarker.lat},${selectedMarker.lng}`, '_blank', 'noopener,noreferrer')}
                >
                  <Navigation className="h-4 w-4 mr-2" />
                  View on Google Maps
                  <ExternalLink className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </div>
          </div>
        </InfoWindow>
      )}
    </GoogleMap>
  );
};

export default Map;