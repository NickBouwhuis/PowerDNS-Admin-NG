import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Account {
  id: number;
  name: string;
  description: string | null;
}

export interface Template {
  id: number;
  name: string;
  description: string | null;
}

export function useAccounts() {
  return useQuery<Account[]>({
    queryKey: ["lookups", "accounts"],
    queryFn: () => api.get<Account[]>("/api/v2/lookups/accounts"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTemplates() {
  return useQuery<Template[]>({
    queryKey: ["lookups", "templates"],
    queryFn: () => api.get<Template[]>("/api/v2/lookups/templates"),
    staleTime: 5 * 60 * 1000,
  });
}
