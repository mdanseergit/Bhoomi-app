"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CooperationSummary, ModelRegistryEntry, StateNode } from "@/lib/types";
import { StateNodeCard } from "@/components/StateNodeCard";
import { ModelCard } from "@/components/ModelCard";
import { MetricCard } from "@/components/MetricCard";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import { titleCase } from "@/lib/format";

export default function CooperationPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedModel, setSelectedModel] = useState<ModelRegistryEntry | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["cooperation-summary"],
    queryFn: () => api.get<CooperationSummary>("/api/v1/cooperation/summary"),
  });

  const { data: states } = useQuery({
    queryKey: ["states"],
    queryFn: () => api.get<StateNode[]>("/api/v1/states"),
  });

  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ["models"],
    queryFn: () => api.get<ModelRegistryEntry[]>("/api/v1/models"),
  });

  const canManageModels = user?.role === "state_admin" || user?.role === "platform_admin";

  const requestAccess = async () => {
    if (!selectedModel) return;
    setRequesting(true);
    setRequestError(null);
    try {
      await api.post(`/api/v1/models/${selectedModel.id}/request`, { justification: "Requested from BHOOMI cooperation dashboard." });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      setSelectedModel(null);
    } catch (err) {
      setRequestError(err instanceof ApiError ? err.message : "Unable to request this model.");
    } finally {
      setRequesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-page-title text-text-primary">Agriculture Cooperation</h1>
        <p className="text-sm text-text-secondary">
          A unified inter-state agriculture intelligence exchange enabling state departments and research institutions to share verified crop models and agro-climatic intelligence.
        </p>
      </div>

      {summaryLoading ? (
        <CardSkeleton />
      ) : (
        <div className="grid grid-cols-3 gap-3">
          <MetricCard label="Shared Models" value={summary?.shared_models ?? 0} />
          <MetricCard label="Shared Schemas" value={summary?.shared_schemas ?? 0} />
          <MetricCard label="Model Requests" value={summary?.model_requests ?? 0} />
        </div>
      )}

      <section>
        <h2 className="mb-2 text-section-title text-text-primary">Connected Nodes</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {states?.map((node) => (
            <StateNodeCard key={node.id} node={node} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-section-title text-text-primary">Model Registry</h2>
        {modelsLoading && <CardSkeleton />}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {models?.map((m) => (
            <ModelCard key={m.id} model={m} onSelect={() => setSelectedModel(m)} />
          ))}
        </div>
      </section>

      {selectedModel && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30">
          <div className="h-full w-full max-w-md overflow-y-auto bg-surface p-6 shadow-subtle">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-section-title text-text-primary">{selectedModel.name}</h2>
              <button onClick={() => setSelectedModel(null)} className="rounded p-1 hover:bg-background" aria-label="Close">
                ✕
              </button>
            </div>
            <dl className="space-y-3 text-sm">
              <Row label="Version" value={selectedModel.version} />
              <Row label="Crop" value={titleCase(selectedModel.crop)} />
              <Row label="Type" value={titleCase(selectedModel.model_type)} />
              <Row label="Status" value={titleCase(selectedModel.status)} />
              <Row label="Visibility" value={titleCase(selectedModel.visibility)} />
              <Row label="Regions" value={selectedModel.supported_regions.join(", ") || "—"} />
              <Row label="Accuracy" value={selectedModel.accuracy != null ? `${Math.round(selectedModel.accuracy * 100)}%` : "Not reported"} />
              <Row label="License" value={selectedModel.license} />
              <Row label="Training data" value={selectedModel.training_dataset_description || "Not documented"} />
              <Row label="Compatible schema" value="agri.schema.v1" />
            </dl>

            {requestError && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-danger">{requestError}</p>}
            {canManageModels && selectedModel.visibility === "shared" && selectedModel.status === "published" && (
              <button
                onClick={requestAccess}
                disabled={requesting}
                className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-deep disabled:opacity-60"
              >
                {requesting ? "Requesting…" : "Request access"}
              </button>
            )}
            {!canManageModels && (
              <p className="mt-4 text-xs text-text-muted">Only state or platform administrators can request cross-state models.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border pb-2">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="text-right font-medium text-text-primary">{value}</dd>
    </div>
  );
}
