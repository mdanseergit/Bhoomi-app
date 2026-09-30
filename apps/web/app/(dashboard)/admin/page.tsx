"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { CardSkeleton } from "@/components/LoadingSkeleton";
import { formatRelativeTime, titleCase } from "@/lib/format";

import { useState } from "react";
import { DataNetworkAdminView } from "@/components/DataNetworkAdminView";
import { Network, Users, FileText } from "lucide-react";

interface Overview {
  users: number;
  farms: number;
  states: number;
  models: number;
  advisories: number;
  disease_scans: number;
}
interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource: string;
  resource_id: string | null;
  result: string;
  created_at: string;
}
interface UserRow {
  id: string;
  full_name: string;
  email: string;
  role: string;
  state: string | null;
  is_active: boolean;
}

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"network" | "platform" | "audit">("network");

  useEffect(() => {
    if (!loading && user && user.role !== "platform_admin") router.replace("/overview");
  }, [loading, user, router]);

  const { data: overview, isLoading } = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () => api.get<Overview>("/api/v1/admin/overview"),
    enabled: user?.role === "platform_admin",
  });
  const { data: users } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<UserRow[]>("/api/v1/admin/users"),
    enabled: user?.role === "platform_admin",
  });
  const { data: auditLogs } = useQuery({
    queryKey: ["admin-audit-logs"],
    queryFn: () => api.get<AuditLogEntry[]>("/api/v1/admin/audit-logs"),
    enabled: user?.role === "platform_admin",
  });

  if (user?.role !== "platform_admin") return null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-page-title text-text-primary">Platform Administration</h1>
        
        {/* Navigation Tabs */}
        <div className="flex rounded-md border border-border bg-surface p-1 text-xs font-medium shadow-xs">
          <button
            onClick={() => setActiveTab("network")}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 transition ${
              activeTab === "network"
                ? "bg-primary text-white shadow-xs"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Network size={14} />
            Data Network & Providers
          </button>
          <button
            onClick={() => setActiveTab("platform")}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 transition ${
              activeTab === "platform"
                ? "bg-primary text-white shadow-xs"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Users size={14} />
            Users & Entities
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 transition ${
              activeTab === "audit"
                ? "bg-primary text-white shadow-xs"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <FileText size={14} />
            Audit Logs
          </button>
        </div>
      </div>

      {activeTab === "network" && <DataNetworkAdminView />}

      {activeTab === "platform" && (
        <>
          {isLoading ? (
            <CardSkeleton />
          ) : (
            overview && (
              <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
                <MetricCard label="Users" value={overview.users} />
                <MetricCard label="Farms" value={overview.farms} />
                <MetricCard label="States" value={overview.states} />
            <MetricCard label="Models" value={overview.models} />
            <MetricCard label="Advisories" value={overview.advisories} />
            <MetricCard label="Disease scans" value={overview.disease_scans} />
          </div>
        )
      )}

      <section>
        <h2 className="mb-2 text-section-title text-text-primary">Users</h2>
        <div className="overflow-x-auto rounded-card border border-border bg-surface shadow-subtle">
          <table className="w-full min-w-[500px] text-left text-sm">
            <thead className="border-b border-border text-xs text-text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">State</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 text-text-primary">{u.full_name}</td>
                  <td className="px-4 py-2 text-text-secondary">{u.email}</td>
                  <td className="px-4 py-2 text-text-secondary">{titleCase(u.role)}</td>
                  <td className="px-4 py-2 text-text-secondary">{u.state || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
        </>
      )}

      {activeTab === "audit" && (
        <section>
          <h2 className="mb-2 text-section-title text-text-primary">System Audit Trail</h2>
          <div className="max-h-[500px] overflow-y-auto rounded-card border border-border bg-surface shadow-subtle divide-y divide-border">
            {auditLogs?.map((log) => (
              <div key={log.id} className="flex items-center justify-between px-4 py-2.5 text-xs">
                <span className="font-semibold text-text-primary font-mono">{log.action}</span>
                <span className="text-text-secondary">{log.resource} ({log.resource_id?.slice(0, 8) || "—"})</span>
                <span className="text-text-muted">{formatRelativeTime(log.created_at)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
