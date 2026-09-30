"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useFarms } from "@/lib/farm-context";
import { api } from "@/lib/api";
import {
  IntelligenceResponse,
  Notification,
  FarmDataStatusResponse,
  FarmWaterIntelligence,
  FarmSourcesResponse,
} from "@/lib/types";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { WavyGreenHero } from "@/components/WavyGreenHero";
import { WaterIntelligenceCard } from "@/components/WaterIntelligenceCard";
import { FarmTimelineView } from "@/components/FarmTimelineView";
import { SourceProvenanceModal } from "@/components/SourceProvenanceModal";
import { formatRelativeTime, titleCase } from "@/lib/format";
import Link from "next/link";

export default function OverviewPage() {
  const { user } = useAuth();
  const { farms, selectedFarm, selectedFarmId, selectFarm, isLoading: farmsLoading } = useFarms();
  const [showSourcesModal, setShowSourcesModal] = useState<boolean>(false);

  const {
    data: intelligence,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["intelligence", selectedFarmId],
    queryFn: () => api.get<IntelligenceResponse>(`/api/v1/farms/${selectedFarmId}/intelligence`),
    enabled: !!selectedFarmId,
  });

  const { data: dataStatus, isLoading: statusLoading } = useQuery({
    queryKey: ["farm-data-status", selectedFarmId],
    queryFn: () => api.get<FarmDataStatusResponse>(`/api/v1/farms/${selectedFarmId}/data-status`),
    enabled: !!selectedFarmId,
  });

  const { data: waterData, isLoading: waterLoading } = useQuery({
    queryKey: ["farm-water", selectedFarmId],
    queryFn: () => api.get<FarmWaterIntelligence>(`/api/v1/farms/${selectedFarmId}/water`),
    enabled: !!selectedFarmId,
  });

  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["farm-sources", selectedFarmId],
    queryFn: () => api.get<FarmSourcesResponse>(`/api/v1/farms/${selectedFarmId}/sources`),
    enabled: !!selectedFarmId,
  });

  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<Notification[]>("/api/v1/notifications"),
  });

  const greetingHour = new Date().getHours();
  const greeting = greetingHour < 12 ? "Good morning" : greetingHour < 17 ? "Good afternoon" : "Good evening";

  if (farmsLoading) return <CardSkeleton />;

  if (farms.length === 0) {
    return (
      <EmptyState
        title="No farms yet"
        description="Create your first farm to start seeing weather, soil, vegetation and health intelligence in one place."
        action={
          <Link href="/farms" className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-deep">
            Create a farm
          </Link>
        }
      />
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* ── Wavy Green Hero Section ─────────────────────────────────── */}
      <WavyGreenHero
        greeting={greeting}
        userName={user?.full_name}
        role={user?.role ? titleCase(user.role) : "Farmer"}
        selectedFarm={selectedFarm}
        farms={farms}
        selectedFarmId={selectedFarmId}
        onSelectFarm={selectFarm}
        onRefresh={() => refetch()}
        isRefreshing={isFetching}
        temperature={intelligence?.weather.temperature_c}
        weatherCondition={intelligence?.weather.condition}
        healthScore={intelligence?.health.score}
        waterStatus={intelligence?.health.water_stress}
        soilStatus={intelligence?.health.soil_health}
      />

      {isLoading && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      )}

      {!!error && <ErrorState message="Farm intelligence temporarily unavailable. Showing the most recent verified data where possible." onRetry={() => refetch()} />}

      {intelligence && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard
              label="Farm Health"
              value={intelligence.health.has_data ? Math.round(intelligence.health.score ?? 0) : "Not enough data"}
              unit={intelligence.health.has_data ? "/ 100" : undefined}
              helper={
                intelligence.health.has_data
                  ? "BHOOMI Intelligence Score"
                  : "Add soil, weather or vegetation data to calculate a score"
              }
            />
            <MetricCard
              label="Climate Risk"
              value={formatRisk(intelligence.health.climate_risk)}
              helper={<StatusBadge severity={intelligence.health.climate_risk} />}
            />
            <MetricCard
              label="Water Status"
              value={
                intelligence.health.water_stress === "low"
                  ? "Adequate"
                  : formatRisk(intelligence.health.water_stress)
              }
              helper={<StatusBadge severity={intelligence.health.water_stress} />}
            />
            <MetricCard
              label="Soil Health"
              value={formatRisk(intelligence.health.soil_health)}
              helper={<StatusBadge severity={intelligence.health.soil_health} />}
            />
          </div>

          {/* Water Intelligence Layer */}
          <WaterIntelligenceCard water={waterData} isLoading={waterLoading} />

          <section className="rounded-card border border-border bg-surface p-5 shadow-subtle">
            <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Current farm</p>
            <h2 className="text-section-title text-text-primary">{intelligence.farm.name}</h2>
            <p className="text-sm text-text-secondary">
              {titleCase(intelligence.farm.crop || "No crop set")} &middot; {titleCase(intelligence.farm.crop_stage || "Stage unknown")}
            </p>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div>
                <p className="text-xs text-text-muted">NDVI</p>
                <p className="text-lg font-semibold text-text-primary">
                  {intelligence.vegetation.ndvi?.toFixed(2) ?? "No data"}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted">Soil Moisture</p>
                <p className="text-lg font-semibold text-text-primary">
                  {intelligence.soil.moisture != null ? `${Math.round(intelligence.soil.moisture)}%` : "No data"}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted">Rainfall Probability</p>
                <p className="text-lg font-semibold text-text-primary">
                  {intelligence.weather.rain_probability_pct != null ? `${Math.round(intelligence.weather.rain_probability_pct)}%` : "No data"}
                </p>
              </div>
            </div>
          </section>

          {/* Historical Telemetry Timeline */}
          {selectedFarmId && <FarmTimelineView farmId={selectedFarmId} />}

          <section>
            <h2 className="mb-2 text-section-title text-text-primary">Today&apos;s Intelligence</h2>
            <div className="space-y-2">
              {intelligence.advisories.slice(0, 3).map((a) => (
                <div key={a.id} className="rounded-card border border-border bg-surface p-4 shadow-subtle">
                  <p className="text-sm text-text-primary">{a.summary}</p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-section-title text-text-primary">Active Alerts</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <AlertTile label="Rainfall Risk" severity={intelligence.health.climate_risk} />
              <AlertTile label="Disease Risk" severity={intelligence.health.disease_risk} />
              <AlertTile label="Vegetation Stress" severity={intelligence.health.vegetation_stress} />
              <AlertTile label="Water Stress" severity={intelligence.health.water_stress} />
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-section-title text-text-primary">Recent Activity</h2>
            <div className="rounded-card border border-border bg-surface shadow-subtle">
              {(notifications ?? []).slice(0, 5).map((n, i) => (
                <div key={n.id} className={`flex items-center justify-between px-4 py-3 text-sm ${i > 0 ? "border-t border-border" : ""}`}>
                  <span className="text-text-primary">{n.title}</span>
                  <span className="text-xs text-text-muted">{formatRelativeTime(n.created_at)}</span>
                </div>
              ))}
              {(!notifications || notifications.length === 0) && (
                <p className="px-4 py-4 text-sm text-text-muted">No recent activity yet.</p>
              )}
            </div>
          </section>

          {/* Source Provenance Modal */}
          <SourceProvenanceModal
            isOpen={showSourcesModal}
            onClose={() => setShowSourcesModal(false)}
            sourcesData={sourcesData}
            isLoading={sourcesLoading}
          />
        </>
      )}
    </div>
  );
}

function formatRisk(severity: string) {
  return severity === "unknown" ? "No data" : titleCase(severity);
}

function AlertTile({ label, severity }: { label: string; severity: string }) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <p className="text-xs font-medium text-text-secondary">{label}</p>
      <div className="mt-2">
        <StatusBadge severity={severity} />
      </div>
    </div>
  );
}
