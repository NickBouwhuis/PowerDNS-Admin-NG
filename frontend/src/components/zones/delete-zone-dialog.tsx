"use client";

import { useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import type { Zone } from "@/types/zones";
import { useDeleteZone } from "@/hooks/use-zones";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface DeleteZoneDialogProps {
  zone: Zone | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteZoneDialog({
  zone,
  open,
  onOpenChange,
}: DeleteZoneDialogProps) {
  const [confirmName, setConfirmName] = useState("");
  const deleteZone = useDeleteZone();

  const handleDelete = async () => {
    if (!zone || confirmName !== zone.name) return;

    try {
      await deleteZone.mutateAsync(zone.name);
      toast.success(`Zone ${zone.name} deleted`);
      onOpenChange(false);
      setConfirmName("");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail);
      } else {
        toast.error("Failed to delete zone");
      }
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) setConfirmName("");
        onOpenChange(v);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Delete Zone
          </DialogTitle>
          <DialogDescription>
            This action cannot be undone. The zone and all its records will be
            permanently deleted from PowerDNS.
          </DialogDescription>
        </DialogHeader>

        {zone && (
          <div className="space-y-4 py-2">
            <p className="text-sm">
              To confirm, type{" "}
              <span className="font-mono font-semibold">{zone.name}</span>{" "}
              below:
            </p>
            <div className="space-y-2">
              <Label htmlFor="confirm-name" className="sr-only">
                Zone name
              </Label>
              <Input
                id="confirm-name"
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                placeholder={zone.name}
                autoComplete="off"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={
              !zone ||
              confirmName !== zone.name ||
              deleteZone.isPending
            }
          >
            {deleteZone.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Delete Zone"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
