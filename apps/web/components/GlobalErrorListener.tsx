"use client";

import { useEffect, useState } from "react";

/**
 * Surfaces otherwise-silent client-side failures (uncaught exceptions,
 * unhandled promise rejections) as a visible banner. Without this, a
 * failure in an event handler (e.g. a form submit) can look like "nothing
 * happened" to the user while the real error only appears in the browser
 * console, which is hard to retrieve inside an embedded preview.
 */
export function GlobalErrorListener() {
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "SCRIPT" || target.tagName === "LINK")) {
        const src = (target as HTMLScriptElement).src || (target as HTMLLinkElement).href;
        setMessage(`Failed to load a required file (${src || "unknown"}). Try a hard refresh of this page.`);
        return;
      }
      setMessage(event.message || "An unexpected error occurred.");
    };
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const text =
        reason instanceof Error ? reason.message : typeof reason === "string" ? reason : "An unexpected error occurred.";
      setMessage(text);
    };
    // `capture: true` is required to observe resource-loading failures
    // (script/link tags), which do not bubble and never reach a
    // non-capturing window listener.
    window.addEventListener("error", onError, true);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError, true);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  if (!message) return null;

  return (
    <div className="fixed inset-x-0 top-0 z-[999] flex items-start justify-center px-4 pt-3">
      <div className="flex max-w-lg items-start gap-3 rounded-md border border-danger/30 bg-white px-4 py-3 text-xs text-danger shadow-lg">
        <span className="font-semibold">Client error:</span>
        <span className="flex-1 break-words">{message}</span>
        <button onClick={() => setMessage(null)} className="font-medium text-text-muted hover:text-text-primary">
          Dismiss
        </button>
      </div>
    </div>
  );
}
