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
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-background">
      {/* ── Top Organic Wavy Green Section ───────────────────────────── */}
      <div className="absolute inset-x-0 top-0 h-80 overflow-hidden bg-gradient-to-br from-[#102408] via-[#1b3810] to-[#2c5519] shadow-md">
        {/* Ambient glow spots */}
        <div className="pointer-events-none absolute -left-10 -top-10 h-72 w-72 rounded-full bg-emerald-500/20 blur-3xl" />
        <div className="pointer-events-none absolute right-0 top-10 h-64 w-64 rounded-full bg-lime-400/15 blur-3xl" />

        {/* Wavy bottom border */}
        <div className="absolute inset-x-0 bottom-0 h-16 w-full leading-none">
          <svg className="block h-full w-full" viewBox="0 0 1440 80" preserveAspectRatio="none">
            <path
              fill="#F4F7F1"
              d="M0,32L60,42.7C120,53,240,75,360,74.7C480,75,600,53,720,42.7C840,32,960,32,1080,48C1200,64,1320,75,1380,80L1440,85L1440,80L0,80Z"
            />
          </svg>
        </div>
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
            <p className="mt-1 text-xs font-medium text-emerald-200">{t("appTagline")}</p>
          </div>
        </div>

        {/* ── Sign in card ──────────────────────────────────────────── */}
        <div className="rounded-2xl border border-emerald-900/10 bg-surface p-8 shadow-xl backdrop-blur-sm">
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
