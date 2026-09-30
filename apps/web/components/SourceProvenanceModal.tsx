"use client";

import React from "react";
import { X, ExternalLink, ShieldCheck, Database, Calendar } from "lucide-react";
import { FarmSourcesResponse } from "@/lib/types";
import { FreshnessBadge } from "./FreshnessBadge";
import { formatRelativeTime, titleCase } from "@/lib/format";

interface SourceProvenanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourcesData?: FarmSourcesResponse | null;
  isLoading?: boolean;
}

export function SourceProvenanceModal({
  isOpen,
  onClose,
  sourcesData,
  isLoading,
}: SourceProvenanceModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-card border border-border bg-surface shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Database className="text-primary" size={18} />
            <h2 className="text-section-title text-text-primary">
              Data Provenance & Source Registry
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-text-muted hover:bg-background hover:text-text-primary"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[70vh] overflow-y-auto p-4 space-y-4">
          <p className="text-xs text-text-secondary">
            BHOOMI enforces strict end-to-end data provenance. Every telemetry record and agronomic advisory traces back to verified national meteorological services, Earth observation satellites, or certified laboratory soil analyses.
          </p>

          {isLoading ? (
            <div className="space-y-3">
              <div className="h-16 animate-pulse rounded bg-muted/20" />
              <div className="h-16 animate-pulse rounded bg-muted/20" />
            </div>
          ) : !sourcesData || sourcesData.sources.length === 0 ? (
            <p className="py-6 text-center text-sm text-text-muted">
              No live provider telemetry ingested for this farm yet.
            </p>
          ) : (
            <div className="space-y-3">
              {sourcesData.sources.map((src, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-border bg-background/50 p-3.5 transition hover:border-primary/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                        {titleCase(src.domain)} Provider
                      </span>
                      <h3 className="text-sm font-semibold text-text-primary">
                        {src.provider_name}
                      </h3>
                      <p className="text-xs text-text-secondary">
                        Scope: {src.country} &middot; Type: {titleCase(src.source_type.replace(/_/g, " "))}
                      </p>
                    </div>
                    <FreshnessBadge
                      status={src.freshness}
                      observedAt={src.observed_at}
                      showDetails={true}
                    />
                  </div>

                  <div className="mt-3 flex flex-wrap items-center justify-between border-t border-border/60 pt-2 text-xs text-text-muted">
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck size={14} className="text-emerald-500" />
                      <span>License: {src.license}</span>
                    </div>
                    {src.terms_url && (
                      <a
                        href={src.terms_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 text-primary hover:underline"
                      >
                        Terms & Attribution
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border p-3 text-right">
          <button
            onClick={onClose}
            className="rounded-md bg-primary px-4 py-1.5 text-xs font-semibold text-white hover:bg-primary-deep"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
