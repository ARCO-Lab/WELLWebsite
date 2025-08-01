import { GoogleMap, Marker, useLoadScript, InfoWindow } from "@react-google-maps/api";
import { FC, useState } from "react";
import { MapPin, ExternalLink, Navigation } from "lucide-react"; // Import necessary icons
import { Button } from "@/components/animations/button"; // Import Button component

interface ActiveGroups {
  gauges: boolean;
  weather: boolean;
  quality: boolean;
}

interface MapProps {
  activeGroups: ActiveGroups;
  setActiveGroups: React.Dispatch<React.SetStateAction<ActiveGroups>>;
  subFilters: {
    gauges: string[];
    weather: string[];
    quality: string[];
  };
  setSubFilters: React.Dispatch<React.SetStateAction<{
    gauges: string[];
    weather: string[];
    quality: string[];
  }>>;
  open: {
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  };
  setOpen: React.Dispatch<React.SetStateAction<{
    gauges: boolean;
    weather: boolean;
    quality: boolean;
  }>>;
}

const center = { lat: 43.260456, lng: -79.932517 };

const markers = [
  { lat: 43.2671, lng: -79.928828, label: "Water Logger 1", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.264372, lng: -79.928956, label: "Water Logger 2", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.260456, lng: -79.932517, label: "Water Logger 3", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.258192, lng: -79.938394, label: "Water Logger 4", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.253939, lng: -79.942208, label: "Water Logger 5", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.260456, lng: -79.932812, label: "Water Quality Sensor", icon: "/icons/qualityIcon.png", group: "quality" },
  { lat: 43.265686, lng: -79.929256, label: "Weather Station", icon: "/icons/weatherIcon.png", group: "weather" },
];

const containerStyle = {
  width: "100%",
  height: "300px",
};

