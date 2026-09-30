"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Advisory } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { EvidencePanel } from "./EvidencePanel";
import { titleCase } from "@/lib/format";

export function AdvisoryCard({ advisory }: { advisory: Advisory }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{titleCase(advisory.type)}</span>
          <h3 className="text-card-title text-text-primary">{advisory.title}</h3>
        </div>
        <StatusBadge severity={advisory.severity} />
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{advisory.summary}</p>

      {advisory.actions.length > 0 && (
        <ul className="mt-3 space-y-1">
          {advisory.actions.map((a, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
              <span>{a.title}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-center justify-between text-xs text-text-muted">
        <span>Confidence: {Math.round(advisory.confidence * 100)}% &middot; {titleCase(advisory.generated_by)}</span>
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1 font-medium text-text-primary hover:text-primary-deep"
          aria-expanded={open}
        >
          Why? {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {open && (
        <div className="mt-3">
          <EvidencePanel
            evidence={advisory.evidence}
            why={advisory.actions.map((a) => a.reason).join(" ") || "Generated from BHOOMI's deterministic agriculture rules."}
          />
        </div>
      )}
    </div>
  );
}
