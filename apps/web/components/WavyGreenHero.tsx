"use client";

import React from "react";
import { Sprout, RefreshCcw, MapPin, CloudSun, ShieldCheck, Droplets, Sparkles } from "lucide-react";
import { FarmSelector } from "./FarmSelector";
import { Farm } from "@/lib/types";

interface WavyGreenHeroProps {
  greeting: string;
  userName?: string;
  role?: string;
  selectedFarm?: Farm | null;
  farms: Farm[];
  selectedFarmId?: string | null;
  onSelectFarm: (id: string) => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  weatherCondition?: string | null;
  temperature?: number | null;
  healthScore?: number | null;
  waterStatus?: string | null;
  soilStatus?: string | null;
}

export function WavyGreenHero({
  greeting,
  userName = "Farmer",
  role = "Farmer",
  selectedFarm,
  farms,
  selectedFarmId,
  onSelectFarm,
  onRefresh,
  isRefreshing = false,
  weatherCondition,
  temperature,
  healthScore,
  waterStatus,
  soilStatus,
}: WavyGreenHeroProps) {
  const firstName = userName?.split(" ")[0] || "Farmer";
  const locationText = selectedFarm
    ? `${selectedFarm.village ? selectedFarm.village + ", " : ""}${selectedFarm.district || ""}, ${selectedFarm.state}`
    : "Select a farm to view live intelligence";

  return (
    <div className="relative mb-6 overflow-hidden rounded-2xl md:rounded-3xl border border-emerald-900/15 bg-gradient-to-br from-[#112509] via-[#1A3810] to-[#295117] p-6 md:p-8 text-white shadow-xl shadow-emerald-950/10 transition-all">
      {/* Decorative glowing ambient spots that blend seamlessly */}
      <div className="pointer-events-none absolute -left-20 -top-20 h-64 w-64 rounded-full bg-emerald-500/20 blur-3xl" />
      <div className="pointer-events-none absolute right-10 top-0 h-72 w-72 rounded-full bg-lime-400/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-1/4 h-52 w-52 rounded-full bg-emerald-400/10 blur-3xl" />

      {/* Subtle organic topographic wave contours blending softly into the background */}
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full opacity-15"
        viewBox="0 0 1200 400"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          fill="none"
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="1.5"
          d="M0,80 C300,160 600,0 900,100 C1050,150 1150,110 1200,90"
        />
        <path
          fill="none"
          stroke="rgba(110,174,69,0.3)"
          strokeWidth="2"
          d="M0,180 C250,90 550,240 850,160 C1000,120 1120,200 1200,170"
        />
        <path
          fill="none"
          stroke="rgba(163,230,53,0.2)"
          strokeWidth="1.5"
          d="M0,280 C350,330 650,210 950,280 C1080,310 1160,260 1200,240"
        />
      </svg>

      <div className="relative z-10">
          {/* Header Row: Title & Actions */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-950/50 px-2.5 py-0.5 text-xs font-semibold text-emerald-300 backdrop-blur-md">
                  <Sparkles size={12} className="text-emerald-400" />
                  BHOOMI Intelligence Platform
                </span>
                <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs text-white/80">
                  <ShieldCheck size={12} className="text-emerald-400" />
                  {role}
                </span>
              </div>

              <h1 className="mt-2 text-2xl font-bold tracking-tight text-white md:text-3xl">
                {greeting}, {firstName}
              </h1>

              <p className="mt-1 flex items-center gap-1.5 text-xs text-emerald-200/90 md:text-sm">
                <MapPin size={13} className="shrink-0 text-emerald-400" />
                <span>{locationText}</span>
                {temperature != null && (
                  <>
                    <span className="opacity-50">&middot;</span>
                    <CloudSun size={13} className="shrink-0 text-amber-300" />
                    <span>{Math.round(temperature)}°C</span>
                    {weatherCondition && <span>({weatherCondition})</span>}
                  </>
                )}
              </p>
            </div>

            {/* Farm Selector & Refresh */}
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="rounded-lg bg-white/10 p-0.5 backdrop-blur-md">
                <FarmSelector
                  farms={farms}
                  selectedId={selectedFarmId ?? null}
                  onSelect={onSelectFarm}
                />
              </div>

              {onRefresh && (
                <button
                  onClick={onRefresh}
                  disabled={isRefreshing}
                  className="flex items-center gap-1.5 rounded-lg border border-white/20 bg-white/10 px-3.5 py-2 text-xs font-semibold text-white backdrop-blur-md transition-all hover:bg-white/20 hover:shadow-sm active:scale-95 disabled:opacity-50"
                  aria-label="Refresh intelligence data"
                >
                  <RefreshCcw size={13} className={isRefreshing ? "animate-spin" : ""} />
                  <span>{isRefreshing ? "Updating..." : "Refresh"}</span>
                </button>
              )}
            </div>
          </div>

          {/* Quick Stats Grid Pill Row */}
          {(healthScore != null || waterStatus || soilStatus) && (
            <div className="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              {healthScore != null && (
                <div className="flex items-center gap-3 rounded-xl border border-white/15 bg-white/10 p-3 backdrop-blur-md transition hover:bg-white/15">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-300">
                    <Sprout size={20} />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wider text-emerald-200/80">
                      Crop Health
                    </p>
                    <p className="text-lg font-bold text-white">
                      {Math.round(healthScore)} <span className="text-xs font-normal text-emerald-200">/ 100</span>
                    </p>
                  </div>
                </div>
              )}

              {waterStatus && (
                <div className="flex items-center gap-3 rounded-xl border border-white/15 bg-white/10 p-3 backdrop-blur-md transition hover:bg-white/15">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-500/20 text-sky-300">
                    <Droplets size={20} />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wider text-emerald-200/80">
                      Water Index
                    </p>
                    <p className="text-sm font-bold capitalize text-white">
                      {waterStatus}
                    </p>
                  </div>
                </div>
              )}

              {soilStatus && (
                <div className="flex items-center gap-3 rounded-xl border border-white/15 bg-white/10 p-3 backdrop-blur-md transition hover:bg-white/15">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/20 text-amber-300">
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wider text-emerald-200/80">
                      Soil Status
                    </p>
                    <p className="text-sm font-bold capitalize text-white">
                      {soilStatus}
                    </p>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 rounded-xl border border-white/15 bg-white/10 p-3 backdrop-blur-md transition hover:bg-white/15">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-400/20 text-emerald-300">
                  <ShieldCheck size={20} />
                </div>
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-wider text-emerald-200/80">
                    System Posture
                  </p>
                  <p className="text-sm font-bold text-white">
                    Live Monitored
                  </p>
                </div>
              </div>
            </div>
          )}
      </div>
    </div>
  );
}
