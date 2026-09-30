import { ModelRegistryEntry } from "@/lib/types";
import { titleCase } from "@/lib/format";

const STATUS_STYLE: Record<string, string> = {
  published: "bg-primary-soft text-primary-deep",
  pending_review: "bg-amber-50 text-warning",
  draft: "bg-gray-100 text-text-muted",
  requested: "bg-amber-50 text-warning",
  approved: "bg-primary-soft text-primary-deep",
  rejected: "bg-red-50 text-danger",
  deprecated: "bg-gray-100 text-text-muted",
};

export function ModelCard({ model, onSelect }: { model: ModelRegistryEntry; onSelect?: () => void }) {
  return (
    <button
      onClick={onSelect}
      className="w-full rounded-card border border-border bg-surface p-4 text-left shadow-subtle transition hover:border-text-muted"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-card-title text-text-primary">{model.name}</p>
          <p className="text-xs text-text-secondary">
            {model.version} &middot; {titleCase(model.model_type)} &middot; {titleCase(model.crop)}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${STATUS_STYLE[model.status] || "bg-gray-100 text-text-muted"}`}>
          {titleCase(model.status)}
        </span>
      </div>
      {model.accuracy != null && (
        <p className="mt-2 text-xs text-text-muted">Reported accuracy: {Math.round(model.accuracy * 100)}%</p>
      )}
    </button>
  );
}
