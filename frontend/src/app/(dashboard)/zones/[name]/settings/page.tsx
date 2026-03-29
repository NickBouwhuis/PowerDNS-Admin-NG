"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import {
  useZoneSettings,
  useUpdateZoneSettings,
} from "@/hooks/use-zone-detail";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function ZoneSettingsPage() {
  const params = useParams();
  const zoneName = decodeURIComponent(params.name as string);
  const { user } = useAuth();
  const { data, isLoading, error } = useZoneSettings(zoneName);
  const updateSettings = useUpdateZoneSettings(zoneName);

  const isAdmin =
    user?.role === "Administrator" || user?.role === "Operator";

  const [zoneType, setZoneType] = useState("");
  const [masters, setMasters] = useState("");
  const [soaEditApi, setSoaEditApi] = useState("DEFAULT");
  const [accountId, setAccountId] = useState<string>("");
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([]);
  const [userSearch, setUserSearch] = useState("");

  // Initialize form when data loads
  useEffect(() => {
    if (data) {
      setZoneType(data.zone_type);
      setMasters(data.masters.join(", "));
      setSoaEditApi(data.soa_edit_api);
      setAccountId(data.account_id ? String(data.account_id) : "");
      setSelectedUserIds(data.domain_user_ids);
    }
  }, [data]);

  if (!isAdmin) {
    return (
      <div className="rounded-lg border p-6 text-center text-muted-foreground">
        Only administrators and operators can manage zone settings.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">
          {error instanceof ApiError
            ? error.detail
            : "Failed to load zone settings"}
        </p>
      </div>
    );
  }

  const handleSaveType = async () => {
    try {
      await updateSettings.mutateAsync({
        zone_type: zoneType,
        masters: masters
          .split(",")
          .map((m) => m.trim())
          .filter(Boolean),
      });
      toast.success("Zone type updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update zone type"
      );
    }
  };

  const handleSaveSoa = async () => {
    try {
      await updateSettings.mutateAsync({ soa_edit_api: soaEditApi });
      toast.success("SOA-EDIT-API updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update SOA setting"
      );
    }
  };

  const handleSaveAccount = async () => {
    try {
      await updateSettings.mutateAsync({
        account_id: accountId ? parseInt(accountId) : null,
      });
      toast.success("Account updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update account"
      );
    }
  };

  const handleSaveUsers = async () => {
    try {
      await updateSettings.mutateAsync({ user_ids: selectedUserIds });
      toast.success("User access updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update user access"
      );
    }
  };

  const toggleUser = (userId: number) => {
    setSelectedUserIds((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId]
    );
  };

  const filteredUsers = data.users.filter((u) =>
    u.username.toLowerCase().includes(userSearch.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Zone Type */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Zone Type</CardTitle>
          <CardDescription>
            Change the zone type and configure master servers for slave zones.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Type</Label>
              <Select value={zoneType} onValueChange={setZoneType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="native">Native</SelectItem>
                  <SelectItem value="master">Master</SelectItem>
                  <SelectItem value="slave">Slave</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>SOA-EDIT-API</Label>
              <Select value={soaEditApi} onValueChange={setSoaEditApi}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DEFAULT">DEFAULT</SelectItem>
                  <SelectItem value="INCREASE">INCREASE</SelectItem>
                  <SelectItem value="EPOCH">EPOCH</SelectItem>
                  <SelectItem value="OFF">OFF</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {zoneType === "slave" && (
            <div className="space-y-2">
              <Label>Master IPs</Label>
              <Input
                value={masters}
                onChange={(e) => setMasters(e.target.value)}
                placeholder="192.168.1.1, 10.0.0.1"
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated list of master server IP addresses.
              </p>
            </div>
          )}
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleSaveType}
              disabled={updateSettings.isPending}
            >
              {updateSettings.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save Type
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleSaveSoa}
              disabled={updateSettings.isPending}
            >
              Save SOA
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Account */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Account</CardTitle>
          <CardDescription>
            Assign this zone to an account for group-based access control.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select value={accountId} onValueChange={setAccountId}>
            <SelectTrigger>
              <SelectValue placeholder="No account" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">None</SelectItem>
              {data.accounts.map((acc) => (
                <SelectItem key={acc.id} value={String(acc.id)}>
                  {acc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            onClick={handleSaveAccount}
            disabled={updateSettings.isPending}
          >
            {updateSettings.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save Account
          </Button>
        </CardContent>
      </Card>

      {/* User Access */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">User Access</CardTitle>
          <CardDescription>
            Grant individual users access to this zone.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            placeholder="Search users..."
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
          />
          <div className="max-h-[300px] overflow-y-auto border rounded-md">
            {filteredUsers.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground text-center">
                No users found
              </p>
            ) : (
              <div className="divide-y">
                {filteredUsers.map((u) => (
                  <label
                    key={u.id}
                    className="flex items-center gap-3 px-4 py-2 hover:bg-muted/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedUserIds.includes(u.id)}
                      onChange={() => toggleUser(u.id)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">{u.username}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {selectedUserIds.length} user
            {selectedUserIds.length !== 1 ? "s" : ""} selected
          </p>
          <Button
            size="sm"
            onClick={handleSaveUsers}
            disabled={updateSettings.isPending}
          >
            {updateSettings.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save User Access
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
