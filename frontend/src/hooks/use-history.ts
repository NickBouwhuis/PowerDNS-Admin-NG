import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface HistoryEntry {
  id: number;
  msg: string;
  detail: Record<string, unknown> | string | null;
  created_by: string;
  created_on: string | null;
  domain_id: number | null;
}

export interface HistoryResponse {
  total: number;
  entries: HistoryEntry[];
}

export interface HistoryFilters {
  page?: number;
  per_page?: number;
  domain_name?: string;
  user_name?: string;
  date_from?: string;
  date_to?: string;
}

export function useHistory(filters: HistoryFilters = {}) {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));
  if (filters.domain_name) params.set("domain_name", filters.domain_name);
  if (filters.user_name) params.set("user_name", filters.user_name);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);

  const qs = params.toString();
  return useQuery<HistoryResponse>({
    queryKey: ["history", filters],
    queryFn: () =>
      api.get<HistoryResponse>(`/api/v2/history${qs ? `?${qs}` : ""}`),
  });
}

export function useClearHistory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete("/api/v2/history"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });
}
