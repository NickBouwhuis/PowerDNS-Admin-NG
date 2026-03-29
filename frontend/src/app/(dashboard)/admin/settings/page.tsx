"use client";

import { useState } from "react";
import { Loader2, Search, X } from "lucide-react";
import { toast } from "sonner";

import {
  useBasicSettings,
  useToggleSetting,
  useUpdateBasicSettings,
  type SettingItem,
} from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// Human-readable labels and grouping
const SETTING_LABELS: Record<string, string> = {
  site_name: "Site Name",
  maintenance: "Maintenance Mode",
  fullscreen_layout: "Fullscreen Layout",
  session_timeout: "Session Timeout (minutes)",
  warn_session_timeout: "Warn Before Session Timeout",
  default_domain_table_size: "Default Domain Table Size",
  default_record_table_size: "Default Record Table Size",
  custom_css: "Custom CSS",
  custom_history_header: "Custom History Header",
  gravatar_enabled: "Gravatar Enabled",
  otp_field_enabled: "Show OTP Field on Login",
  otp_force: "Force OTP for All Users",
  login_ldap_first: "LDAP Login First",
  auto_ptr: "Automatic PTR Records",
  record_helper: "Record Helper",
  record_quick_edit: "Quick Record Edit",
  pretty_ipv6_ptr: "Pretty IPv6 PTR",
  ttl_options: "TTL Options",
  pdns_api_timeout: "PDNS API Timeout (seconds)",
  max_history_records: "Max History Records",
  enforce_api_ttl: "Enforce API TTL",
  enable_api_rr_history: "Enable API RR History",
  preserve_history: "Preserve History",
  deny_domain_override: "Deny Domain Override",
  allow_user_create_domain: "Allow Users to Create Domains",
  allow_user_remove_domain: "Allow Users to Remove Domains",
  allow_user_view_history: "Allow Users to View History",
  delete_sso_accounts: "Delete SSO Accounts on Remove",
  bg_domain_updates: "Background Domain Updates",
  dnssec_admins_only: "DNSSEC Admins Only",
  account_name_extra_chars: "Allow Extra Chars in Account Names",
  verify_ssl_connections: "Verify SSL Connections",
  verify_user_email: "Verify User Email",
};

const SETTING_GROUPS: Record<string, string[]> = {
  General: [
    "site_name", "maintenance", "fullscreen_layout",
    "session_timeout", "warn_session_timeout", "custom_css",
    "custom_history_header", "gravatar_enabled",
  ],
  Authentication: [
    "otp_field_enabled", "otp_force", "login_ldap_first",
    "verify_user_email", "delete_sso_accounts",
  ],
  "DNS Records": [
    "auto_ptr", "record_helper", "record_quick_edit",
    "pretty_ipv6_ptr", "ttl_options", "enforce_api_ttl",
    "dnssec_admins_only",
  ],
  "Tables & Display": [
    "default_domain_table_size", "default_record_table_size",
  ],
  Permissions: [
    "allow_user_create_domain", "allow_user_remove_domain",
    "allow_user_view_history", "deny_domain_override",
    "account_name_extra_chars",
  ],
  Advanced: [
    "pdns_api_timeout", "max_history_records", "enable_api_rr_history",
    "preserve_history", "bg_domain_updates", "verify_ssl_connections",
  ],
};

export default function BasicSettingsPage() {
  const { data: settings, isLoading } = useBasicSettings();
  const toggleSetting = useToggleSetting();
  const updateSettings = useUpdateBasicSettings();
  const [search, setSearch] = useState("");
  const [editValues, setEditValues] = useState<Record<string, string>>({});

  const handleToggle = async (key: string) => {
    try {
      const result = await toggleSetting.mutateAsync(key);
      toast.success(
        `${SETTING_LABELS[key] || key}: ${result.value ? "enabled" : "disabled"}`
      );
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to toggle setting"
      );
    }
  };

  const handleSave = async (key: string, value: string) => {
    try {
      const setting = settings?.find((s) => s.key === key);
      let parsedValue: unknown = value;
      if (setting?.type === "integer") {
        parsedValue = parseInt(value, 10);
        if (isNaN(parsedValue as number)) {
          toast.error("Invalid number");
          return;
        }
      }
      await updateSettings.mutateAsync({ [key]: parsedValue });
      toast.success(`${SETTING_LABELS[key] || key} updated`);
      setEditValues((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update setting"
      );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
      </div>
    );
  }

  if (!settings) return null;

  const settingsMap = Object.fromEntries(
    settings.map((s) => [s.key, s])
  );

  const matchesSearch = (key: string) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const label = (SETTING_LABELS[key] || key).toLowerCase();
    return label.includes(q) || key.includes(q);
  };

  const renderSetting = (item: SettingItem) => {
    const label = SETTING_LABELS[item.key] || item.key;

    if (item.type === "boolean") {
      return (
        <div
          key={item.key}
          className="flex items-center justify-between py-2"
        >
          <Label className="cursor-pointer" htmlFor={item.key}>
            {label}
          </Label>
          <button
            id={item.key}
            type="button"
            role="switch"
            aria-checked={!!item.value}
            onClick={() => handleToggle(item.key)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
              item.value
                ? "bg-primary"
                : "bg-input"
            }`}
          >
            <span
              className={`pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                item.value ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      );
    }

    // String / integer
    const currentEdit =
      item.key in editValues
        ? editValues[item.key]
        : String(item.value ?? "");
    const isEditing = item.key in editValues;

    return (
      <div key={item.key} className="space-y-1.5 py-2">
        <Label htmlFor={item.key}>{label}</Label>
        <div className="flex gap-2">
          <Input
            id={item.key}
            value={currentEdit}
            onChange={(e) =>
              setEditValues((prev) => ({
                ...prev,
                [item.key]: e.target.value,
              }))
            }
            onFocus={() => {
              if (!(item.key in editValues)) {
                setEditValues((prev) => ({
                  ...prev,
                  [item.key]: String(item.value ?? ""),
                }));
              }
            }}
            type={item.type === "integer" ? "number" : "text"}
            className="max-w-md"
          />
          {isEditing && (
            <Button
              size="sm"
              onClick={() => handleSave(item.key, currentEdit)}
              disabled={updateSettings.isPending}
            >
              {updateSettings.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save"
              )}
            </Button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search settings..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8 pr-8"
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Settings groups */}
      {Object.entries(SETTING_GROUPS).map(([group, keys]) => {
        const visibleKeys = keys.filter(
          (k) => settingsMap[k] && matchesSearch(k)
        );
        if (visibleKeys.length === 0) return null;

        return (
          <Card key={group}>
            <CardHeader>
              <CardTitle className="text-lg">{group}</CardTitle>
            </CardHeader>
            <CardContent className="divide-y">
              {visibleKeys.map((key) => renderSetting(settingsMap[key]))}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
