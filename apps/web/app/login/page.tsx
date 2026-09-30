"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertCircle, Eye, EyeOff, ServerCrash } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n-context";
import { ApiError, BACKEND_UNREACHABLE_MESSAGE, NetworkError } from "@/lib/api";
import { BhoomiLogo } from "@/components/BhoomiLogo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useI18n();
  const [serverError, setServerError] = useState<string | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    setBackendDown(false);
    setSubmitting(true);
    try {
      await login(values.email, values.password);
    } catch (err) {
      if (err instanceof NetworkError) {
        setBackendDown(true);
        setServerError(err.message);
      } else if (err instanceof ApiError) {
        // 5xx or 404 from the proxy means the backend did not answer at all.
        if (err.status >= 500 || err.status === 404 || err.message === BACKEND_UNREACHABLE_MESSAGE) {
          setBackendDown(true);
          setServerError(BACKEND_UNREACHABLE_MESSAGE);
        } else {
          setServerError(err.message);
        }
      } else {
        setServerError("Unable to sign in. Please try again.");
      }
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
            <linearGradient id="wave-green-deep" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#1B3E12" stopOpacity="0.95" />
              <stop offset="45%" stopColor="#2D5A1A" stopOpacity="0.8" />
              <stop offset="80%" stopColor="#4D7F31" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            {/* Vibrant mid wave gradient fading to soft white */}
            <linearGradient id="wave-green-mid" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#2A5418" stopOpacity="0.75" />
              <stop offset="45%" stopColor="#5B933C" stopOpacity="0.55" />
              <stop offset="80%" stopColor="#8CCB67" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            {/* Soft accent wave */}
            <linearGradient id="wave-green-soft" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#78B852" stopOpacity="0.4" />
              <stop offset="60%" stopColor="#B3E293" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Layer 1: Back Wave */}
          <path
            fill="url(#wave-green-soft)"
            d="M0,0 L1440,0 L1440,340 C1300,400 1150,280 980,330 C800,380 620,460 450,420 C280,380 120,450 0,410 Z"
          />

          {/* Layer 2: Mid Wave */}
          <path
            fill="url(#wave-green-mid)"
            d="M0,0 L1440,0 L1440,280 C1280,340 1100,250 920,290 C740,330 560,270 380,310 C200,350 80,290 0,310 Z"
          />

          {/* Layer 3: Foreground Main Rich Wave fading smoothly into white */}
          <path
            fill="url(#wave-green-deep)"
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
            <p className="mt-1 text-xs font-medium text-emerald-100 drop-shadow-sm sm:text-sm">{t("appTagline")}</p>
          </div>
        </div>

        {/* ── Sign in card ──────────────────────────────────────────── */}
        <div className="rounded-2xl border border-emerald-900/10 bg-white/95 p-8 shadow-2xl shadow-emerald-950/10 backdrop-blur-md">
          <h2 className="text-section-title text-text-primary">{t("signIn")}</h2>
          <form className="mt-4 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
            <div>
              <label htmlFor="email" className="text-xs font-medium text-text-secondary">
                {t("email")}
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                {...register("email")}
                aria-invalid={!!errors.email}
              />
              {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
            </div>
            <div>
              <label htmlFor="password" className="text-xs font-medium text-text-secondary">
                {t("password")}
              </label>
              <div className="relative mt-1">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Your password"
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 pr-10 text-sm transition focus:border-primary focus:ring-2 focus:ring-primary/10"
                  {...register("password")}
                  aria-invalid={!!errors.password}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-text-muted transition hover:text-text-secondary"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-danger">{errors.password.message}</p>}
            </div>
            {serverError && (
              <div
                role="alert"
                className={
                  backendDown
                    ? "rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
                    : "rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-danger"
                }
              >
                <p className="flex items-start gap-1.5">
                  {backendDown ? (
                    <ServerCrash size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                  ) : (
                    <AlertCircle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                  )}
                  <span>{serverError}</span>
                </p>
                {backendDown && (
                  <p className="mt-1.5 pl-[20px] text-[11px] text-amber-800">
                    This is a service problem, not a wrong password. Please try again in a moment or contact your
                    administrator.
                  </p>
                )}
              </div>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-deep hover:shadow-md active:scale-[0.98] disabled:opacity-60"
            >
              {submitting ? t("signingIn") : t("signIn")}
            </button>
          </form>
          <p className="mt-5 text-center text-xs text-text-secondary">
            {t("newToBhoomi")}{" "}
            <Link href="/register" className="font-medium text-primary-deep hover:underline">
              {t("createAccount")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
