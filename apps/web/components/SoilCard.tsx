import { FlaskConical } from "lucide-react";
import { IntelligenceResponse } from "@/lib/types";
import { DataSourceBadge } from "./DataSourceBadge";

export function SoilCard({ soil }: { soil: IntelligenceResponse["soil"] }) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <div className="flex items-center justify-between">
        <p className="text-card-title text-text-primary">Soil</p>
        <FlaskConical size={16} className="text-text-muted" aria-hidden="true" />
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-metric text-text-primary">{soil.ph != null ? soil.ph.toFixed(1) : "--"}</span>
        <span className="text-sm text-text-muted">pH</span>
      </div>
      <p className="text-sm text-text-secondary">
        Organic carbon {soil.organic_carbon != null ? `${soil.organic_carbon.toFixed(2)}%` : "not recorded"}
      </p>
      <div className="mt-3">
        <DataSourceBadge source="soil" label="Soil Health Card Profile" timestamp={soil.sample_date} />
      </div>
    </div>
  );
}
