import { Leaf } from "lucide-react";
import { IntelligenceResponse } from "@/lib/types";
import { DataSourceBadge } from "./DataSourceBadge";

export function VegetationCard({ vegetation }: { vegetation: IntelligenceResponse["vegetation"] }) {
  const trend = vegetation.trend_7d_pct;
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <div className="flex items-center justify-between">
        <p className="text-card-title text-text-primary">Vegetation</p>
        <Leaf size={16} className="text-primary" aria-hidden="true" />
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-metric text-text-primary">{vegetation.ndvi != null ? vegetation.ndvi.toFixed(2) : "--"}</span>
        <span className="text-sm text-text-muted">NDVI</span>
      </div>
      {trend != null && (
        <p className={`text-sm ${trend >= 0 ? "text-success" : "text-danger"}`}>
          {trend >= 0 ? "+" : ""}
          {trend.toFixed(1)}% over 7 days
        </p>
      )}
      <div className="mt-3">
        <DataSourceBadge source="vegetation" label="Satellite Earth Observation" timestamp={vegetation.observation_date} />
      </div>
    </div>
  );
}
