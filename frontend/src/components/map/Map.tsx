import { GoogleMap, Marker, useLoadScript, InfoWindow } from "@react-google-maps/api";
import { FC, useState } from "react";

interface ActiveGroups {
  gauges: boolean;
  weather: boolean;
  quality: boolean;
}

interface MapProps {
  activeGroups: ActiveGroups;
  setActiveGroups: React.Dispatch<React.SetStateAction<ActiveGroups>>;
}

const center = { lat: 43.260456, lng: -79.932517 };

const markers = [
  { lat: 43.2671, lng: -79.928828, label: "Water Logger 1", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.264372, lng: -79.928956, label: "Water Logger 2", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.260456, lng: -79.932517, label: "Water Logger 3", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.258192, lng: -79.938394, label: "Water Logger 4", icon: "/icons/loggerIcon.png", group: "gauges" },
  { lat: 43.253939, lng: -79.942208, label: "Water Logger 5", icon: "icons/loggerIcon.png", group: "gauges" },
  { lat: 43.260456, lng: -79.932812, label: "Water Quality Sensor", icon: "/icons/qualityIcon.png", group: "quality" },
  { lat: 43.265686, lng: -79.929256, label: "Weather Station", icon: "/icons/weatherIcon.png", group: "weather" },
];

const containerStyle = {
  width: "100%",
  height: "300px",
};

const Map: FC<MapProps> = ({ activeGroups, setActiveGroups }) => {
  const { isLoaded } = useLoadScript({
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!,
  });

  const [selectedMarker, setSelectedMarker] = useState<null | typeof markers[0]>(null);
  const [hoverTimeout, setHoverTimeout] = useState<NodeJS.Timeout | null>(null);

  if (!isLoaded) return <div>Loading...</div>;

  return (
    <GoogleMap mapContainerStyle={containerStyle} center={center} zoom={14}>
      {markers.map((marker, index) => {
        const isActive = activeGroups[marker.group as keyof ActiveGroups] ?? false;

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
                setSelectedMarker(null);
              }, 300);
              setHoverTimeout(timeout);
            }}
            onClick={() => {
              const group = marker.group as keyof ActiveGroups;
              setActiveGroups((prev) => ({
                ...prev,
                [group]: !prev[group],
              }));
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
          <div style={{ opacity: 1 }}>
            <h1 className="font-semibold">{selectedMarker.label}</h1>
            <p>Latitude: {selectedMarker.lat}</p>
            <p>Longitude: {selectedMarker.lng}</p>
            <p>Hamilton, ON<br />Canada</p>
            <a
              href={`https://maps.google.com/?q=${selectedMarker.lat},${selectedMarker.lng}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              View on Google Maps
            </a>
          </div>
        </InfoWindow>
      )}
    </GoogleMap>
  );
};

export default Map;
