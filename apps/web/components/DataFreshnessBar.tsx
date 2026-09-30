"use client";

import React from "react";
import { CloudSun, FlaskConical, Satellite, Sprout, ShieldAlert, Droplets, Info } from "lucide-react";
import { FarmDataStatusResponse } from "@/lib/types";
import { FreshnessBadge } from "./FreshnessBadge";

interface DataFreshnessBarProps {
  dataStatus?: FarmDataStatusResponse | null;
  isLoading?: boolean;
  onViewSources?: () => void;
}

export function DataFreshnessBar({ dataStatus, isLoading, onViewSources }: DataFreshnessBarProps) {
  if (isLoading) {
    return (
      <div className="flex animate-pulse items-center gap-4 rounded-card border border-border bg-surface px-4 py-3 text-xs text-text-muted">
        <div className="h-4 w-24 rounded bg-muted/20" />
        <div className="h-4 w-32 rounded bg-muted/20" />
        <div className="h-4 w-28 rounded bg-muted/20" />
      </div>
    );
  }

  if (!dataStatus) return null;

  const domains = [
    {
      key: "weather",
      label: "Weather",
      icon: CloudSun,
      domain: dataStatus.domains.weather,
      expected: "15-60 min updates",
    },
    {
      key: "satellite",
      label: "Satellite",
      icon: Satellite,
      domain: dataStatus.domains.satellite,
      expected: "5-day revisit cycle",
    },
    {
      key: "soil",
      label: "Soil",
      icon: FlaskConical,
      domain: dataStatus.domains.soil,
      expected: "Periodic lab testing",
    },
    {
      key: "water",
      label: "Water",
      icon: Droplets,
      domain: dataStatus.domains.water,
      expected: "Composite observation",
    },
    {
      key: "crop",
      label: "Crop",
      icon: Sprout,
      domain: dataStatus.domains.crop,
      expected: "Farmer provided",
    },
    {
      key: "disease",
      label: "Disease",
      icon: ShieldAlert,
      domain: dataStatus.domains.disease,
      expected: "On image diagnosis",
    },
  ];

  return (
    <div className="rounded-card border border-border bg-surface p-3.5 shadow-subtle">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
            Telemetry Provenance & Freshness
          </p>
          <span className="text-[11px] text-text-secondary">
            &middot; Natural Domain Update Frequencies
          </span>
        </div>
        {onViewSources && (
          <button
            onClick={onViewSources}
            className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            <Info size={13} />
            Data Sources & Licenses
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {domains.map(({ key, label, icon: Icon, domain, expected }) => {
          const status = domain?.status || "DATA NOT AVAILABLE";
          return (
            <div
              key={key}
              className="flex flex-col justify-between rounded-md border border-border/60 bg-background/60 p-2.5 transition hover:border-border"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
                  <Icon size={13} className="text-text-muted" />
                  <span>{label}</span>
                </div>
              </div>

              <div className="mt-2">
                <FreshnessBadge
                  status={status}
                  observedAt={domain?.observed_at || domain?.last_updated}
                  source={domain?.source}
                  showDetails={true}
                  className="w-full justify-start text-[11px]"
                />
              </div>

              <p className="mt-1.5 text-[10px] text-text-muted truncate" title={expected}>
                {expected}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
