import { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  unit,
  helper,
  icon,
}: {
  label: string;
  value: string | number;
  unit?: string;
  helper?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 shadow-subtle">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-text-secondary">{label}</span>
        {icon}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-metric text-text-primary">{value}</span>
        {unit && <span className="text-sm text-text-muted">{unit}</span>}
      </div>
      {helper && <div className="mt-1 text-xs text-text-muted">{helper}</div>}
    </div>
  );
}
