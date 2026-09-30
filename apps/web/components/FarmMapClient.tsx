"use client";

import dynamic from "next/dynamic";

export const FarmMapClient = dynamic(() => import("./FarmMap").then((m) => m.FarmMap), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center rounded-card border border-border bg-background text-sm text-text-muted">
      Loading map…
    </div>
  ),
});
