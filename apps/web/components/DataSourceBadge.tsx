import { Database, Satellite, CloudSun, FlaskConical } from "lucide-react";
import { formatRelativeTime } from "@/lib/format";

const ICONS: Record<string, typeof Database> = {
  weather: CloudSun,
  vegetation: Satellite,
  soil: FlaskConical,
  default: Database,
};

export function DataSourceBadge({
  source,
  label,
  timestamp,
}: {
  source: string;
  label: string;
  timestamp?: string | null;
  isDev?: boolean;
}) {
  const Icon = ICONS[source] ?? ICONS.default ?? Database;
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-text-secondary">
      <Icon size={13} className="text-primary" aria-hidden="true" />
      <span className="font-medium text-text-primary">{label}</span>
      {timestamp && <span className="text-text-muted">Updated {formatRelativeTime(timestamp)}</span>}
    </div>
  );
}
