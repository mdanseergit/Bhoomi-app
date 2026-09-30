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
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-gradient-to-b from-[#EEF5E9] via-[#F8FAF6] to-[#FFFFFF] px-4 py-12">
      {/* ── Organic Wavy Green Layers with White Gradient Transition ──────── */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[560px] overflow-hidden">
        {/* Soft glowing ambient spots */}
        <div className="absolute -left-20 -top-20 h-80 w-80 rounded-full bg-emerald-400/25 blur-3xl" />
        <div className="absolute right-0 top-10 h-72 w-72 rounded-full bg-lime-300/25 blur-3xl" />

        {/* Sweeping Layered Organic Waves blending into white */}
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 1440 560"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            {/* Deep rich wave gradient fading down to transparent white */}
            <linearGradient id="wave-green-reg-deep" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#1B3E12" stopOpacity="0.95" />
              <stop offset="45%" stopColor="#2D5A1A" stopOpacity="0.8" />
              <stop offset="80%" stopColor="#4D7F31" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            {/* Vibrant mid wave gradient fading to soft white */}
            <linearGradient id="wave-green-reg-mid" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#2A5418" stopOpacity="0.75" />
              <stop offset="45%" stopColor="#5B933C" stopOpacity="0.55" />
              <stop offset="80%" stopColor="#8CCB67" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            {/* Soft accent wave */}
            <linearGradient id="wave-green-reg-soft" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#78B852" stopOpacity="0.4" />
              <stop offset="60%" stopColor="#B3E293" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Layer 1: Back Wave */}
          <path
            fill="url(#wave-green-reg-soft)"
            d="M0,0 L1440,0 L1440,340 C1300,400 1150,280 980,330 C800,380 620,460 450,420 C280,380 120,450 0,410 Z"
          />

          {/* Layer 2: Mid Wave */}
          <path
            fill="url(#wave-green-reg-mid)"
            d="M0,0 L1440,0 L1440,280 C1280,340 1100,250 920,290 C740,330 560,270 380,310 C200,350 80,290 0,310 Z"
          />

          {/* Layer 3: Foreground Main Rich Wave fading smoothly into white */}
          <path
            fill="url(#wave-green-reg-deep)"
            d="M0,0 L1440,0 L1440,210 C1320,250 1160,190 1000,230 C820,275 650,205 480,240 C300,280 140,220 0,240 Z"
          />
        </svg>

        {/* Smooth mask to ensure complete seamless fade into white gradient */}
        <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-white via-white/80 to-transparent" />
      </div>

      {/* Language switcher in top-right corner */}
      <div className="fixed right-4 top-4 z-50">
        <LanguageSwitcher />
      </div>

      <div className="relative z-10 w-full max-w-sm px-4 py-8 animate-fade-in-up">
        {/* ── Centered Logo ─────────────────────────────────────────── */}
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="rounded-2xl bg-white/90 p-2.5 shadow-lg backdrop-blur-md border border-emerald-900/10">
            <BhoomiLogo size={72} />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight text-white drop-shadow-md sm:text-3xl">{t("appName")}</h1>
            <p className="mt-1 text-xs font-medium text-emerald-100 drop-shadow-sm sm:text-sm">{t("signUp")}</p>
          </div>
        </div>

        {/* ── Registration card ─────────────────────────────────────── */}
        <div className="rounded-2xl border border-emerald-900/10 bg-white/95 p-8 shadow-2xl shadow-emerald-950/10 backdrop-blur-md">
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
