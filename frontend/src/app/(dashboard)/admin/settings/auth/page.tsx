"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  useAuthSettings,
  useUpdateAuthSettings,
  type AuthSettingsData,
} from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// Provider configs
const PROVIDERS = [
  { key: "local", label: "Local" },
  { key: "ldap", label: "LDAP" },
  { key: "google", label: "Google" },
  { key: "github", label: "GitHub" },
  { key: "azure", label: "Azure AD" },
  { key: "oidc", label: "OpenID Connect" },
  { key: "saml", label: "SAML" },
] as const;

// Human-readable labels for setting keys
const FIELD_LABELS: Record<string, string> = {
  // Local
  local_db_enabled: "Enable Local Authentication",
  signup_enabled: "Allow Registration",
  pwd_enforce_characters: "Enforce Password Characters",
  pwd_min_len: "Minimum Password Length",
  pwd_min_lowercase: "Min Lowercase Characters",
  pwd_min_uppercase: "Min Uppercase Characters",
  pwd_min_digits: "Min Digits",
  pwd_min_special: "Min Special Characters",
  pwd_enforce_complexity: "Enforce Password Complexity",
  pwd_min_complexity: "Min Complexity Score",
  // LDAP
  ldap_enabled: "Enable LDAP",
  ldap_type: "LDAP Type",
  ldap_uri: "LDAP URI",
  ldap_base_dn: "Base DN",
  ldap_admin_username: "Admin Username",
  ldap_admin_password: "Admin Password",
  ldap_domain: "Domain",
  ldap_filter_basic: "Basic Filter",
  ldap_filter_username: "Username Filter",
  ldap_filter_group: "Group Filter",
  ldap_filter_groupname: "Group Name Filter",
  ldap_sg_enabled: "Security Group Mapping",
  ldap_admin_group: "Admin Group",
  ldap_operator_group: "Operator Group",
  ldap_user_group: "User Group",
  ldap_tls_verify: "Verify TLS",
  autoprovisioning: "Auto Provisioning",
  autoprovisioning_attribute: "Auto Provisioning Attribute",
  urn_value: "URN Value",
  purge: "Purge Old Users",
  // Google
  google_oauth_enabled: "Enable Google OAuth",
  google_oauth_client_id: "Client ID",
  google_oauth_client_secret: "Client Secret",
  google_oauth_scope: "Scope",
  google_base_url: "Base URL",
  google_oauth_auto_configure: "Auto Configure",
  google_oauth_metadata_url: "Metadata URL",
  google_token_url: "Token URL",
  google_authorize_url: "Authorize URL",
  // GitHub
  github_oauth_enabled: "Enable GitHub OAuth",
  github_oauth_key: "Client ID",
  github_oauth_secret: "Client Secret",
  github_oauth_scope: "Scope",
  github_oauth_api_url: "API URL",
  github_oauth_auto_configure: "Auto Configure",
  github_oauth_metadata_url: "Metadata URL",
  github_oauth_token_url: "Token URL",
  github_oauth_authorize_url: "Authorize URL",
  // Azure
  azure_oauth_enabled: "Enable Azure OAuth",
  azure_oauth_key: "Client ID",
  azure_oauth_secret: "Client Secret",
  azure_oauth_scope: "Scope",
  azure_oauth_api_url: "API URL",
  azure_oauth_auto_configure: "Auto Configure",
  azure_oauth_metadata_url: "Metadata URL",
  azure_oauth_token_url: "Token URL",
  azure_oauth_authorize_url: "Authorize URL",
  azure_sg_enabled: "Security Group Mapping",
  azure_admin_group: "Admin Group",
  azure_operator_group: "Operator Group",
  azure_user_group: "User Group",
  azure_group_accounts_enabled: "Group-based Accounts",
  azure_group_accounts_name: "Account Name Property",
  azure_group_accounts_name_re: "Account Name Regex",
  azure_group_accounts_description: "Account Description Property",
  azure_group_accounts_description_re: "Account Description Regex",
  // OIDC
  oidc_oauth_enabled: "Enable OIDC",
  oidc_oauth_key: "Client ID",
  oidc_oauth_secret: "Client Secret",
  oidc_oauth_scope: "Scope",
  oidc_oauth_api_url: "API URL",
  oidc_oauth_auto_configure: "Auto Configure",
  oidc_oauth_metadata_url: "Metadata URL",
  oidc_oauth_token_url: "Token URL",
  oidc_oauth_authorize_url: "Authorize URL",
  oidc_oauth_logout_url: "Logout URL",
  oidc_oauth_username: "Username Attribute",
  oidc_oauth_email: "Email Attribute",
  oidc_oauth_firstname: "First Name Attribute",
  oidc_oauth_last_name: "Last Name Attribute",
  oidc_oauth_account_name_property: "Account Name Property",
  oidc_oauth_account_description_property: "Account Description Property",
  // SAML
  saml_enabled: "Enable SAML",
  saml_debug: "Debug Mode",
  saml_metadata_url: "Metadata URL",
  saml_metadata_cache_lifetime: "Metadata Cache Lifetime (days)",
  saml_idp_sso_binding: "IDP SSO Binding",
  saml_idp_entity_id: "IDP Entity ID",
  saml_nameid_format: "NameID Format",
  saml_attribute_account: "Account Attribute",
  saml_attribute_email: "Email Attribute",
  saml_attribute_givenname: "Given Name Attribute",
  saml_attribute_surname: "Surname Attribute",
  saml_attribute_name: "Name Attribute",
  saml_attribute_username: "Username Attribute",
  saml_attribute_admin: "Admin Attribute",
  saml_attribute_group: "Group Attribute",
  saml_group_admin_name: "Admin Group Name",
  saml_group_operator_name: "Operator Group Name",
  saml_group_to_account_mapping: "Group to Account Mapping",
  saml_sp_entity_id: "SP Entity ID",
  saml_sp_contact_name: "SP Contact Name",
  saml_sp_contact_mail: "SP Contact Email",
  saml_sign_request: "Sign Requests",
  saml_want_message_signed: "Require Signed Messages",
  saml_logout: "Enable Logout",
  saml_logout_url: "Logout URL",
  saml_assertion_encrypted: "Encrypted Assertions",
  saml_cert: "Certificate",
  saml_key: "Private Key",
};

