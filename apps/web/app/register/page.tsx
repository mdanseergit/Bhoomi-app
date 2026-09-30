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
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-gradient-to-b from-[#0F2208] via-[#1A370E] to-[#274E16] px-4 py-12">
      {/* ── Seamless Ambient Organic Glow & Contour Waves ─────────────── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Soft atmospheric blurred glowing orbs */}
        <div className="absolute -left-24 -top-24 h-96 w-96 rounded-full bg-emerald-500/20 blur-[100px]" />
        <div className="absolute right-0 top-1/4 h-80 w-80 rounded-full bg-lime-400/15 blur-[100px]" />
        <div className="absolute bottom-0 left-1/3 h-96 w-96 rounded-full bg-emerald-600/15 blur-[120px]" />

        {/* Subtle, soft organic wave contours that blend into the ambiance */}
        <svg
          className="absolute inset-0 h-full w-full opacity-15"
          viewBox="0 0 1440 900"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            fill="url(#wave-grad-reg-1)"
            d="M0,160L80,186.7C160,213,320,267,480,261.3C640,256,800,192,960,186.7C1120,181,1280,235,1360,261.3L1440,288L1440,900L1360,900C1280,900,1120,900,960,900C800,900,640,900,480,900C320,900,160,900,80,900L0,900Z"
          />
          <path
            fill="url(#wave-grad-reg-2)"
            opacity="0.6"
            d="M0,380L60,400C120,420,240,460,360,453.3C480,447,600,393,720,389.3C840,385,960,431,1080,442.7C1200,455,1320,433,1380,422.3L1440,411.7L1440,900L1380,900C1320,900,1200,900,1080,900C960,900,840,900,720,900C600,900,480,900,360,900C240,900,120,900,60,900L0,900Z"
          />
          <defs>
            <linearGradient id="wave-grad-reg-1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#4A7C2E" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#1E3A10" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="wave-grad-reg-2" x1="100%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#6FAE45" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#0F2208" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      {/* Language switcher in top-right corner */}
      <div className="fixed right-4 top-4 z-50">
        <LanguageSwitcher />
      </div>

      <div className="relative z-10 w-full max-w-sm px-4 py-8 animate-fade-in-up">
        {/* ── Centered Logo ─────────────────────────────────────────── */}
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="rounded-2xl bg-white/10 p-2 shadow-lg backdrop-blur-md border border-white/20">
            <BhoomiLogo size={76} />
          </div>
          <div className="text-center text-white">
            <h1 className="text-2xl font-bold tracking-tight text-white drop-shadow-sm">{t("appName")}</h1>
            <p className="mt-1 text-xs font-medium text-emerald-200">{t("signUp")}</p>
          </div>
        </div>

        {/* ── Registration card ─────────────────────────────────────── */}
        <div className="rounded-2xl border border-emerald-900/10 bg-surface p-8 shadow-xl backdrop-blur-sm">
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
