"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Farm } from "./types";
import { useAuth } from "./auth-context";

interface FarmContextValue {
  farms: Farm[];
  isLoading: boolean;
  error: unknown;
  selectedFarmId: string | null;
  selectedFarm: Farm | null;
  selectFarm: (id: string) => void;
  refetch: () => void;
}

const FarmContext = createContext<FarmContextValue | undefined>(undefined);

const STORAGE_KEY = "bhoomi_selected_farm";

export function FarmProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [selectedFarmId, setSelectedFarmId] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["farms"],
    queryFn: () => api.get<Farm[]>("/api/v1/farms"),
    enabled: !!user,
  });

  const farms = data ?? [];

  useEffect(() => {
    if (farms.length === 0) return;
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    const validStored = stored && farms.some((f) => f.id === stored) ? stored : null;
    const fallbackId = validStored ?? farms[0]?.id ?? null;
    setSelectedFarmId((prev) => (prev && farms.some((f) => f.id === prev) ? prev : fallbackId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const selectFarm = (id: string) => {
    setSelectedFarmId(id);
    if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, id);
  };

  const selectedFarm = farms.find((f) => f.id === selectedFarmId) || null;

  return (
    <FarmContext.Provider value={{ farms, isLoading, error, selectedFarmId, selectedFarm, selectFarm, refetch }}>
      {children}
    </FarmContext.Provider>
  );
}

export function useFarms() {
  const ctx = useContext(FarmContext);
  if (!ctx) throw new Error("useFarms must be used within FarmProvider");
  return ctx;
}
