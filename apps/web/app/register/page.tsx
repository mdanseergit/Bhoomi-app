"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n-context";
import { ApiError } from "@/lib/api";
import { BhoomiLogo } from "@/components/BhoomiLogo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const schema = z.object({
  full_name: z.string().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  role: z.enum(["farmer", "agronomist"]),
  state: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const { t } = useI18n();
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { role: "farmer" } });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    setSubmitting(true);
    try {
      await registerUser(values);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Unable to create account. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-white px-4 py-12">
      {/* ── Separate Green Wavy Header on White Background ────────────── */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[380px] overflow-hidden">
        {/* Layer 1: Bright fresh green wave */}
        <svg
          className="absolute inset-x-0 top-0 h-full w-full"
          viewBox="0 0 1440 380"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            fill="#5C9E38"
            d="M0,0 L1440,0 L1440,320 C1300,360 1140,250 960,290 C780,330 620,380 440,350 C260,320 120,370 0,340 Z"
          />
        </svg>

        {/* Layer 2: Mid forest green wave */}
        <svg
          className="absolute inset-x-0 top-0 h-full w-full"
          viewBox="0 0 1440 380"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            fill="#2D5A18"
            d="M0,0 L1440,0 L1440,265 C1280,310 1100,225 920,255 C740,285 580,240 400,270 C220,300 80,255 0,265 Z"
          />
        </svg>

        {/* Layer 3: Foreground deep agricultural emerald wave */}
        <svg
          className="absolute inset-x-0 top-0 h-full w-full"
          viewBox="0 0 1440 380"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            fill="#1E3A10"
            d="M0,0 L1440,0 L1440,215 C1320,250 1160,190 1000,225 C820,260 660,195 480,225 C300,255 140,200 0,215 Z"
          />
        </svg>
      </div>

      {/* Language switcher in top-right corner */}
      <div className="fixed right-4 top-4 z-50">
        <LanguageSwitcher />
      </div>

      <div className="relative z-10 w-full max-w-sm px-4 py-6 animate-fade-in-up">
        {/* ── Centered Logo ─────────────────────────────────────────── */}
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="rounded-2xl bg-white/15 p-2 shadow-lg backdrop-blur-md border border-white/20">
            <BhoomiLogo size={72} />
          </div>
          <div className="text-center text-white">
            <h1 className="text-2xl font-bold tracking-tight text-white drop-shadow-md sm:text-3xl">{t("appName")}</h1>
            <p className="mt-1 text-xs font-medium text-emerald-100 drop-shadow-sm sm:text-sm">{t("signUp")}</p>
          </div>
        </div>

        {/* ── Registration card ─────────────────────────────────────── */}
        <div className="rounded-2xl border border-border bg-white p-8 shadow-xl">
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
            <div>
              <label htmlFor="full_name" className="text-xs font-medium text-text-secondary">
                {t("fullName")}
              </label>
              <input
                id="full_name"
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                {...register("full_name")}
              />
              {errors.full_name && <p className="mt-1 text-xs text-danger">{errors.full_name.message}</p>}
            </div>
            <div>
              <label htmlFor="email" className="text-xs font-medium text-text-secondary">
                {t("email")}
              </label>
              <input
                id="email"
                type="email"
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                {...register("email")}
              />
              {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
            </div>
            <div>
              <label htmlFor="password" className="text-xs font-medium text-text-secondary">
                {t("password")}
              </label>
              <input
                id="password"
                type="password"
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                {...register("password")}
              />
              {errors.password && <p className="mt-1 text-xs text-danger">{errors.password.message}</p>}
            </div>
            <div>
              <label htmlFor="role" className="text-xs font-medium text-text-secondary">
                {t("role")}
              </label>
              <select
                id="role"
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                {...register("role")}
              >
                <option value="farmer">{t("farmer")}</option>
                <option value="agronomist">{t("agronomist")}</option>
              </select>
            </div>
            <div>
              <label htmlFor="state" className="text-xs font-medium text-text-secondary">
                {t("state")}
              </label>
              <input
                id="state"
                placeholder="e.g. Tamil Nadu"
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                {...register("state")}
              />
            </div>
            {serverError && (
              <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-danger">
                {serverError}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-deep hover:shadow-md active:scale-[0.98] disabled:opacity-60"
            >
              {submitting ? t("creatingAccount") : t("createAccount")}
            </button>
          </form>
          <p className="mt-5 text-center text-xs text-text-secondary">
            {t("alreadyHaveAccount")}{" "}
            <Link href="/login" className="font-medium text-primary-deep hover:underline">
              {t("signIn")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
