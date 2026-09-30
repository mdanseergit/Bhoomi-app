"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, TrendingUp, CloudSun, Satellite, FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { FarmTimelineResponse, TimelineObservation } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

interface FarmTimelineViewProps {
  farmId: string;
}

export function FarmTimelineView({ farmId }: FarmTimelineViewProps) {
  const [windowRange, setWindowRange] = useState<string>("30d");

  const { data, isLoading } = useQuery({
    queryKey: ["farm-timeline", farmId, windowRange],
    queryFn: () =>
      api.get<FarmTimelineResponse>(`/api/v1/farms/${farmId}/timeline?window=${windowRange}`),
    enabled: !!farmId,
  });

  const windows = [
    { key: "1d", label: "24 Hours" },
    { key: "7d", label: "7 Days" },
    { key: "30d", label: "30 Days" },
    { key: "90d", label: "90 Days" },
    { key: "season", label: "Season" },
    { key: "year", label: "1 Year" },
  ];

  return (
    <section className="rounded-card border border-border bg-surface p-5 shadow-subtle">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <History className="text-primary" size={18} />
          <div>
            <h2 className="text-section-title text-text-primary">Historical Telemetry Timeline</h2>
            <p className="text-xs text-text-secondary">
              Immutable time-series records across satellite, weather, and soil observations
            </p>
          </div>
        </div>

        {/* Window Selector */}
        <div className="flex rounded-md border border-border bg-background p-0.5 text-xs font-medium">
          {windows.map((w) => (
            <button
              key={w.key}
              onClick={() => setWindowRange(w.key)}
              className={`rounded px-2.5 py-1 transition ${
                windowRange === w.key
                  ? "bg-primary text-white shadow-xs"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-2 py-4">
            <div className="h-10 animate-pulse rounded bg-muted/20" />
            <div className="h-10 animate-pulse rounded bg-muted/20" />
          </div>
        ) : !data || data.timeline.length === 0 ? (
          <div className="py-8 text-center text-sm text-text-muted">
            <TrendingUp size={24} className="mx-auto mb-2 text-text-muted/60" />
            <p>No historical observations recorded in this {windowRange} window.</p>
            <p className="mt-1 text-xs text-text-secondary">
              Telemetry accumulates automatically as periodic synchronizations occur.
            </p>
          </div>
        ) : (
          <div className="max-h-72 overflow-y-auto space-y-2">
            {data.timeline.map((obs: TimelineObservation, idx: number) => {
              const Icon =
                obs.domain === "satellite"
                  ? Satellite
                  : obs.domain === "weather"
                  ? CloudSun
                  : FlaskConical;

              return (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-md border border-border/60 bg-background/40 px-3.5 py-2 text-xs"
                >
                  <div className="flex items-center gap-2.5">
                    <Icon size={14} className="text-primary" />
                    <div>
                      <span className="font-semibold uppercase tracking-wider text-text-primary">
                        {obs.indicator}
                      </span>
                      <span className="ml-2 text-text-muted">
                        ({obs.source})
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <span className="font-mono text-sm font-semibold text-text-primary">
                      {obs.value != null ? obs.value : "—"} {obs.unit}
                    </span>
                    <span className="text-[11px] text-text-muted min-w-[70px] text-right">
                      {formatRelativeTime(obs.observed_at)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
