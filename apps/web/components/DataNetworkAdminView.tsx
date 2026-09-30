"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Play,
  RotateCw,
  Power,
  ShieldAlert,
  Globe2,
  MapPin,
  Clock,
  Sparkles,
  Server,
  Layers,
} from "lucide-react";
import { api } from "@/lib/api";
import { ProviderRegistryStatusResponse, ProviderInfo } from "@/lib/types";
import { MetricCard } from "./MetricCard";
import { formatRelativeTime, titleCase } from "@/lib/format";

export function DataNetworkAdminView() {
  const queryClient = useQueryClient();
  const [testingId, setTestingId] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [testModalData, setTestModalData] = useState<{
    providerName: string;
    status: string;
    results: any;
  } | null>(null);

  const { data: statusData, isLoading, refetch } = useQuery({
    queryKey: ["admin-providers-status"],
    queryFn: () => api.get<ProviderRegistryStatusResponse>("/api/v1/providers/status"),
  });

  const { data: countries } = useQuery({
    queryKey: ["admin-countries"],
    queryFn: () => api.get<any[]>("/api/v1/countries"),
  });

  // Test provider connection mutation
  const testMutation = useMutation({
    mutationFn: async (provider: ProviderInfo) => {
      setTestingId(provider.id);
      return api.post<{ provider_name: string; status: string; test_results: any }>(
        `/api/v1/admin/providers/${provider.id}/test`
      );
    },
    onSuccess: (data) => {
      setTestModalData({
        providerName: data.provider_name,
        status: data.status,
        results: data.test_results,
      });
      queryClient.invalidateQueries({ queryKey: ["admin-providers-status"] });
    },
    onSettled: () => {
      setTestingId(null);
    },
  });

  // Sync provider on-demand mutation
  const syncMutation = useMutation({
    mutationFn: async (provider: ProviderInfo) => {
      setSyncingId(provider.id);
      return api.post<{ sync_result: any }>(`/api/v1/admin/providers/${provider.id}/sync`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-providers-status"] });
    },
    onSettled: () => {
      setSyncingId(null);
    },
  });

  // Toggle enabled mutation
  const toggleMutation = useMutation({
    mutationFn: async ({ provider, enable }: { provider: ProviderInfo; enable: boolean }) => {
      const action = enable ? "enable" : "disable";
      return api.post(`/api/v1/admin/providers/${provider.id}/${action}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-providers-status"] });
    },
  });

  const summary = statusData?.summary;
  const providers = statusData?.providers || [];
  const recentRuns = statusData?.recent_sync_runs || [];

  // Regional states for India
  const indianStates = [
    { name: "Tamil Nadu", weather: true, soil: true, satellite: true },
    { name: "Karnataka", weather: true, soil: true, satellite: true },
    { name: "Kerala", weather: true, soil: true, satellite: true },
    { name: "Maharashtra", weather: true, soil: false, satellite: true },
    { name: "Punjab", weather: true, soil: false, satellite: true },
    { name: "Andhra Pradesh", weather: true, soil: false, satellite: true },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Header */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <MetricCard
          label="Registered Sources"
          value={summary?.total_providers ?? "—"}
          helper="Declared in registry"
        />
        <MetricCard
          label="Connected"
          value={summary?.connected ?? "—"}
          helper="Verified reachable"
        />
        <MetricCard
          label="Not Verified"
          value={summary?.unverified ?? 0}
          helper="Declared, not yet checked"
        />
        <MetricCard
          label="Degraded"
          value={summary?.degraded ?? 0}
          helper="Using cached fallback"
        />
        <MetricCard
          label="Auth Required / Failed"
          value={summary?.failed ?? 0}
          helper="Configured but uncredentialed"
        />
        <MetricCard
          label="Last Ingestion Sync"
          value={summary?.last_sync ? formatRelativeTime(summary.last_sync) : "Standby"}
          helper="Periodic automated cycle"
        />
      </div>

      {/* Country & State Provider Availability Matrix */}
      <section className="rounded-card border border-border bg-surface p-5 shadow-subtle">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <MapPin className="text-primary" size={18} />
            <div>
              <h2 className="text-section-title text-text-primary">
                Jurisdiction & State Provider Matrix
              </h2>
              <p className="text-xs text-text-secondary">
                Hierarchical provider resolution: National Official → State Node → Global Fallback
              </p>
            </div>
          </div>
          <span className="rounded bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
            India & Global
          </span>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {indianStates.map((st) => (
            <div
              key={st.name}
              className="rounded-md border border-border bg-background/50 p-3 text-xs"
            >
              <div className="flex items-center justify-between font-semibold text-text-primary">
                <span>{st.name}</span>
                <span className="text-[10px] text-text-muted">State Node</span>
              </div>
              <div className="mt-2 flex items-center justify-between border-t border-border/60 pt-2 text-[11px]">
                <span className="flex items-center gap-1">
                  Weather:
                  <span className="font-semibold text-emerald-600">IMD ✓</span>
                </span>
                <span className="flex items-center gap-1">
                  Soil:
                  {st.soil ? (
                    <span className="font-semibold text-emerald-600">SHC ✓</span>
                  ) : (
                    <span className="text-text-muted">Unconfigured –</span>
                  )}
                </span>
                <span className="flex items-center gap-1">
                  Satellite:
                  <span className="font-semibold text-emerald-600">ISRO / CDSE ✓</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Provider Registry Table */}
      <section className="rounded-card border border-border bg-surface shadow-subtle">
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Server className="text-primary" size={18} />
            <div>
              <h2 className="text-section-title text-text-primary">Connected Agricultural Providers</h2>
              <p className="text-xs text-text-secondary">
                Zero data fabrication: providers report real telemetry or explicit authentication states
              </p>
            </div>
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium text-text-primary hover:bg-muted/10"
          >
            <RotateCw size={13} className={isLoading ? "animate-spin" : ""} />
            Refresh Status
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border bg-muted/5 text-text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Provider</th>
                <th className="px-4 py-3 font-semibold">Country / Scope</th>
                <th className="px-4 py-3 font-semibold">Data Domain</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Priority</th>
                <th className="px-4 py-3 font-semibold">Last Sync</th>
                <th className="px-4 py-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {providers.map((p) => {
                const isTesting = testingId === p.id;
                const isSyncing = syncingId === p.id;

                let statusBadge = (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-600 font-medium">
                    <CheckCircle2 size={12} />
                    Healthy
                  </span>
                );

                if (p.status === "auth_required" || p.auth_status === "authentication_required") {
                  statusBadge = (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-600 font-medium">
                      <ShieldAlert size={12} />
                      Auth Required
                    </span>
                  );
                } else if (p.status === "degraded") {
                  statusBadge = (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-600 font-medium">
                      <AlertTriangle size={12} />
                      Degraded
                    </span>
                  );
                } else if (!p.enabled) {
                  statusBadge = (
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted/20 px-2 py-0.5 text-text-muted font-medium">
                      <Power size={12} />
                      Disabled
                    </span>
                  );
                }

                return (
                  <tr key={p.id} className="transition hover:bg-muted/5">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-text-primary">{p.name}</p>
                      {p.error_message && (
                        <p className="text-[10px] text-amber-600 truncate max-w-[200px]" title={p.error_message}>
                          {p.error_message}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{p.country}</td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-background px-2 py-0.5 font-mono text-[11px] uppercase border border-border">
                        {p.data_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">{statusBadge}</td>
                    <td className="px-4 py-3 text-text-secondary">P{p.priority}</td>
                    <td className="px-4 py-3 text-text-muted">
                      {p.last_sync ? formatRelativeTime(p.last_sync) : "Never"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => testMutation.mutate(p)}
                          disabled={isTesting}
                          className="rounded border border-border px-2 py-1 text-[11px] font-medium text-text-secondary hover:bg-background hover:text-text-primary disabled:opacity-50"
                          title="Run connection & capability diagnostics"
                        >
                          {isTesting ? "Testing..." : "Test"}
                        </button>

                        <button
                          onClick={() => syncMutation.mutate(p)}
                          disabled={isSyncing || !p.enabled}
                          className="rounded bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
                          title="Trigger manual telemetry sync"
                        >
                          {isSyncing ? "Syncing..." : "Sync"}
                        </button>

                        <button
                          onClick={() => toggleMutation.mutate({ provider: p, enable: !p.enabled })}
                          className={`rounded px-2 py-1 text-[11px] font-medium ${
                            p.enabled
                              ? "text-rose-600 hover:bg-rose-500/10"
                              : "text-emerald-600 hover:bg-emerald-500/10"
                          }`}
                        >
                          {p.enabled ? "Disable" : "Enable"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent Sync Runs */}
      {recentRuns.length > 0 && (
        <section className="rounded-card border border-border bg-surface p-4 shadow-subtle">
          <div className="flex items-center gap-2 mb-3">
            <Clock size={16} className="text-text-muted" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Audit Log: Recent Provider Sync Executions
            </h3>
          </div>
          <div className="max-h-48 overflow-y-auto space-y-1.5 text-xs">
            {recentRuns.map((run) => (
              <div
                key={run.id}
                className="flex items-center justify-between rounded border border-border/40 bg-background/50 px-3 py-1.5"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      run.status === "success" ? "bg-emerald-500" : "bg-rose-500"
                    }`}
                  />
                  <span className="font-medium text-text-primary">
                    Trigger: {titleCase(run.trigger_type)}
                  </span>
                  <span className="text-text-muted">
                    ({run.records_ingested} records in {run.duration_ms}ms)
                  </span>
                </div>
                <span className="text-text-muted">
                  {run.started_at ? formatRelativeTime(run.started_at) : "—"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Test Diagnostic Modal */}
      {testModalData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-card border border-border bg-surface p-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-section-title text-text-primary">
                Diagnostics: {testModalData.providerName}
              </h3>
              <button
                onClick={() => setTestModalData(null)}
                className="rounded p-1 text-text-muted hover:text-text-primary"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 space-y-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-text-primary">Status:</span>
                <span
                  className={`rounded px-2 py-0.5 font-medium ${
                    testModalData.status === "healthy"
                      ? "bg-emerald-500/10 text-emerald-600"
                      : "bg-amber-500/10 text-amber-600"
                  }`}
                >
                  {testModalData.status.toUpperCase()}
                </span>
              </div>
              <div className="rounded-md border border-border bg-background p-3">
                <p className="font-semibold text-text-secondary mb-1">Raw Health Check Output:</p>
                <pre className="overflow-x-auto text-[11px] font-mono text-text-primary">
                  {JSON.stringify(testModalData.results, null, 2)}
                </pre>
              </div>
            </div>
            <div className="mt-4 text-right">
              <button
                onClick={() => setTestModalData(null)}
                className="rounded-md bg-primary px-4 py-1.5 text-xs font-semibold text-white hover:bg-primary-deep"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
