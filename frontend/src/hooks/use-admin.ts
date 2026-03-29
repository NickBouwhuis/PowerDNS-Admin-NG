import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export interface AdminUser {
  id: number;
  username: string;
  firstname: string;
  lastname: string;
  email: string;
  role: string | null;
  otp_enabled: boolean;
}

export interface AdminUserDetail extends AdminUser {
  accounts: { id: number; name: string }[];
}

export interface UserCreateData {
  username: string;
  password?: string;
  firstname?: string;
  lastname?: string;
  email?: string;
  role_name?: string;
}

export interface UserUpdateData {
  firstname?: string;
  lastname?: string;
  email?: string;
  password?: string;
  role_name?: string;
  otp_secret?: string;
}

export function useAdminUsers() {
  return useQuery<AdminUser[]>({
    queryKey: ["admin", "users"],
    queryFn: () => api.get<AdminUser[]>("/api/v2/admin/users"),
  });
}

export function useAdminUser(username: string) {
  return useQuery<AdminUserDetail>({
    queryKey: ["admin", "users", username],
    queryFn: () =>
      api.get<AdminUserDetail>(`/api/v2/admin/users/${username}`),
    enabled: !!username,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UserCreateData) =>
      api.post("/api/v2/admin/users", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useUpdateUser(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UserUpdateData) =>
      api.put(`/api/v2/admin/users/${userId}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) =>
      api.delete(`/api/v2/admin/users/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

export interface AdminAccount {
  id: number;
  name: string;
  description: string;
  contact: string;
  mail: string;
  domain_count: number;
  user_count: number;
}

export interface AdminAccountDetail {
  id: number;
  name: string;
  description: string;
  contact: string;
  mail: string;
  members: { id: number; username: string }[];
  domains: { id: number; name: string }[];
}

export interface AccountCreateData {
  name: string;
  description?: string;
  contact?: string;
  mail?: string;
}

export interface AccountUpdateData {
  description?: string;
  contact?: string;
  mail?: string;
}

export function useAdminAccounts() {
  return useQuery<AdminAccount[]>({
    queryKey: ["admin", "accounts"],
    queryFn: () => api.get<AdminAccount[]>("/api/v2/admin/accounts"),
  });
}

export function useAdminAccount(accountId: number) {
  return useQuery<AdminAccountDetail>({
    queryKey: ["admin", "accounts", accountId],
    queryFn: () =>
      api.get<AdminAccountDetail>(`/api/v2/admin/accounts/${accountId}`),
    enabled: !!accountId,
  });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AccountCreateData) =>
      api.post("/api/v2/admin/accounts", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "accounts"] }),
  });
}

export function useUpdateAccount(accountId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AccountUpdateData) =>
      api.put(`/api/v2/admin/accounts/${accountId}`, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "accounts"] }),
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId: number) =>
      api.delete(`/api/v2/admin/accounts/${accountId}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "accounts"] }),
  });
}

export function useUpdateAccountMembers(accountId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userIds: number[]) =>
      api.put(`/api/v2/admin/accounts/${accountId}/members`, {
        user_ids: userIds,
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "accounts", accountId] }),
  });
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export interface AdminApiKey {
  id: number;
  description: string;
  role: string | null;
  domains: { id: number; name: string }[];
  accounts: { id: number; name: string }[];
}

export interface AdminApiKeyCreated extends AdminApiKey {
  plain_key: string | null;
}

export interface ApiKeyCreateData {
  description?: string;
  role_name?: string;
  domain_names?: string[];
  account_names?: string[];
}

export interface ApiKeyUpdateData {
  description?: string;
  role_name?: string;
  domain_names?: string[];
  account_names?: string[];
}

export function useAdminApiKeys() {
  return useQuery<AdminApiKey[]>({
    queryKey: ["admin", "apikeys"],
    queryFn: () => api.get<AdminApiKey[]>("/api/v2/admin/apikeys"),
  });
}

export function useAdminApiKey(keyId: number) {
  return useQuery<AdminApiKey>({
    queryKey: ["admin", "apikeys", keyId],
    queryFn: () => api.get<AdminApiKey>(`/api/v2/admin/apikeys/${keyId}`),
    enabled: !!keyId,
  });
}

export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ApiKeyCreateData) =>
      api.post<AdminApiKeyCreated>("/api/v2/admin/apikeys", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "apikeys"] }),
  });
}

export function useUpdateApiKey(keyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ApiKeyUpdateData) =>
      api.put(`/api/v2/admin/apikeys/${keyId}`, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "apikeys"] }),
  });
}

export function useDeleteApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyId: number) =>
      api.delete(`/api/v2/admin/apikeys/${keyId}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "apikeys"] }),
  });
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

export interface AdminTemplate {
  id: number;
  name: string;
  description: string;
  record_count: number;
}

export interface TemplateRecord {
  id?: number;
  name: string;
  type: string;
  ttl: number;
  data: string;
  comment: string;
  status: boolean;
}

export interface AdminTemplateDetail {
  id: number;
  name: string;
  description: string;
  records: TemplateRecord[];
}

export interface TemplateCreateData {
  name: string;
  description?: string;
}

export interface TemplateFromZoneData {
  name: string;
  description?: string;
  zone_name: string;
}

export function useAdminTemplates() {
  return useQuery<AdminTemplate[]>({
    queryKey: ["admin", "templates"],
    queryFn: () => api.get<AdminTemplate[]>("/api/v2/admin/templates"),
  });
}

export function useAdminTemplate(templateId: number) {
  return useQuery<AdminTemplateDetail>({
    queryKey: ["admin", "templates", templateId],
    queryFn: () =>
      api.get<AdminTemplateDetail>(
        `/api/v2/admin/templates/${templateId}`
      ),
    enabled: !!templateId,
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TemplateCreateData) =>
      api.post("/api/v2/admin/templates", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "templates"] }),
  });
}

export function useUpdateTemplate(templateId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { description?: string; records?: TemplateRecord[] }) =>
      api.put(`/api/v2/admin/templates/${templateId}`, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "templates"] }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (templateId: number) =>
      api.delete(`/api/v2/admin/templates/${templateId}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "templates"] }),
  });
}

export function useCreateTemplateFromZone() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TemplateFromZoneData) =>
      api.post("/api/v2/admin/templates/from-zone", data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin", "templates"] }),
  });
}
