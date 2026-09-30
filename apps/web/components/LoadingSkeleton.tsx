export function LoadingSkeleton({ rows = 3, className = "" }: { rows?: number; className?: string }) {
  return (
    <div className={`animate-pulse space-y-2 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 rounded bg-border/60" style={{ width: `${100 - i * 8}%` }} />
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-card border border-border bg-surface p-4">
      <LoadingSkeleton rows={3} />
    </div>
  );
}
