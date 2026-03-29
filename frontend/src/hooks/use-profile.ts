import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Profile {
  id: number;
  username: string;
  firstname: string;
  lastname: string;
  email: string;
  role: string;
  otp_enabled: boolean;
  auth_type: string;
}

export interface ProfileUpdate {
  firstname?: string;
  lastname?: string;
  email?: string;
  password?: string;
}

export function useProfile() {
  return useQuery<Profile>({
    queryKey: ["profile"],
    queryFn: () => api.get<Profile>("/api/v2/auth/profile"),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProfileUpdate) =>
      api.put<{ status: string; message: string }>("/api/v2/auth/profile", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useToggleOtp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enable: boolean) =>
      api.post<{ status: string; otp_enabled: boolean; otp_uri: string | null }>(
        "/api/v2/auth/profile/otp",
        { enable }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}
