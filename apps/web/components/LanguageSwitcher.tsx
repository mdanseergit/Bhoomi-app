"use client";

import { useState, useRef, useEffect } from "react";
import { Globe, Check, ChevronDown } from "lucide-react";
import { useI18n, SUPPORTED_LANGUAGES } from "@/lib/i18n-context";

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const currentLang = SUPPORTED_LANGUAGES.find((l) => l.code === lang);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = SUPPORTED_LANGUAGES.filter(
    (l) =>
      l.label.toLowerCase().includes(search.toLowerCase()) ||
      l.nativeLabel.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 ${
          open
            ? "bg-primary/10 text-primary-deep shadow-sm"
            : "text-text-secondary hover:bg-primary/5 hover:text-text-primary"
        }`}
        aria-label={t("language")}
        title={t("language")}
      >
        <Globe size={16} className="shrink-0" aria-hidden="true" />
        {!compact && (
          <>
            <span className="hidden sm:inline">{currentLang?.nativeLabel}</span>
            <ChevronDown
              size={12}
              className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
              aria-hidden="true"
            />
          </>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 origin-top-right animate-in rounded-xl border border-border bg-surface p-2 shadow-lg ring-1 ring-black/5">
          {/* Search */}
          <div className="px-2 pb-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search language…"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
              autoFocus
            />
          </div>
          {/* Language list */}
          <div className="max-h-72 overflow-y-auto">
            {filtered.map((l) => {
              const isActive = l.code === lang;
              return (
                <button
                  key={l.code}
                  onClick={() => {
                    setLang(l.code);
                    setOpen(false);
                    setSearch("");
                  }}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-all duration-150 ${
                    isActive
                      ? "bg-primary/10 font-semibold text-primary-deep"
                      : "text-text-primary hover:bg-background"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-base">{l.nativeLabel}</span>
                    <span className="text-xs text-text-muted">{l.label}</span>
                  </div>
                  {isActive && <Check size={16} className="text-primary" />}
                </button>
              );
            })}
            {filtered.length === 0 && (
              <p className="px-3 py-4 text-center text-sm text-text-muted">No languages found</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
