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
    <div className="relative -mx-4 -mt-5 mb-8 overflow-hidden md:-mx-6">
      {/* ── Top Rich Emerald Gradient Background ──────────────────────── */}
      <div className="relative bg-gradient-to-br from-[#112409] via-[#1c3811] to-[#2b5418] px-5 pb-16 pt-7 text-white md:px-8 md:pb-20 md:pt-9 shadow-md">
        {/* Decorative glowing ambient spots */}
        <div className="pointer-events-none absolute -left-20 -top-20 h-64 w-64 rounded-full bg-emerald-500/15 blur-3xl" />
        <div className="pointer-events-none absolute right-10 top-0 h-72 w-72 rounded-full bg-lime-400/10 blur-3xl" />

        <div className="relative z-10 mx-auto max-w-5xl">
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

      {/* ── Layered Wavy SVG Curve Transition ─────────────────────────── */}
      <div className="relative -mt-10 h-10 w-full overflow-hidden leading-none md:-mt-12 md:h-12">
        {/* Soft back wave */}
        <svg
          className="absolute inset-0 h-full w-full opacity-35"
          viewBox="0 0 1440 80"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            fill="#2B5418"
            d="M0,32L48,42.7C96,53,192,75,288,74.7C384,75,480,53,576,42.7C672,32,768,32,864,42.7C960,53,1056,75,1152,69.3C1248,64,1344,32,1392,16L1440,0L1440,80L1392,80C1344,80,1248,80,1152,80C1056,80,960,80,864,80C768,80,672,80,576,80C480,80,384,80,288,80C192,80,96,80,48,80L0,80Z"
          />
        </svg>
        {/* Main foreground wave matching body bg #F4F7F1 */}
        <svg
          className="relative block h-full w-full"
          viewBox="0 0 1440 80"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            fill="#F4F7F1"
            d="M0,24L48,29.3C96,35,192,45,288,53.3C384,61,480,67,576,58.7C672,51,768,29,864,24C960,19,1056,29,1152,37.3C1248,45,1344,51,1392,53.3L1440,56L1440,80L1392,80C1344,80,1248,80,1152,80C1056,80,960,80,864,80C768,80,672,80,576,80C480,80,384,80,288,80C192,80,96,80,48,80L0,80Z"
          />
        </svg>
      </div>
    </div>
  );
}
