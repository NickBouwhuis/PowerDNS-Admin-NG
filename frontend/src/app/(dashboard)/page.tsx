"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import type { Zone, ZoneTab } from "@/types/zones";
import { useAuth } from "@/lib/auth";
import { useSyncZones } from "@/hooks/use-zones";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ZoneTable } from "@/components/zones/zone-table";
import { DeleteZoneDialog } from "@/components/zones/delete-zone-dialog";
import { DnssecDialog } from "@/components/zones/dnssec-dialog";

export default function DashboardPage() {
  const { user } = useAuth();
  const syncZones = useSyncZones();
  const [activeTab, setActiveTab] = useState<ZoneTab>("forward");
  const [deleteZone, setDeleteZone] = useState<Zone | null>(null);
  const [dnssecZone, setDnssecZone] = useState<Zone | null>(null);

  const isAdmin = user?.role === "Administrator" || user?.role === "Operator";

  const handleSync = async () => {
    try {
      const result = await syncZones.mutateAsync();
      toast.success(result.message || "Zones synchronized");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail);
      } else {
        toast.error("Zone sync failed");
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Manage your DNS zones and records.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSync}
              disabled={syncZones.isPending}
            >
              {syncZones.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Sync Zones
            </Button>
          )}
          <Button size="sm" asChild>
            <Link href="/zones/add">
              <Plus className="mr-2 h-4 w-4" />
              Add Zone
            </Link>
          </Button>
        </div>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as ZoneTab)}
      >
        <TabsList>
          <TabsTrigger value="forward">Forward Zones</TabsTrigger>
          <TabsTrigger value="reverse_ipv4">Reverse IPv4</TabsTrigger>
          <TabsTrigger value="reverse_ipv6">Reverse IPv6</TabsTrigger>
        </TabsList>

        <TabsContent value="forward">
          <ZoneTable tab="forward" onDelete={setDeleteZone} onDnssec={setDnssecZone} />
        </TabsContent>
        <TabsContent value="reverse_ipv4">
          <ZoneTable tab="reverse_ipv4" onDelete={setDeleteZone} onDnssec={setDnssecZone} />
        </TabsContent>
        <TabsContent value="reverse_ipv6">
          <ZoneTable tab="reverse_ipv6" onDelete={setDeleteZone} onDnssec={setDnssecZone} />
        </TabsContent>
      </Tabs>

      <DeleteZoneDialog
        zone={deleteZone}
        open={!!deleteZone}
        onOpenChange={(open) => {
          if (!open) setDeleteZone(null);
        }}
      />

      {dnssecZone && (
        <DnssecDialog
          zoneName={dnssecZone.name}
          open={!!dnssecZone}
          onOpenChange={(open) => {
            if (!open) setDnssecZone(null);
          }}
        />
      )}
    </div>
  );
}
