import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Zone } from "@/types/zones";

export interface RecordItem {
  name: string;
  type: string;
  ttl: number;
  content: string;
  disabled: boolean;
  comment: string;
  is_allowed_edit: boolean;
}

export interface ZoneDetail {
  zone: Zone;
  records: RecordItem[];
  editable_types: string[];
}

export interface ChangelogEntry {
  id: number;
  msg: string;
  detail: Record<string, unknown> | string | null;
  created_by: string;
  created_on: string | null;
}

export interface ChangelogResponse {
  total: number;
  entries: ChangelogEntry[];
}

export interface DnssecKey {
  id: number;
  keytype: string;
  active: boolean;
  published: boolean;
  dnskey: string;
  ds: string[];
}

export interface DnssecInfo {
  enabled: boolean;
  keys: DnssecKey[];
  message?: string;
}

export interface ZoneSettings {
  zone_type: string;
  masters: string[];
  soa_edit_api: string;
  account_id: number | null;
  account_name: string | null;
  domain_user_ids: number[];
  users: { id: number; username: string }[];
  accounts: { id: number; name: string }[];
}

// Submitted record format (matches backend Record.apply() input)
export interface SubmittedRecord {
  record_name: string;
  record_type: string;
  record_ttl: string;
  record_data: string;
  record_status: string;
  record_comment: string;
}

export function useZoneDetail(zoneName: string) {
  return useQuery<ZoneDetail>({
    queryKey: ["zone-detail", zoneName],
    queryFn: () => api.get<ZoneDetail>(`/api/v2/zones/detail/${zoneName}`),
    enabled: !!zoneName,
  });
}

export function useApplyRecords(zoneName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (records: SubmittedRecord[]) =>
      api.patch(`/api/v2/zones/detail/${zoneName}/records`, { records }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zone-detail", zoneName] });
    },
  });
}

export function useNotifyZone(zoneName: string) {
  return useMutation({
    mutationFn: () => api.post(`/api/v2/zones/detail/${zoneName}/notify`),
  });
}

export function useAxfrZone(zoneName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/api/v2/zones/detail/${zoneName}/axfr`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zone-detail", zoneName] });
    },
  });
}

export function useZoneChangelog(zoneName: string, page: number, perPage = 50) {
  return useQuery<ChangelogResponse>({
    queryKey: ["zone-changelog", zoneName, page],
    queryFn: () =>
      api.get<ChangelogResponse>(
        `/api/v2/zones/detail/${zoneName}/changelog?page=${page}&per_page=${perPage}`
      ),
    enabled: !!zoneName,
  });
}

export function useZoneDnssec(zoneName: string) {
  return useQuery<DnssecInfo>({
    queryKey: ["zone-dnssec", zoneName],
    queryFn: () => api.get<DnssecInfo>(`/api/v2/zones/detail/${zoneName}/dnssec`),
    enabled: !!zoneName,
  });
}

export function useEnableDnssec(zoneName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/api/v2/zones/detail/${zoneName}/dnssec/enable`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zone-dnssec", zoneName] });
      queryClient.invalidateQueries({ queryKey: ["zone-detail", zoneName] });
    },
  });
}

export function useDisableDnssec(zoneName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete(`/api/v2/zones/detail/${zoneName}/dnssec`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zone-dnssec", zoneName] });
      queryClient.invalidateQueries({ queryKey: ["zone-detail", zoneName] });
    },
  });
}

export function useZoneSettings(zoneName: string) {
  return useQuery<ZoneSettings>({
    queryKey: ["zone-settings", zoneName],
    queryFn: () => api.get<ZoneSettings>(`/api/v2/zones/detail/${zoneName}/settings`),
    enabled: !!zoneName,
  });
}

export function useUpdateZoneSettings(zoneName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.put(`/api/v2/zones/detail/${zoneName}/settings`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zone-settings", zoneName] });
      queryClient.invalidateQueries({ queryKey: ["zone-detail", zoneName] });
    },
  });
}
