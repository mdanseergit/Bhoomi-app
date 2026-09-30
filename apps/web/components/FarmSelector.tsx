"use client";

import { Farm } from "@/lib/types";

export function FarmSelector({
  farms,
  selectedId,
  onSelect,
}: {
  farms: Farm[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (farms.length === 0) return null;
  return (
    <select
      aria-label="Select farm"
      value={selectedId ?? ""}
      onChange={(e) => onSelect(e.target.value)}
      className="rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-text-primary shadow-subtle focus:border-primary"
    >
      {farms.map((f) => (
        <option key={f.id} value={f.id}>
          {f.name} &middot; {f.district}
        </option>
      ))}
    </select>
  );
}