// Keys that are boolean toggles
const BOOLEAN_KEYS = new Set([
  "local_db_enabled", "signup_enabled", "pwd_enforce_characters",
  "pwd_enforce_complexity",
  "ldap_enabled", "ldap_sg_enabled", "ldap_tls_verify",
  "autoprovisioning", "purge",
  "google_oauth_enabled", "google_oauth_auto_configure",
  "github_oauth_enabled", "github_oauth_auto_configure",
  "azure_oauth_enabled", "azure_oauth_auto_configure",
  "azure_sg_enabled", "azure_group_accounts_enabled",
  "oidc_oauth_enabled", "oidc_oauth_auto_configure",
  "saml_enabled", "saml_debug", "saml_sign_request",
  "saml_want_message_signed", "saml_logout", "saml_assertion_encrypted",
]);

// Keys that are integer fields
const INTEGER_KEYS = new Set([
  "pwd_min_len", "pwd_min_lowercase", "pwd_min_uppercase",
  "pwd_min_digits", "pwd_min_special", "pwd_min_complexity",
  "saml_metadata_cache_lifetime",
]);

// Keys that should use password inputs
const SECRET_KEYS = new Set([
  "google_oauth_client_secret", "github_oauth_secret",
  "azure_oauth_secret", "oidc_oauth_secret",
  "ldap_admin_password", "saml_key",
]);

export default function AuthSettingsPage() {
  const { data, isLoading } = useAuthSettings();
  const updateAuth = useUpdateAuthSettings();
  const [activeTab, setActiveTab] = useState("local");
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});

  // Initialize form when data loads
  useEffect(() => {
    if (data) {
      const flat: Record<string, unknown> = {};
      for (const [, settings] of Object.entries(data)) {
        for (const [key, value] of Object.entries(settings)) {
          flat[key] = value;
        }
      }
      setFormValues(flat);
    }
  }, [data]);

  const setValue = useCallback((key: string, value: unknown) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = async (providerKey: string) => {
    // Find all keys for this provider
    const provider = PROVIDERS.find((p) => p.key === providerKey);
    if (!provider || !data) return;

    const providerSettings = data[providerKey] || {};
    const keysToSave: Record<string, unknown> = {};

    for (const key of Object.keys(providerSettings)) {
      if (key in formValues) {
        keysToSave[key] = formValues[key];
      }
    }

    try {
      await updateAuth.mutateAsync(keysToSave);
      toast.success(`${provider.label} settings saved`);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to save settings"
      );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full max-w-xl" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!data) return null;

  const renderField = (key: string) => {
    const label = FIELD_LABELS[key] || key;
    const value = formValues[key];

    if (BOOLEAN_KEYS.has(key)) {
      return (
        <div key={key} className="flex items-center justify-between py-2">
          <Label className="cursor-pointer" htmlFor={key}>
            {label}
          </Label>
          <button
            id={key}
            type="button"
            role="switch"
            aria-checked={!!value}
            onClick={() => setValue(key, !value)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
              value ? "bg-primary" : "bg-input"
            }`}
          >
            <span
              className={`pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                value ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      );
    }

    return (
      <div key={key} className="space-y-1.5 py-2">
        <Label htmlFor={key}>{label}</Label>
        <Input
          id={key}
          value={String(value ?? "")}
          onChange={(e) => {
            const v = INTEGER_KEYS.has(key)
              ? parseInt(e.target.value, 10) || 0
              : e.target.value;
            setValue(key, v);
          }}
          type={
            INTEGER_KEYS.has(key)
              ? "number"
              : SECRET_KEYS.has(key)
                ? "password"
                : "text"
          }
          className="max-w-lg"
        />
      </div>
    );
  };

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <TabsList className="flex-wrap h-auto gap-1">
        {PROVIDERS.map((p) => (
          <TabsTrigger key={p.key} value={p.key}>
            {p.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {PROVIDERS.map((provider) => {
        const providerData = data[provider.key] || {};
        const keys = Object.keys(providerData);

        return (
          <TabsContent key={provider.key} value={provider.key}>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  {provider.label} Authentication
                </CardTitle>
                <CardDescription>
                  Configure {provider.label} authentication settings.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 divide-y">
                {keys.map((key) => renderField(key))}

                <div className="pt-4">
                  <Button
                    onClick={() => handleSave(provider.key)}
                    disabled={updateAuth.isPending}
                  >
                    {updateAuth.isPending && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Save {provider.label} Settings
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
