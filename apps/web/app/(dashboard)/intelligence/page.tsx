"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCcw, Sparkles } from "lucide-react";
import { useFarms } from "@/lib/farm-context";
import { api } from "@/lib/api";
import {
  IntelligenceResponse,
  FarmDataStatusResponse,
  FarmWaterIntelligence,
  FarmSourcesResponse,
} from "@/lib/types";
import { FarmSelector } from "@/components/FarmSelector";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { WeatherCard } from "@/components/WeatherCard";
import { SoilCard } from "@/components/SoilCard";
import { VegetationCard } from "@/components/VegetationCard";
import { AdvisoryCard } from "@/components/AdvisoryCard";
import { BhoomiIntelligenceReport } from "@/components/BhoomiIntelligenceReport";
import { WavyGreenHero } from "@/components/WavyGreenHero";
import { WaterIntelligenceCard } from "@/components/WaterIntelligenceCard";
import { FarmTimelineView } from "@/components/FarmTimelineView";
import { SourceProvenanceModal } from "@/components/SourceProvenanceModal";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import { titleCase } from "@/lib/format";

export default function IntelligencePage() {
  const { farms, selectedFarm, selectedFarmId, selectFarm, isLoading: farmsLoading } = useFarms();
  const queryClient = useQueryClient();
  const [showSourcesModal, setShowSourcesModal] = useState<boolean>(false);

  const {
    data,
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

  const handleReanalyze = async () => {
    if (!selectedFarmId) return;
    await api.post(`/api/v1/farms/${selectedFarmId}/analyze`);
    queryClient.invalidateQueries({ queryKey: ["intelligence", selectedFarmId] });
  };

  if (farmsLoading) return <CardSkeleton />;
  if (farms.length === 0) return <EmptyState title="No farms yet" description="Add a farm to see intelligence here." />;

  const reportText = data?.bhoomi_report || data?.ai_interpretation;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* ── Wavy Green Hero Section ─────────────────────────────────── */}
      <WavyGreenHero
        greeting="Farm Intelligence & Diagnostics"
        userName={data ? data.farm.name : "Field Intelligence"}
        role={data ? `${titleCase(data.farm.crop || "Crop")} · ${data.farm.area_hectares} ha` : "AI Analytics"}
        selectedFarm={selectedFarm}
        farms={farms}
        selectedFarmId={selectedFarmId}
        onSelectFarm={selectFarm}
        onRefresh={handleReanalyze}
        isRefreshing={isFetching}
        temperature={data?.weather.temperature_c}
        weatherCondition={data?.weather.condition}
        healthScore={data?.health.score}
        waterStatus={data?.health.water_stress}
        soilStatus={data?.health.soil_health}
      />

      {isLoading && <CardSkeleton />}
      {!!error && <ErrorState message="Intelligence pipeline temporarily unavailable." onRetry={() => refetch()} />}

      {data && (
        <>
          {/* Main BHOOMI Intelligence AI Report */}
          <BhoomiIntelligenceReport
            reportText={reportText}
            data={data}
            onReanalyze={handleReanalyze}
            isFetching={isFetching}
          />

          {/* Quick Metrics Bar */}
          <div className="pt-2">
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-text-muted">
              Sensor & Satellite Telemetry
            </h3>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <MetricCard
                label="Farm Health"
                value={data.health.has_data ? Math.round(data.health.score ?? 0) : "Not enough data"}
                unit={data.health.has_data ? "/ 100" : undefined}
                helper={
                  data.health.has_data
                    ? `${Math.round(data.health.data_coverage * 100)}% data coverage`
                    : `Missing: ${data.health.missing_inputs.join(", ") || "farm data"}`
                }
              />
              <MetricCardWithBadge label="Climate Risk" severity={data.health.climate_risk} />
              <MetricCardWithBadge label="Soil Condition" severity={data.health.soil_health} />
              <MetricCardWithBadge label="Water Stress" severity={data.health.water_stress} />
              <MetricCardWithBadge label="Disease Risk" severity={data.health.disease_risk} />
            </div>
          </div>

          {/* Sensor Detail Cards */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <WeatherCard weather={data.weather} />
            <VegetationCard vegetation={data.vegetation} />
            <SoilCard soil={data.soil} />
          </div>

          {/* Water Intelligence Layer */}
          <WaterIntelligenceCard water={waterData} isLoading={waterLoading} />

          {/* Health Score Calculation Factor Breakdown */}
          <section>
            <h2 className="mb-2 text-section-title text-text-primary">Why this score?</h2>
            <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
              <ul className="space-y-2">
                {data.health.factors.slice(0, 8).map((f, i) => (
                  <li key={i} className="flex items-center justify-between text-sm">
                    <span className="text-text-primary">{f.detail}</span>
                    <span className="ml-3 shrink-0 text-xs text-text-muted">{Math.round(f.impact * 100)}% weight</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 grid grid-cols-5 gap-2 text-center text-xs text-text-muted border-t border-border pt-3">
                {Object.entries(data.health.breakdown).map(([key, v]) => (
                  <div key={key}>
                    <p className="font-semibold text-text-primary">
                      {v.score != null ? Math.round(v.score) : "—"}
                    </p>
                    <p>{titleCase(key)}</p>
                    <p>{Math.round(v.weight * 100)}%</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Historical Telemetry Timeline */}
          {selectedFarmId && <FarmTimelineView farmId={selectedFarmId} />}

          {/* Today's Rule-Engine Actions */}
          {data.advisories && data.advisories.length > 0 && (
            <section>
              <h2 className="mb-2 text-section-title text-text-primary">Verified Agronomic Advisories</h2>
              <div className="space-y-3">
                {data.advisories.map((a) => (
                  <AdvisoryCard key={a.id} advisory={a} />
                ))}
              </div>
            </section>
          )}

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

function MetricCardWithBadge({ label, severity }: { label: string; severity: string }) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <p className="text-[13px] font-medium text-text-secondary">{label}</p>
      <div className="mt-2">
        <StatusBadge severity={severity} />
      </div>
    </div>
  );
}
