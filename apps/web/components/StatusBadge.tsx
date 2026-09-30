import { AlertTriangle, CheckCircle2, XCircle, HelpCircle } from "lucide-react";
import { titleCase } from "@/lib/format";

type Severity = "low" | "moderate" | "high" | "critical" | "unknown";

const CONFIG: Record<Severity, { bg: string; text: string; icon: typeof CheckCircle2; label: string }> = {
  low: { bg: "bg-primary-soft", text: "text-primary-deep", icon: CheckCircle2, label: "Low" },
  moderate: { bg: "bg-amber-50", text: "text-warning", icon: AlertTriangle, label: "Moderate" },
  high: { bg: "bg-red-50", text: "text-danger", icon: AlertTriangle, label: "High" },
  critical: { bg: "bg-red-100", text: "text-danger", icon: XCircle, label: "Critical" },
  unknown: { bg: "bg-gray-100", text: "text-text-muted", icon: HelpCircle, label: "No data" },
};

export function StatusBadge({ severity, label }: { severity: string; label?: string }) {
  const config = CONFIG[(severity as Severity) in CONFIG ? (severity as Severity) : "unknown"];
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.bg} ${config.text}`}
    >
      <Icon size={13} aria-hidden="true" />
      <span>{label || config.label || titleCase(severity)}</span>
    </span>
  );
}
