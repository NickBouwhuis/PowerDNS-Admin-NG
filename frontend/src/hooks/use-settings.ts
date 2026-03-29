import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// Basic Settings
// ---------------------------------------------------------------------------

export interface SettingItem {
  key: string;
  value: unknown;
  type: "boolean" | "string" | "integer" | "dict" | "list";
}

export function useBasicSettings() {
  return useQuery<SettingItem[]>({
    queryKey: ["settings", "basic"],
    queryFn: () => api.get<SettingItem[]>("/api/v2/settings/basic"),
  });
}

export function useUpdateBasicSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.put("/api/v2/settings/basic", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["settings", "basic"] }),
  });
}

export function useToggleSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) =>
      api.put<{ key: string; value: boolean }>(
        `/api/v2/settings/basic/${key}/toggle`
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["settings", "basic"] }),
  });
}

// ---------------------------------------------------------------------------
// PDNS Settings
// ---------------------------------------------------------------------------

export function usePdnsSettings() {
  return useQuery<SettingItem[]>({
    queryKey: ["settings", "pdns"],
    queryFn: () => api.get<SettingItem[]>("/api/v2/settings/pdns"),
  });
}

export function useUpdatePdnsSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.put("/api/v2/settings/pdns", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["settings", "pdns"] }),
  });
}

export function useTestPdnsConnection() {
  return useMutation({
    mutationFn: () =>
      api.post<{ status: string; message: string; version?: string }>(
        "/api/v2/settings/pdns/test"
      ),
  });
}

// ---------------------------------------------------------------------------
// Record Type Settings
// ---------------------------------------------------------------------------

export interface RecordTypeSettings {
  forward: Record<string, boolean>;
  reverse: Record<string, boolean>;
}

export function useRecordSettings() {
  return useQuery<RecordTypeSettings>({
    queryKey: ["settings", "records"],
    queryFn: () => api.get<RecordTypeSettings>("/api/v2/settings/records"),
  });
}

export function useUpdateRecordSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      forward?: Record<string, boolean>;
      reverse?: Record<string, boolean>;
    }) => api.put("/api/v2/settings/records", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["settings", "records"] }),
  });
}

// ---------------------------------------------------------------------------
// Authentication Settings
// ---------------------------------------------------------------------------

export type AuthSettingsData = Record<string, Record<string, unknown>>;

export function useAuthSettings() {
  return useQuery<AuthSettingsData>({
    queryKey: ["settings", "authentication"],
    queryFn: () =>
      api.get<AuthSettingsData>("/api/v2/settings/authentication"),
  });
}

export function useUpdateAuthSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.put("/api/v2/settings/authentication", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["settings", "authentication"] }),
  });
}
