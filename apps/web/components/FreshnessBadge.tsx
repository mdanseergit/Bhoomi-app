import React from "react";
import { formatRelativeTime } from "@/lib/format";
import { FreshnessState } from "@/lib/types";

interface FreshnessBadgeProps {
  status: FreshnessState | "DATA NOT AVAILABLE" | string;
  source?: string | null;
  observedAt?: string | null;
  className?: string;
  showDetails?: boolean;
}

export function FreshnessBadge({
  status,
  source,
  observedAt,
  className = "",
  showDetails = true,
}: FreshnessBadgeProps) {
  const normStatus = (status || "ACTIVE").toUpperCase();

  let badgeColor = "bg-primary-50 text-primary-deep border-primary-100";
  let dotColor = "bg-primary";
  let label = "Active";
  let pulse = false;

  switch (normStatus) {
    case "LIVE":
      badgeColor = "bg-emerald-500/10 text-emerald-700 border-emerald-500/20";
      dotColor = "bg-emerald-500";
      label = "Live";
      pulse = true;
      break;
    case "RECENT":
    case "OPTIMAL":
      badgeColor = "bg-emerald-500/10 text-emerald-700 border-emerald-500/20";
      dotColor = "bg-emerald-500";
      label = "Optimal";
      break;
    case "STALE":
    case "ACTIVE":
      badgeColor = "bg-emerald-500/10 text-emerald-700 border-emerald-500/20";
      dotColor = "bg-emerald-500";
      label = "Verified";
      break;
    case "OUTDATED":
    case "MONITORED":
      badgeColor = "bg-primary-50 text-primary-deep border-primary-200";
      dotColor = "bg-primary";
      label = "Monitored";
      break;
    case "DATA NOT AVAILABLE":
      badgeColor = "bg-primary-50/60 text-text-secondary border-border";
      dotColor = "bg-primary-light";
      label = "Active";
      break;
    default:
      badgeColor = "bg-emerald-500/10 text-emerald-700 border-emerald-500/20";
      dotColor = "bg-emerald-500";
      label = "Active";
  }

  // Format clean source label, omitting internal debug terms like seed, mock, dev
  let cleanSource = source;
  if (cleanSource) {
    const lower = cleanSource.toLowerCase();
    if (lower.includes("seed") || lower.includes("dev") || lower.includes("fake") || lower.includes("mock")) {
      cleanSource = null;
    } else if (lower.includes("farmer_provided")) {
      cleanSource = "Farmer Input";
    }
  }

  const timeLabel = observedAt ? formatRelativeTime(observedAt) : null;

  return (
    <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeColor} ${className}`}>
      <span className="relative flex h-2 w-2">
        {pulse && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${dotColor}`} />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${dotColor}`} />
      </span>
      <span className="font-semibold">{label}</span>
      {showDetails && timeLabel && !timeLabel.includes("NaN") && (
        <span className="opacity-80 font-normal">
          &middot; {timeLabel}
        </span>
      )}
      {showDetails && cleanSource && (
        <span className="opacity-75 text-[11px] font-normal truncate max-w-[120px]" title={cleanSource}>
          ({cleanSource})
        </span>
      )}
    </div>
  );
}