const Map: FC<MapProps> = ({ activeGroups, setActiveGroups, subFilters, setSubFilters, open, setOpen }) => {
  const { isLoaded } = useLoadScript({
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!,
  });

  const [selectedMarker, setSelectedMarker] = useState<null | typeof markers[0]>(null);
  const [hoverTimeout, setHoverTimeout] = useState<NodeJS.Timeout | null>(null);
  // State to track if the InfoWindow itself is being hovered over
  const [isInfoWindowHovered, setIsInfoWindowHovered] = useState(false);


  if (!isLoaded) return <div>Loading...</div>;

  // Helper function to determine marker-specific styling based on its group
  const getMarkerTypeInfo = (group: string) => {
    switch (group) {
      case "weather":
        return { color: "text-blue-600", bgColor: "bg-blue-50 border-blue-200" };
      case "quality":
        return { color: "text-pink-600", bgColor: "bg-pink-50 border-pink-200" };
      case "gauges":
        return { color: "text-blue-500", bgColor: "bg-blue-50 border-blue-200" };
      default:
        return { color: "text-muted-foreground", bgColor: "bg-muted border-border" };
    }
  };

  return (
    <GoogleMap mapContainerStyle={containerStyle} center={center} zoom={14}>
      {markers.map((marker, index) => {
        const isLogger = marker.group === "gauges";

        let isActive = false;
        if (isLogger) {
          if (!activeGroups.gauges) {
            isActive = false;
          } else if (subFilters.gauges.includes("All Loggers")) {
            isActive = true;
          } else {
            const loggerName = marker.label.replace("Water ", ""); // "Logger 1", etc.
            isActive = subFilters.gauges.includes(loggerName);

          }
        } else {
          isActive = activeGroups[marker.group as keyof ActiveGroups] ?? false;
        }

        return (
          <Marker
            key={index}
            position={{ lat: marker.lat, lng: marker.lng }}
            icon={{
              url: marker.icon,
              scaledSize: new google.maps.Size(32, 32),
            }}
            opacity={isActive ? 1.0 : 0.5}
            onMouseOver={() => {
              if (hoverTimeout) clearTimeout(hoverTimeout);
              setSelectedMarker(marker);
            }}
            onMouseOut={() => {
              const timeout = setTimeout(() => {
                // Only close if InfoWindow is not being hovered
                if (!isInfoWindowHovered) {
                  setSelectedMarker(null);
                }
              }, 200); // Increased delay to allow moving mouse to InfoWindow
              setHoverTimeout(timeout);
            }}
            onClick={() => {
              if (marker.group === "gauges") {
                setOpen((prev) => ({ ...prev, gauges: true }));
                const loggerName = marker.label.replace("Water ", ""); // e.g., "Logger 1"

                setSubFilters((prev) => {
                  const selected = new Set(prev.gauges);
                  const loggerLabels = ["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"];

                  let newSelected: Set<string>;
                  if (selected.has("All Loggers")) {
                    // If "All Loggers" is selected, deselect the clicked logger and select all others
                    newSelected = new Set(["Logger 1", "Logger 2", "Logger 3", "Logger 4", "Logger 5"]);
                    newSelected.delete(loggerName);
                  } else {
                    // Normal toggle
                    newSelected = new Set(selected);
                    if (newSelected.has(loggerName)) {
                      newSelected.delete(loggerName);
                    } else {
                      newSelected.add(loggerName);
                    }
                  }
                  // If all individual loggers are now selected, collapse back to "All Loggers"
                  const allSelected = loggerLabels.every((l) => newSelected.has(l));
                  if (allSelected) {
                    setActiveGroups((prevGroups) => ({ ...prevGroups, gauges: true }));

                    return { ...prev, gauges: ["All Loggers"] };
                  }

                  // If at least one logger is selected, ensure group is active
                  if (newSelected.size > 0) {
                    setActiveGroups((prevGroups) => ({ ...prevGroups, gauges: true }));
                  }

                  return { ...prev, gauges: Array.from(newSelected) };
                });
              } else {
                const group = marker.group as keyof ActiveGroups;
                const newActiveState = !activeGroups[group];
                setActiveGroups((prev) => ({
                  ...prev,
                  [group]: newActiveState,
                }));
                setOpen((prev) => ({
                  ...prev,
                  [group]: newActiveState,
                }));
              }
            }}
          />
        );
      })}

      {selectedMarker && (
        <InfoWindow
          position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }}
          onCloseClick={() => setSelectedMarker(null)}
          options={{
            pixelOffset: new google.maps.Size(0, -40),
            disableAutoPan: true,
          }}
        >
          {/* InfoWindow content with new UI styling */}
          <div
            className="p-0 m-0 min-w-[280px]"
            onMouseEnter={() => {
              if (hoverTimeout) clearTimeout(hoverTimeout);
              setIsInfoWindowHovered(true);
            }}
            onMouseLeave={() => {
              setIsInfoWindowHovered(false);
              const timeout = setTimeout(() => {
                setSelectedMarker(null);
              }, 100); // 500ms delay to allow moving mouse to InfoWindow
              setHoverTimeout(timeout);
            }}
          >
            <div className={`rounded-lg border shadow-lg bg-card overflow-hidden animate-in fade-in-0 zoom-in-95 duration-200 ${getMarkerTypeInfo(selectedMarker.group).bgColor}`}>
              {/* Header section of the InfoWindow */}
              <div className={`p-4 border-b ${getMarkerTypeInfo(selectedMarker.group).bgColor}`}>
                <div className="flex items-center space-x-2">
                  <MapPin className={`h-5 w-5 ${getMarkerTypeInfo(selectedMarker.group).color}`} />
                  <h3 className="font-semibold text-lg text-foreground">{selectedMarker.label}</h3>
                </div>
              </div>

              {/* Content section of the InfoWindow */}
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

                <div className="text-sm">
                  <span className="text-muted-foreground">Location:</span>
                  <p className="text-foreground">Hamilton, ON, Canada</p>
                </div>

                {/* Action Button to view on Google Maps */}
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full hover-scale"
                  onClick={() => {
                    window.open(
                      `https://maps.google.com/?q=${selectedMarker.lat},${selectedMarker.lng}`,
                      '_blank',
                      'noopener,noreferrer'
                    );
                  }}
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
