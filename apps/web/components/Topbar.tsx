"use client";

import { useState } from "react";
import { Bell, Check, ChevronDown, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n-context";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Notification } from "@/lib/types";
import { formatRelativeTime, titleCase } from "@/lib/format";
import { BhoomiLogo } from "./BhoomiLogo";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function Topbar() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<Notification[]>("/api/v1/notifications"),
    enabled: !!user,
    refetchInterval: 60_000,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/notifications/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const unreadCount = notifications?.filter((n) => !n.read_at).length ?? 0;

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-4 md:px-6">
      {/* Mobile logo */}
      <div className="flex items-center gap-2 md:hidden">
        <BhoomiLogo size={28} />
        <p className="text-base font-bold text-text-primary">BHOOMI</p>
      </div>
      <div className="hidden md:block" />

      <div className="flex items-center gap-2">
        {/* Language switcher */}
        <LanguageSwitcher />

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen((v) => !v)}
            aria-label={`${t("notifications")}${unreadCount ? `, ${unreadCount} unread` : ""}`}
            className="relative rounded-lg p-2 text-text-secondary transition hover:bg-primary-50 hover:text-text-primary"
          >
            <Bell size={18} aria-hidden="true" />
            {unreadCount > 0 && (
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-danger" aria-hidden="true" />
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 z-30 mt-2 w-80 animate-in rounded-xl border border-border bg-surface p-2 shadow-lg">
              <p className="px-2 py-1 text-xs font-semibold text-text-secondary">{t("notifications")}</p>
              {!notifications || notifications.length === 0 ? (
                <p className="px-2 py-3 text-xs text-text-muted">{t("noNotifications")}</p>
              ) : (
                <ul className="max-h-80 overflow-y-auto">
                  {notifications.map((n) => (
                    <li
                      key={n.id}
                      role="button"
                      tabIndex={0}
                      aria-label={n.read_at ? n.title : `${n.title} (unread)`}
                      onClick={() => {
                        if (!n.read_at) markRead.mutate(n.id);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          if (!n.read_at) markRead.mutate(n.id);
                        }
                      }}
                      className={`group cursor-pointer rounded-lg px-2 py-2 text-xs transition hover:bg-primary-50 ${
                        n.read_at ? "opacity-60" : "bg-primary-soft/40"
                      }`}
                    >
                      <div className="flex items-start gap-1.5">
                        {!n.read_at && (
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-danger" aria-hidden="true" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-text-primary">{n.title}</p>
                          <p className="text-text-secondary">{n.message}</p>
                          <p className="mt-0.5 text-text-muted">{formatRelativeTime(n.created_at)}</p>
                        </div>
                        {!n.read_at && (
                          <Check
                            size={13}
                            className="mt-0.5 shrink-0 text-text-muted opacity-0 transition group-hover:opacity-100"
                            aria-hidden="true"
                          />
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-text-primary transition hover:bg-primary-50"
          >
            <span className="hidden sm:inline">{user?.full_name}</span>
            <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary-deep">
              {user ? titleCase(user.role) : ""}
            </span>
            <ChevronDown
              size={14}
              aria-hidden="true"
              className={`transition-transform duration-200 ${menuOpen ? "rotate-180" : ""}`}
            />
          </button>
          {menuOpen && (
            <div className="absolute right-0 z-30 mt-2 w-48 animate-in rounded-xl border border-border bg-surface p-1.5 shadow-lg">
              <button
                onClick={logout}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-text-primary transition hover:bg-primary-50"
              >
                <LogOut size={14} aria-hidden="true" /> {t("logOut")}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
