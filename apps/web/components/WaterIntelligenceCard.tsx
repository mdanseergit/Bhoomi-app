"use client";

import React from "react";
import { Droplets, CloudRain, Gauge, Satellite, FlaskConical, AlertCircle } from "lucide-react";
import { FarmWaterIntelligence } from "@/lib/types";
import { FreshnessBadge } from "./FreshnessBadge";
import { titleCase } from "@/lib/format";

interface WaterIntelligenceCardProps {
  water?: FarmWaterIntelligence | null;
  isLoading?: boolean;
}

export function WaterIntelligenceCard({ water, isLoading }: WaterIntelligenceCardProps) {
  if (isLoading) {
    return (
      <div className="animate-pulse rounded-card border border-border bg-surface p-5 shadow-subtle">
        <div className="h-5 w-40 rounded bg-muted/20" />
        <div className="mt-4 grid grid-cols-3 gap-3">
          <div className="h-20 rounded bg-muted/20" />
          <div className="h-20 rounded bg-muted/20" />
          <div className="h-20 rounded bg-muted/20" />
        </div>
      </div>
    );
  }

  if (!water) return null;

  const stressIndex = water.water_stress_index || water.drought_index || "normal";
  const rainAmount = water.precipitation_recent_mm ?? water.rainfall_mm;

  return (
    <section className="rounded-card border border-border bg-surface p-5 shadow-subtle">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Droplets className="text-primary" size={18} />
          <h2 className="text-section-title text-text-primary">Water Intelligence Layer</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Water Stress Index:</span>
          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${
            stressIndex === "critical"
              ? "bg-rose-500/10 text-rose-600"
              : stressIndex === "high"
              ? "bg-amber-500/10 text-amber-600"
              : "bg-emerald-500/10 text-emerald-600"
          }`}>
            {titleCase(stressIndex)}
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Lab Soil Moisture */}
        <div className="rounded-md border border-border bg-background/50 p-3.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <FlaskConical size={14} className="text-primary" />
              Lab Soil Test
            </span>
            <FreshnessBadge
              status={water.soil_moisture_lab?.freshness || (water.soil_moisture_lab?.value_pct != null ? "RECENT" : "DATA NOT AVAILABLE")}
              observedAt={water.soil_moisture_lab?.observed_at || water.soil_moisture_lab?.sampled_at}
              showDetails={false}
            />
          </div>
          <p className="mt-2 text-2xl font-bold text-text-primary">
            {water.soil_moisture_lab?.value_pct != null
              ? `${Math.round(water.soil_moisture_lab.value_pct)}%`
              : "—"}
          </p>
          <p className="mt-1 text-[11px] text-text-muted">
            Source: {water.soil_moisture_lab?.source || "Laboratory / Soil Health Card"}
          </p>
        </div>

        {/* Satellite Soil Moisture */}
        <div className="rounded-md border border-border bg-background/50 p-3.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <Satellite size={14} className="text-primary" />
              Satellite Estimate
            </span>
            <FreshnessBadge
              status={water.soil_moisture_satellite?.freshness || (water.soil_moisture_satellite?.value_pct != null ? "RECENT" : "DATA NOT AVAILABLE")}
              observedAt={water.soil_moisture_satellite?.observed_at}
              showDetails={false}
            />
          </div>
          <p className="mt-2 text-2xl font-bold text-text-primary">
            {water.soil_moisture_satellite?.value_pct != null
              ? `${Math.round(water.soil_moisture_satellite.value_pct)}%`
              : "—"}
          </p>
          <p className="mt-1 text-[11px] text-text-muted">
            Source: {water.soil_moisture_satellite?.source || "ISRO Bhoonidhi / Sentinel-1"}
          </p>
        </div>

        {/* In-situ Sensor */}
        <div className="rounded-md border border-border bg-background/50 p-3.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <Gauge size={14} className="text-text-muted" />
              In-situ Sensor
            </span>
            <FreshnessBadge
              status={water.soil_moisture_sensor?.freshness || "DATA NOT AVAILABLE"}
              observedAt={water.soil_moisture_sensor?.observed_at}
              showDetails={false}
            />
          </div>
          <p className="mt-2 text-2xl font-bold text-text-primary">
            {water.soil_moisture_sensor?.value_pct != null
              ? `${Math.round(water.soil_moisture_sensor.value_pct)}%`
              : "Not Configured"}
          </p>
          <p className="mt-1 text-[11px] text-text-muted">
            IoT Field Sensor Telemetry
          </p>
        </div>

        {/* Rainfall & Irrigation */}
        <div className="rounded-md border border-border bg-background/50 p-3.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <CloudRain size={14} className="text-primary" />
              Precipitation (24h)
            </span>
          </div>
          <p className="mt-2 text-2xl font-bold text-text-primary">
            {rainAmount != null
              ? `${rainAmount.toFixed(1)} mm`
              : "—"}
          </p>
          <p className="mt-1 text-[11px] text-text-muted">
            {water.irrigation_type ? `Type: ${titleCase(water.irrigation_type)}` : "Rainfed"} &middot; {water.water_source || "Natural rainfall"}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-md bg-muted/10 px-3 py-2 text-xs text-text-secondary">
        <AlertCircle size={14} className="shrink-0 text-text-muted" />
        <span>
          <strong>Measurement Principle:</strong> Laboratory soil tests measure exact chemical saturation, field sensors measure real-time capacitance, and satellites measure microwave dielectric reflection. They are maintained separately to prevent false equivalences.
        </span>
      </div>
    </section>
  );
}
