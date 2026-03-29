"use client";

import { useState, useEffect } from "react";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
import { toast } from "sonner";

import {
  usePdnsSettings,
  useUpdatePdnsSettings,
  useTestPdnsConnection,
} from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function PdnsSettingsPage() {
  const { data: settings, isLoading } = usePdnsSettings();
  const updateSettings = useUpdatePdnsSettings();
  const testConnection = useTestPdnsConnection();

  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [version, setVersion] = useState("");

  useEffect(() => {
    if (settings) {
      const map = Object.fromEntries(settings.map((s) => [s.key, s.value]));
      setApiUrl(String(map.pdns_api_url ?? ""));
      setApiKey(String(map.pdns_api_key ?? ""));
      setVersion(String(map.pdns_version ?? ""));
    }
  }, [settings]);

  const handleSave = async () => {
    try {
      await updateSettings.mutateAsync({
        pdns_api_url: apiUrl,
        pdns_api_key: apiKey,
        pdns_version: version,
      });
      toast.success("PowerDNS settings saved");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to save settings"
      );
    }
  };

  const handleTest = async () => {
    try {
      const result = await testConnection.mutateAsync();
      if (result.status === "ok") {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Connection test failed"
      );
    }
  };

  if (isLoading) {
    return <Skeleton className="h-64 w-full max-w-2xl" />;
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle className="text-lg">PowerDNS API Connection</CardTitle>
        <CardDescription>
          Configure the connection to your PowerDNS Authoritative Server API.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="pdns-url">API URL</Label>
          <Input
            id="pdns-url"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="http://127.0.0.1:8081"
          />
          <p className="text-xs text-muted-foreground">
            URL of the PowerDNS API (e.g., http://127.0.0.1:8081)
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="pdns-key">API Key</Label>
          <Input
            id="pdns-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Your PowerDNS API key"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="pdns-version">PowerDNS Version</Label>
          <Input
            id="pdns-version"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="4.1.1"
          />
        </div>

        <div className="flex gap-2 pt-2">
          <Button
            onClick={handleSave}
            disabled={updateSettings.isPending}
          >
            {updateSettings.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save
          </Button>
          <Button
            variant="outline"
            onClick={handleTest}
            disabled={testConnection.isPending}
          >
            {testConnection.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : testConnection.isSuccess ? (
              testConnection.data?.status === "ok" ? (
                <CheckCircle className="mr-2 h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="mr-2 h-4 w-4 text-destructive" />
              )
            ) : null}
            Test Connection
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
