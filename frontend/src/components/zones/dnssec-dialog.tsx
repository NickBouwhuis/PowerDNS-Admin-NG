"use client";

import { Check, Copy, Loader2, ShieldCheck, ShieldOff } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  useZoneDnssec,
  useEnableDnssec,
  useDisableDnssec,
} from "@/hooks/use-zone-detail";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function CopyableRecord({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      toast.success(`${label} copied to clipboard`);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [value, label]);

  return (
    <div className="group relative">
      <pre className="rounded-md bg-muted p-3 pr-12 text-xs font-mono whitespace-pre-wrap break-all max-w-full">
        {value}
      </pre>
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-2 right-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={handleCopy}
        title={`Copy ${label}`}
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-green-600" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
    </div>
  );
}

interface DnssecDialogProps {
  zoneName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DnssecDialog({
  zoneName,
  open,
  onOpenChange,
}: DnssecDialogProps) {
  const { data, isLoading } = useZoneDnssec(zoneName);
  const enableDnssec = useEnableDnssec(zoneName);
  const disableDnssec = useDisableDnssec(zoneName);

  const handleEnable = async () => {
    try {
      await enableDnssec.mutateAsync();
      toast.success("DNSSEC enabled");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to enable DNSSEC"
      );
    }
  };

  const handleDisable = async () => {
    try {
      await disableDnssec.mutateAsync();
      toast.success("DNSSEC disabled");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to disable DNSSEC"
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            DNSSEC Configuration
            {data?.enabled && (
              <Badge
                variant="outline"
                className="text-green-600 border-green-400"
              >
                Enabled
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Manage DNSSEC for {zoneName}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : !data?.enabled ? (
          <div className="text-center py-8 space-y-4">
            <ShieldOff className="h-12 w-12 mx-auto text-muted-foreground" />
            <div>
              <p className="font-medium">DNSSEC is not enabled</p>
              <p className="text-sm text-muted-foreground mt-1">
                Enable DNSSEC to sign this zone with cryptographic keys.
              </p>
              {data?.message && (
                <p className="text-sm text-muted-foreground mt-1">
                  {data.message}
                </p>
              )}
            </div>
            <Button
              onClick={handleEnable}
              disabled={enableDnssec.isPending}
            >
              {enableDnssec.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              <ShieldCheck className="mr-2 h-4 w-4" />
              Enable DNSSEC
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Key list */}
            {data.keys.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead>Published</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.keys.map((key) => (
                    <TableRow key={key.id}>
                      <TableCell className="font-mono">{key.id}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{key.keytype}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={key.active ? "default" : "secondary"}
                        >
                          {key.active ? "Yes" : "No"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={key.published ? "default" : "secondary"}
                        >
                          {key.published ? "Yes" : "No"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {/* DNSKEY records */}
            {data.keys.some((k) => k.dnskey) && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">DNSKEY Records</h4>
                <p className="text-xs text-muted-foreground">
                  Hover over a record to copy it.
                </p>
                {data.keys
                  .filter((k) => k.dnskey)
                  .map((key) => (
                    <CopyableRecord
                      key={`dnskey-${key.id}`}
                      value={key.dnskey}
                      label="DNSKEY record"
                    />
                  ))}
              </div>
            )}

            {/* DS records */}
            {data.keys.some((k) => k.ds?.length > 0) && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">DS Records</h4>
                <p className="text-xs text-muted-foreground">
                  Copy the DS record to your domain registrar.
                </p>
                {data.keys
                  .filter((k) => k.ds?.length > 0)
                  .map((key) =>
                    key.ds.map((ds: string, idx: number) => (
                      <CopyableRecord
                        key={`ds-${key.id}-${idx}`}
                        value={ds}
                        label="DS record"
                      />
                    ))
                  )}
              </div>
            )}

            {/* Disable button */}
            <div className="flex justify-end pt-4 border-t">
              <Button
                variant="destructive"
                onClick={handleDisable}
                disabled={disableDnssec.isPending}
              >
                {disableDnssec.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                <ShieldOff className="mr-2 h-4 w-4" />
                Disable DNSSEC
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
