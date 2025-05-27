import React from "react";

type MarkerProps = {
  lat: number;
  lng: number;
  type: "logger" | "quality" | "weather";
  id: number;
};

const Marker = ({ type, id }: MarkerProps) => {
  let icon = "";
  let hoverText = "";

  if (type === "logger") {
    icon = "/mapIcons/loggerIcon.png"; // blue water droplet
    hoverText = `Water Logger ${id}`;
  } else if (type === "quality") {
    icon = "/mapIcons/qualityIcon.png"; // pink droplet
    hoverText = `Water Quality Sensor`;
  } else if (type === "weather") {
    icon = "/mapIcons/weatherIcon.png"; // gray cloud
    hoverText = `Weather Station`;
  }

  return (
    <div className="relative group">
      <img src={icon} alt={hoverText} className="w-6 h-6" />
      <div className="absolute px-2 py-1 mb-1 text-xs text-white bg-black rounded opacity-0 bottom-full group-hover:opacity-100">
        {hoverText}
      </div>
    </div>
  );
};

export default Marker;
