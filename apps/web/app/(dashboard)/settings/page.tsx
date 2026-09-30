"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { StateNode } from "@/lib/types";
import { titleCase } from "@/lib/format";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [language, setLanguage] = useState(user?.preferred_language ?? "en");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: health } = useQuery({
    queryKey: ["system-health"],
    queryFn: () =>
      api.get<{
        database: string;
        redis: string;
        weather_provider: string;
        satellite_provider: string;
        disease_model: string;
      }>("/api/v1/health"),
  });

  // Report real capability rather than internal provider identifiers. Anything
  // the API has not confirmed reachable is shown as not connected.
  const weatherStatus = !health ? "—" : health.weather_provider === "configured" ? "Live source connected" : "Not connected";
  const satelliteStatus =
    !health
      ? "—"
      : health.satellite_provider === "none" || health.satellite_provider === "not_configured"
        ? "Not connected"
        : titleCase(health.satellite_provider);
  const diseaseStatus =
    !health || health.disease_model === "not_configured" ? "Not available" : titleCase(health.disease_model);

  const { data: states } = useQuery({
    queryKey: ["states"],
    queryFn: () => api.get<StateNode[]>("/api/v1/states"),
    enabled: !!user?.state,
  });
  const myNode = states?.find((s) => s.state === user?.state);

  const saveProfile = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.patch("/api/v1/users/me", { full_name: fullName, preferred_language: language });
      await refreshUser();
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save changes.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-page-title text-text-primary">Settings</h1>

      <SettingsSection title="Profile">
        <label className="block text-xs font-medium text-text-secondary">
          Full name
          <input className="input mt-1" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>
        <label className="mt-3 block text-xs font-medium text-text-secondary">
          Email
          <input className="input mt-1 bg-background text-text-muted" value={user?.email} disabled />
        </label>
        <label className="mt-3 block text-xs font-medium text-text-secondary">
          Role
          <input className="input mt-1 bg-background text-text-muted" value={user ? titleCase(user.role) : ""} disabled />
        </label>
        {error && <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-xs text-danger">{error}</p>}
        {saved && <p className="mt-2 rounded-md bg-primary-soft px-3 py-2 text-xs text-primary-deep">Profile updated.</p>}
        <button
          onClick={saveProfile}
          disabled={saving}
          className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-deep disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </SettingsSection>

      <SettingsSection title="Language">
        <label className="block text-xs font-medium text-text-secondary">
          Preferred language
          <select className="input mt-1" value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="ta">Tamil (தமிழ்)</option>
            <option value="hi">Hindi (हिन्दी)</option>
          </select>
        </label>
        <p className="mt-2 text-xs text-text-muted">Advisories for your farms are shown in your selected language where supported.</p>
      </SettingsSection>

      <SettingsSection title="Data & privacy">
        <p className="text-sm text-text-secondary">
          Your farm data is used to generate intelligence and advisories for your own account. Raw farm records are not shared
          across states — only approved models and schemas move through the cooperation network.
        </p>
      </SettingsSection>

      {user?.state && (
        <SettingsSection title="State node">
          {myNode ? (
            <>
              <Row label="State" value={myNode.state} />
              <Row label="Status" value={titleCase(myNode.status)} />
              <Row label="Data policy" value={myNode.data_policy} />
            </>
          ) : (
            <p className="text-sm text-text-muted">No cooperation node is registered for {user.state} yet.</p>
          )}
        </SettingsSection>
      )}

      <SettingsSection title="Data sources">
        <Row label="Database" value={health ? titleCase(health.database) : "—"} />
        <Row label="Weather" value={weatherStatus} />
        <Row label="Satellite" value={satelliteStatus} />
        <Row label="Crop Doctor" value={diseaseStatus} />
      </SettingsSection>
    </div>
  );
}

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-card border border-border bg-surface p-5 shadow-subtle">
      <h2 className="mb-3 text-section-title text-text-primary">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2 text-sm last:border-0">
      <span className="text-text-secondary">{label}</span>
      <span className="font-medium text-text-primary">{value}</span>
    </div>
  );
}
