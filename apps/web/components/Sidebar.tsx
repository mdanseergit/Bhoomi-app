"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Sprout,
  BrainCircuit,
  Stethoscope,
  Network,
  Megaphone,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n-context";
import { BhoomiLogo } from "./BhoomiLogo";

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { t } = useI18n();

  const NAV_ITEMS = [
    { href: "/overview", label: t("overview"), icon: LayoutDashboard },
    { href: "/farms", label: t("myFarms"), icon: Sprout },
    { href: "/intelligence", label: t("intelligence"), icon: BrainCircuit },
    { href: "/crop-doctor", label: t("cropDoctor"), icon: Stethoscope },
    { href: "/cooperation", label: t("cooperation"), icon: Network },
    { href: "/advisories", label: t("advisories"), icon: Megaphone },
    { href: "/settings", label: t("settings"), icon: Settings },
  ];

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface px-3 py-5 md:flex">
      {/* Logo section */}
      <div className="mb-6 flex items-center gap-3 px-2 pb-4 border-b border-border">
        <BhoomiLogo size={40} />
        <div>
          <p className="text-base font-bold tracking-tight text-text-primary">BHOOMI</p>
          <p className="text-[10px] font-medium text-text-muted">{t("appTagline")}</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1" aria-label="Primary navigation">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`group flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                active
                  ? "bg-primary-soft text-primary-deep shadow-sm"
                  : "text-text-secondary hover:bg-primary-50 hover:text-text-primary"
              }`}
            >
              <Icon
                size={16}
                aria-hidden="true"
                className={`transition-colors ${active ? "text-primary" : "text-text-muted group-hover:text-primary-light"}`}
              />
              {item.label}
            </Link>
          );
        })}
        {user?.role === "platform_admin" && (
          <Link
            href="/admin"
            className={`group flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
              pathname?.startsWith("/admin")
                ? "bg-primary-soft text-primary-deep shadow-sm"
                : "text-text-secondary hover:bg-primary-50 hover:text-text-primary"
            }`}
          >
            <ShieldCheck
              size={16}
              aria-hidden="true"
              className={`transition-colors ${pathname?.startsWith("/admin") ? "text-primary" : "text-text-muted group-hover:text-primary-light"}`}
            />
            {t("admin")}
          </Link>
        )}
      </nav>

      <div className="mt-auto rounded-lg bg-primary-50 px-3 py-2.5 text-[11px] leading-relaxed text-text-muted">
        {t("disclaimer")}
      </div>
    </aside>
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const { t } = useI18n();

  const NAV_ITEMS = [
    { href: "/overview", label: t("overview"), icon: LayoutDashboard },
    { href: "/farms", label: t("myFarms"), icon: Sprout },
    { href: "/intelligence", label: t("intelligence"), icon: BrainCircuit },
    { href: "/crop-doctor", label: t("cropDoctor"), icon: Stethoscope },
    { href: "/cooperation", label: t("cooperation"), icon: Network },
  ];

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-20 flex justify-around border-t border-border bg-surface/95 py-1.5 backdrop-blur-sm md:hidden"
      aria-label="Primary navigation"
    >
      {NAV_ITEMS.map((item) => {
        const active = pathname?.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] font-medium transition-colors ${
              active ? "text-primary-deep" : "text-text-muted"
            }`}
          >
            <Icon size={18} aria-hidden="true" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
