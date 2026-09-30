import { ShieldAlert, Info } from "lucide-react";
import { DiseaseAnalysisResult } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { titleCase } from "@/lib/format";

export function DiseaseResult({ result }: { result: DiseaseAnalysisResult }) {
  const severityMap: Record<string, string> = { none: "low", low: "low", moderate: "moderate", high: "high" };
  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-subtle">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Possible disease</p>
          <h3 className="text-section-title text-text-primary">{titleCase(result.possible_disease)}</h3>
          <p className="mt-0.5 text-sm text-text-secondary">Crop: {titleCase(result.crop)}</p>
        </div>
        <StatusBadge severity={severityMap[result.severity] || "unknown"} label={`${Math.round(result.confidence * 100)}% confidence`} />
      </div>



      {result.ai_explanation && (
        <div className="mt-3 rounded-md border border-border bg-background p-3 text-sm leading-relaxed text-text-secondary">
          {result.ai_explanation}
        </div>
      )}

      <div className="mt-4">
        <p className="text-[13px] font-semibold text-text-primary">Recommended next steps</p>
        <ul className="mt-1.5 space-y-1">
          {result.recommended_actions.map((a, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
              {a}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 border-t border-border pt-3">
        <p className="flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
          <ShieldAlert size={14} aria-hidden="true" /> Limitations
        </p>
        <ul className="mt-1.5 space-y-1">
          {result.limitations.map((l, i) => (
            <li key={i} className="text-xs text-text-muted">
              {l}
            </li>
          ))}
        </ul>
      </div>

      {result.top_k.length > 1 && (
        <div className="mt-4 border-t border-border pt-3">
          <p className="text-[13px] font-semibold text-text-primary">Other possibilities considered</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {result.top_k.slice(1).map((t, i) => (
              <span key={i} className="rounded-full border border-border px-2.5 py-1 text-xs text-text-secondary">
                {titleCase(t.class)} &middot; {Math.round(t.confidence * 100)}%
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
