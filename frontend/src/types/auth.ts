export interface User {
  id: number;
  username: string;
  firstname: string | null;
  lastname: string | null;
  email: string | null;
  role: "Administrator" | "Operator" | "User";
  otp_enabled: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
  otp_token?: string;
  auth_method?: "LOCAL" | "LDAP";
}

export interface LoginResponse {
  status: "ok" | "otp_required" | "otp_setup_required" | "error";
  message?: string;
  user?: User;
}

export interface AuthSettings {
  local_db_enabled: boolean;
  ldap_enabled: boolean;
  signup_enabled: boolean;
  google_oauth_enabled: boolean;
  github_oauth_enabled: boolean;
  azure_oauth_enabled: boolean;
  oidc_oauth_enabled: boolean;
  saml_enabled: boolean;
  otp_field_enabled: boolean;
  verify_user_email: boolean;
}
