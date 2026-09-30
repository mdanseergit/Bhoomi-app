import { StateNode } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export function StateNodeCard({ node }: { node: StateNode }) {
  const online = node.status === "online";
  return (
    <div className="flex items-center justify-between rounded-card border border-border bg-surface px-4 py-3 shadow-subtle">
      <div>
        <p className="text-sm font-semibold text-text-primary">{node.state}</p>
        <p className="text-xs text-text-muted">Last sync {formatRelativeTime(node.last_sync)}</p>
      </div>
      <span className={`flex items-center gap-1.5 text-xs font-medium ${online ? "text-success" : "text-text-muted"}`}>
        <span className={`h-2 w-2 rounded-full ${online ? "bg-success" : "bg-text-muted"}`} aria-hidden="true" />
        {online ? "Online" : "Offline"}
      </span>
    </div>
  );
}
