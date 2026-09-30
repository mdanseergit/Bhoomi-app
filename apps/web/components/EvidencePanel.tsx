import { EvidenceItem } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export function EvidencePanel({ evidence, why }: { evidence: EvidenceItem[]; why?: string }) {
  if (evidence.length === 0) return null;
  return (
    <div className="rounded-card border border-border bg-background p-3">
      <p className="text-[13px] font-semibold text-text-primary">Evidence</p>
      <ul className="mt-2 space-y-1.5">
        {evidence.map((e, i) => (
          <li key={i} className="flex flex-wrap items-center justify-between gap-x-3 text-xs text-text-secondary">
            <span className="font-medium text-text-primary">{e.source.replace(/_/g, " ")}</span>
            <span className="flex-1 text-right sm:text-left">{e.value}</span>
            <span className="text-text-muted">{formatRelativeTime(e.timestamp)}</span>
          </li>
        ))}
      </ul>
      {why && (
        <div className="mt-3 border-t border-border pt-2">
          <p className="text-[13px] font-semibold text-text-primary">Why BHOOMI recommends this</p>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">{why}</p>
        </div>
      )}
    </div>
  );
}
