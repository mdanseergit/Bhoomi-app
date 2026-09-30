"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n-context";
import { BhoomiLogo } from "@/components/BhoomiLogo";

export default function RootPage() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/overview" : "/login");
  }, [loading, user, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4 logo-pulse">
        <BhoomiLogo size={72} />
        <p className="text-sm font-medium text-text-muted">{t("loading")}</p>
      </div>
    </div>
  );
}
