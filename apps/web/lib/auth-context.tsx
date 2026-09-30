"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, clearTokens, getAccessToken, setTokens } from "./api";
import type { Role, User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { full_name: string; email: string; password: string; role: Role; state?: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    try {
      if (!getAccessToken()) {
        setUser(null);
        return;
      }
      const me = await api.get<User>("/api/v1/auth/me");
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.post<{ access_token: string; refresh_token: string }>(
        "/api/v1/auth/login",
        { email, password },
        { skipAuth: true }
      );
      setTokens(tokens.access_token, tokens.refresh_token);
      // Fetch the profile before navigating: if this fails the tokens are
      // dropped by refreshUser, and pushing to /overview would just bounce the
      // user back to /login with no explanation.
      const me = await api.get<User>("/api/v1/auth/me");
      setUser(me);
      setLoading(false);
      router.push("/overview");
    },
    [router]
  );

  const register = useCallback(
    async (payload: { full_name: string; email: string; password: string; role: Role; state?: string }) => {
      const tokens = await api.post<{ access_token: string; refresh_token: string }>("/api/v1/auth/register", payload, {
        skipAuth: true,
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      const me = await api.get<User>("/api/v1/auth/me");
      setUser(me);
      setLoading(false);
      router.push("/overview");
    },
    [router]
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
