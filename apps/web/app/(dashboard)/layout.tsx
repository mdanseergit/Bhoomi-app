"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n-context";
import { FarmProvider } from "@/lib/farm-context";
import { Sidebar, BottomNav } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { BhoomiLogo } from "@/components/BhoomiLogo";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 logo-pulse">
          <BhoomiLogo size={56} />
          <p className="text-sm font-medium text-text-muted">{t("loading")}</p>
        </div>
      </div>
    );
  }

  return (
    <FarmProvider>
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <Topbar />
          <main className="flex-1 px-4 pb-20 pt-5 md:px-6 md:pb-8">{children}</main>
        </div>
        <BottomNav />
      </div>
    </FarmProvider>
  );
}
