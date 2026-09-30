"use client";

import { useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Farm } from "@/lib/types";

// Default Leaflet marker icons reference bundled assets that don't resolve
// under Next.js's build pipeline -- point them at a CDN instead.
const markerIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

function ClickHandler({ onPick }: { onPick?: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onPick?.(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export function FarmMap({
  farms,
  selectedFarmId,
  onSelect,
  pickable,
  onPick,
  pickedLocation,
}: {
  farms: Farm[];
  selectedFarmId?: string | null;
  onSelect?: (id: string) => void;
  pickable?: boolean;
  onPick?: (lat: number, lng: number) => void;
  pickedLocation?: { lat: number; lng: number } | null;
}) {
  const [layer] = useState<"streets">("streets");
  const firstFarm = farms[0];
  const center: [number, number] = firstFarm
    ? [firstFarm.latitude, firstFarm.longitude]
    : [22.9734, 78.6569]; // India centroid fallback

  return (
    <div className="relative h-full w-full overflow-hidden rounded-card border border-border">
      <MapContainer center={center} zoom={farms.length ? 7 : 5} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {farms.map((f) => (
          <Marker
            key={f.id}
            position={[f.latitude, f.longitude]}
            icon={markerIcon}
            eventHandlers={{ click: () => onSelect?.(f.id) }}
          >
            <Popup>
              <span className="font-medium">{f.name}</span>
              <br />
              {f.district}, {f.state}
            </Popup>
          </Marker>
        ))}
        {pickedLocation && <Marker position={[pickedLocation.lat, pickedLocation.lng]} icon={markerIcon} />}
        {pickable && <ClickHandler onPick={onPick} />}
      </MapContainer>
    </div>
  );
}
