"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Bell, Download, Loader2, Shield } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import {
  useZoneDetail,
  useNotifyZone,
  useAxfrZone,
} from "@/hooks/use-zone-detail";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RecordEditor } from "@/components/zones/record-editor";
import { DnssecDialog } from "@/components/zones/dnssec-dialog";

export default function ZoneDetailPage() {
  const params = useParams();
  const zoneName = decodeURIComponent(params.name as string);
  const { user } = useAuth();
  const { data, isLoading, error } = useZoneDetail(zoneName);
  const notifyZone = useNotifyZone(zoneName);
  const axfrZone = useAxfrZone(zoneName);
  const [dnssecOpen, setDnssecOpen] = useState(false);

  const isAdmin =
    user?.role === "Administrator" || user?.role === "Operator";
  const isSlave = data?.zone.type?.toLowerCase() === "slave";

  const handleNotify = async () => {
    try {
      await notifyZone.mutateAsync();
      toast.success("NOTIFY sent to slave servers");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to send NOTIFY"
      );
    }
  };

  const handleAxfr = async () => {
    try {
      await axfrZone.mutateAsync();
      toast.success("AXFR completed");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "AXFR failed"
      );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">
          {error instanceof ApiError
            ? error.detail
            : "Failed to load zone details"}
        </p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* Action buttons */}
      <div className="flex items-center gap-2">
        {!isSlave && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleNotify}
            disabled={notifyZone.isPending}
          >
            {notifyZone.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Bell className="mr-2 h-4 w-4" />
            )}
            Notify
          </Button>
        )}
        {isSlave && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleAxfr}
            disabled={axfrZone.isPending}
          >
            {axfrZone.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            AXFR
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setDnssecOpen(true)}
        >
          <Shield className="mr-2 h-4 w-4" />
          DNSSEC
        </Button>
      </div>

      {/* Record editor */}
      <RecordEditor
        zoneName={zoneName}
        records={data.records}
        editableTypes={data.editable_types}
        readOnly={isSlave}
      />

      {/* DNSSEC dialog */}
      <DnssecDialog
        zoneName={zoneName}
        open={dnssecOpen}
        onOpenChange={setDnssecOpen}
      />
    </div>
  );
}
