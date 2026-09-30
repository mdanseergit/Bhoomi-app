import { CloudRain, Thermometer, Wind } from "lucide-react";
import { IntelligenceResponse } from "@/lib/types";
import { DataSourceBadge } from "./DataSourceBadge";

export function WeatherCard({ weather }: { weather: IntelligenceResponse["weather"] }) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <div className="flex items-center justify-between">
        <p className="text-card-title text-text-primary">Weather</p>
        <Thermometer size={16} className="text-text-muted" aria-hidden="true" />
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-metric text-text-primary">{weather.temperature_c != null ? Math.round(weather.temperature_c) : "--"}</span>
        <span className="text-sm text-text-muted">°C</span>
      </div>
      <p className="text-sm text-text-secondary">{weather.condition || "Condition unavailable"}</p>
      <div className="mt-3 flex flex-col gap-1.5 text-xs text-text-secondary">
        <span className="flex items-center gap-1.5">
          <CloudRain size={13} className="text-text-muted" aria-hidden="true" />
          Rain probability: {weather.rain_probability_pct != null ? `${Math.round(weather.rain_probability_pct)}%` : "n/a"}
        </span>
      </div>
      <div className="mt-3">
        <DataSourceBadge source="weather" label="Meteorological Observation (IMD)" timestamp={weather.observed_at} />
      </div>
    </div>
  );
}
