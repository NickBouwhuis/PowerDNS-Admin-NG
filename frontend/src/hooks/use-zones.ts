import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  ZoneListResponse,
  ZoneListParams,
  ZoneCreateRequest,
  ZoneCreateResponse,
} from "@/types/zones";

const ZONES_KEY = "zones";

export function useZones(params: ZoneListParams) {
  const searchParams = new URLSearchParams({
    tab: params.tab,
    search: params.search,
    sort_by: params.sort_by,
    sort_dir: params.sort_dir,
    page: params.page.toString(),
    per_page: params.per_page.toString(),
  });

  return useQuery<ZoneListResponse>({
    queryKey: [ZONES_KEY, params],
    queryFn: () => api.get<ZoneListResponse>(`/api/v2/zones?${searchParams}`),
    placeholderData: (prev) => prev,
  });
}

export function useCreateZone() {
  const queryClient = useQueryClient();

  return useMutation<ZoneCreateResponse, Error, ZoneCreateRequest>({
    mutationFn: (data) =>
      api.post<ZoneCreateResponse>("/api/v2/zones", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ZONES_KEY] });
    },
  });
}

export function useDeleteZone() {
  const queryClient = useQueryClient();

  return useMutation<{ status: string; message: string }, Error, string>({
    mutationFn: (zoneName) =>
      api.delete(`/api/v2/zones/${zoneName}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ZONES_KEY] });
    },
  });
}

export function useSyncZones() {
  const queryClient = useQueryClient();

  return useMutation<{ status: string; message: string }, Error>({
    mutationFn: () => api.post("/api/v2/zones/sync"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ZONES_KEY] });
    },
  });
}
