import { AlertCircle, RefreshCcw } from "lucide-react";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-card border border-border bg-surface px-6 py-10 text-center"
    >
      <AlertCircle className="text-danger" size={26} aria-hidden="true" />
      <p className="text-sm text-text-secondary">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition hover:bg-background"
        >
          <RefreshCcw size={14} aria-hidden="true" /> Try again
        </button>
      )}
    </div>
  );
}
