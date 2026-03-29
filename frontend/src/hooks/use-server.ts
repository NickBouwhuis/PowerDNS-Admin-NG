import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface PdnsStat {
  name: string;
  type: string;
  value: string;
}

export interface ServerStatistics {
  pdns_stats: PdnsStat[];
  uptime: number | null;
  zone_count: number;
  user_count: number;
  history_count: number;
}

export interface ServerConfig {
  name: string;
  type: string;
  value: string;
}

export interface ServerConfigResponse {
  config: ServerConfig[];
}

export function useServerStatistics() {
  return useQuery<ServerStatistics>({
    queryKey: ["server", "statistics"],
    queryFn: () => api.get<ServerStatistics>("/api/v2/server/statistics"),
  });
}

export function useServerConfiguration() {
  return useQuery<ServerConfigResponse>({
    queryKey: ["server", "configuration"],
    queryFn: () =>
      api.get<ServerConfigResponse>("/api/v2/server/configuration"),
  });
}
