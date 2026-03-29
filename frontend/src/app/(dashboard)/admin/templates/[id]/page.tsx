"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus, Trash2, Loader2, Undo2 } from "lucide-react";
import { toast } from "sonner";

import {
  useAdminTemplate,
  useUpdateTemplate,
  type TemplateRecord,
} from "@/hooks/use-admin";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const RECORD_TYPES = [
  "A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV", "SOA", "PTR",
  "CAA", "NAPTR", "SPF", "SSHFP", "TLSA",
];

interface EditableTemplateRecord extends TemplateRecord {
  _key: string;
  _deleted: boolean;
}

let nextKey = 0;
function genKey() {
  return `tr-${++nextKey}`;
}

export default function EditTemplatePage() {
  const params = useParams();
  const templateId = parseInt(params.id as string);
  const { data: template, isLoading, error } = useAdminTemplate(templateId);
  const updateTemplate = useUpdateTemplate(templateId);

  const [description, setDescription] = useState("");
  const [records, setRecords] = useState<EditableTemplateRecord[]>([]);

  useEffect(() => {
    if (template) {
      setDescription(template.description);
      setRecords(
        template.records.map((r) => ({
          ...r,
          _key: genKey(),
          _deleted: false,
        }))
      );
    }
  }, [template]);

  const addRecord = useCallback(() => {
    setRecords((prev) => [
      ...prev,
      {
        name: "",
        type: "A",
        ttl: 3600,
        data: "",
        comment: "",
        status: true,
        _key: genKey(),
        _deleted: false,
      },
    ]);
  }, []);

  const updateRecord = useCallback(
    (key: string, field: keyof TemplateRecord, value: string | number | boolean) => {
      setRecords((prev) =>
        prev.map((r) => (r._key === key ? { ...r, [field]: value } : r))
      );
    },
    []
  );

  const deleteRecord = useCallback((key: string) => {
    setRecords((prev) =>
      prev.map((r) => (r._key === key ? { ...r, _deleted: true } : r))
    );
  }, []);

  const restoreRecord = useCallback((key: string) => {
    setRecords((prev) =>
      prev.map((r) => (r._key === key ? { ...r, _deleted: false } : r))
    );
  }, []);

  const handleSave = async () => {
    const activeRecords = records
      .filter((r) => !r._deleted)
      .map((r) => ({
        name: r.name,
        type: r.type,
        ttl: r.ttl,
        data: r.data,
        comment: r.comment,
        status: r.status,
      }));

    try {
      await updateTemplate.mutateAsync({
        description,
        records: activeRecords,
      });
      toast.success("Template saved");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to save template"
      );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !template) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">
          {error instanceof ApiError ? error.detail : "Template not found"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/admin/templates">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {template.name}
          </h1>
          <p className="text-muted-foreground">Edit template records.</p>
        </div>
      </div>

      {/* Description */}
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle className="text-lg">Template Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Description</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Records */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Records</h2>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={addRecord}>
              <Plus className="mr-2 h-4 w-4" />
              Add Record
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={updateTemplate.isPending}
            >
              {updateTemplate.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save Template
            </Button>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">Name</TableHead>
                <TableHead className="w-[100px]">Type</TableHead>
                <TableHead className="w-[80px]">TTL</TableHead>
                <TableHead>Data</TableHead>
                <TableHead className="w-[140px]">Comment</TableHead>
                <TableHead className="w-[60px]">Active</TableHead>
                <TableHead className="w-[50px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center text-muted-foreground h-24"
                  >
                    No records. Click &quot;Add Record&quot; to add one.
                  </TableCell>
                </TableRow>
              )}
              {records.map((r) => (
                <TableRow
                  key={r._key}
                  className={
                    r._deleted
                      ? "opacity-50 line-through bg-destructive/5"
                      : ""
                  }
                >
                  <TableCell className="p-1">
                    <Input
                      value={r.name}
                      onChange={(e) =>
                        updateRecord(r._key, "name", e.target.value)
                      }
                      disabled={r._deleted}
                      className="h-8 text-sm"
                      placeholder="@"
                    />
                  </TableCell>
                  <TableCell className="p-1">
                    <Select
                      value={r.type}
                      onValueChange={(v) =>
                        updateRecord(r._key, "type", v)
                      }
                      disabled={r._deleted}
                    >
                      <SelectTrigger className="h-8 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RECORD_TYPES.map((t) => (
                          <SelectItem key={t} value={t}>
                            {t}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="p-1">
                    <Input
                      type="number"
                      value={r.ttl}
                      onChange={(e) =>
                        updateRecord(r._key, "ttl", parseInt(e.target.value) || 0)
                      }
                      disabled={r._deleted}
                      className="h-8 text-sm"
                    />
                  </TableCell>
                  <TableCell className="p-1">
                    <Input
                      value={r.data}
                      onChange={(e) =>
                        updateRecord(r._key, "data", e.target.value)
                      }
                      disabled={r._deleted}
                      className="h-8 text-sm font-mono"
                      placeholder="Record data"
                    />
                  </TableCell>
                  <TableCell className="p-1">
                    <Input
                      value={r.comment}
                      onChange={(e) =>
                        updateRecord(r._key, "comment", e.target.value)
                      }
                      disabled={r._deleted}
                      className="h-8 text-sm"
                    />
                  </TableCell>
                  <TableCell className="p-1 text-center">
                    <button
                      type="button"
                      onClick={() =>
                        updateRecord(r._key, "status", !r.status)
                      }
                      disabled={r._deleted}
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                        r.status
                          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {r.status ? "On" : "Off"}
                    </button>
                  </TableCell>
                  <TableCell className="p-1">
                    {r._deleted ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => restoreRecord(r._key)}
                      >
                        <Undo2 className="h-4 w-4" />
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => deleteRecord(r._key)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <p className="text-sm text-muted-foreground">
          {records.filter((r) => !r._deleted).length} record
          {records.filter((r) => !r._deleted).length !== 1 ? "s" : ""}
        </p>
      </div>
    </div>
  );
}
