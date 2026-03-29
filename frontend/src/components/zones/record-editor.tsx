"use client";

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { Plus, Trash2, Loader2, Undo2 } from "lucide-react";
import { toast } from "sonner";

import type { RecordItem, SubmittedRecord } from "@/hooks/use-zone-detail";
import { useApplyRecords } from "@/hooks/use-zone-detail";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  RecordDataHelperDialog,
  hasHelper,
} from "@/components/zones/record-data-helper";

// Common DNS record types
const DNS_RECORD_TYPES = [
  "A",
  "AAAA",
  "CNAME",
  "MX",
  "TXT",
  "NS",
  "SRV",
  "SOA",
  "PTR",
  "CAA",
  "NAPTR",
  "SPF",
  "SSHFP",
  "TLSA",
  "DS",
  "DNSKEY",
  "LOC",
  "HINFO",
  "RP",
];

const TTL_PRESETS = [
  { label: "1 min", value: "60" },
  { label: "5 min", value: "300" },
  { label: "15 min", value: "900" },
  { label: "1 hour", value: "3600" },
  { label: "4 hours", value: "14400" },
  { label: "8 hours", value: "28800" },
  { label: "1 day", value: "86400" },
  { label: "1 week", value: "604800" },
];

interface EditableRecord extends RecordItem {
  _key: string;
  _state: "original" | "modified" | "new" | "deleted";
}

interface RecordEditorProps {
  zoneName: string;
  records: RecordItem[];
  editableTypes: string[];
  readOnly?: boolean;
}

let nextKey = 0;
function genKey() {
  return `r-${++nextKey}`;
}

function recordsToEditable(records: RecordItem[]): EditableRecord[] {
  return records.map((r) => ({
    ...r,
    _key: genKey(),
    _state: "original" as const,
  }));
}

export function RecordEditor({
  zoneName,
  records: initialRecords,
  editableTypes,
  readOnly = false,
}: RecordEditorProps) {
  const [records, setRecords] = useState<EditableRecord[]>(() =>
    recordsToEditable(initialRecords)
  );
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [searchFilter, setSearchFilter] = useState("");
  const [helperKey, setHelperKey] = useState<string | null>(null);

  // The record currently open in the helper dialog
  const helperRecord = helperKey
    ? records.find((r) => r._key === helperKey)
    : null;
  const applyRecords = useApplyRecords(zoneName);
  const originalRef = useRef<RecordItem[]>(initialRecords);

  // Reset when initialRecords change (after successful apply / refetch)
  useEffect(() => {
    if (initialRecords !== originalRef.current) {
      originalRef.current = initialRecords;
      setRecords(recordsToEditable(initialRecords));
    }
  }, [initialRecords]);

  // Detect unsaved changes
  const hasChanges = useMemo(() => {
    const active = records.filter((r) => r._state !== "deleted");
    if (active.length !== originalRef.current.length) return true;
    return records.some((r) => r._state !== "original");
  }, [records]);

  // Unique record types for filter
  const availableTypes = useMemo(() => {
    const types = new Set(records.map((r) => r.type));
    return Array.from(types).sort();
  }, [records]);

  // Filtered records
  const filteredRecords = useMemo(() => {
    return records.filter((r) => {
      if (typeFilter !== "all" && r.type !== typeFilter) return false;
      if (searchFilter) {
        const q = searchFilter.toLowerCase();
        return (
          r.name.toLowerCase().includes(q) ||
          r.content.toLowerCase().includes(q) ||
          r.comment.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [records, typeFilter, searchFilter]);

  const updateRecord = useCallback(
    (key: string, field: keyof RecordItem, value: string | number | boolean) => {
      setRecords((prev) =>
        prev.map((r) => {
          if (r._key !== key) return r;
          return {
            ...r,
            [field]: value,
            _state: r._state === "new" ? "new" : "modified",
          };
        })
      );
    },
    []
  );

  const deleteRecord = useCallback((key: string) => {
    setRecords((prev) =>
      prev.flatMap((r) => {
        if (r._key !== key) return [r];
        // New records are removed entirely — they don't exist on the server
        if (r._state === "new") return [];
        return [{ ...r, _state: "deleted" as const }];
      })
    );
  }, []);

  const restoreRecord = useCallback((key: string) => {
    setRecords((prev) =>
      prev.map((r) => {
        if (r._key !== key) return r;
        return { ...r, _state: "original" as const };
      })
    );
  }, []);

  const addRecord = useCallback(() => {
    const newRecord: EditableRecord = {
      name: "",
      type: "A",
      ttl: 3600,
      content: "",
      disabled: false,
      comment: "",
      is_allowed_edit: true,
      _key: genKey(),
      _state: "new",
    };
    setRecords((prev) => [newRecord, ...prev]);
  }, []);

  const resetChanges = useCallback(() => {
    setRecords(recordsToEditable(originalRef.current));
  }, []);

  const handleApply = async () => {
    // Convert active records to submission format
    const active = records.filter((r) => r._state !== "deleted");
    const submitted: SubmittedRecord[] = active.map((r) => ({
      record_name: r.name,
      record_type: r.type,
      record_ttl: String(r.ttl),
      record_data: r.content,
      record_status: r.disabled ? "Disabled" : "Active",
      record_comment: r.comment,
    }));

    try {
      await applyRecords.mutateAsync(submitted);
      // Mark current state as the new baseline
      const activeRecords = records.filter((r) => r._state !== "deleted");
      const asOriginal = activeRecords.map((r) => ({
        ...r,
        _state: "original" as const,
      }));
      setRecords(asOriginal);
      originalRef.current = asOriginal.map(({ _key, _state, ...rest }) => rest);
      toast.success("Records applied successfully");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to apply records"
      );
    }
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Filter type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {availableTypes.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            placeholder="Search records..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-[200px]"
          />
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {hasChanges && (
            <Badge variant="outline" className="text-amber-600 border-amber-400">
              Unsaved changes
            </Badge>
          )}
          {!readOnly && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={resetChanges}
                disabled={!hasChanges}
              >
                <Undo2 className="mr-2 h-4 w-4" />
                Reset
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={addRecord}
              >
                <Plus className="mr-2 h-4 w-4" />
                Add Record
              </Button>
              <Button
                size="sm"
                onClick={handleApply}
                disabled={!hasChanges || applyRecords.isPending}
              >
                {applyRecords.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Apply Changes
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Records table */}
      <div className="rounded-md border overflow-x-auto">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[180px]">Name</TableHead>
              <TableHead className="w-[100px]">Type</TableHead>
              <TableHead className="w-[100px]">TTL</TableHead>
              <TableHead>Data</TableHead>
              <TableHead className="w-[70px]">Status</TableHead>
              <TableHead className="w-[160px]">Comment</TableHead>
              {!readOnly && (
                <TableHead className="w-[50px]" />
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRecords.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={readOnly ? 6 : 7}
                  className="text-center text-muted-foreground h-32"
                >
                  {records.length === 0
                    ? "No records found"
                    : "No records match the current filter"}
                </TableCell>
              </TableRow>
            )}
            {filteredRecords.map((record) => {
              const isEditable = record.is_allowed_edit && !readOnly;
              const isDeleted = record._state === "deleted";
              const isNew = record._state === "new";
              const isModified = record._state === "modified";

              return (
                <TableRow
                  key={record._key}
                  className={
                    isDeleted
                      ? "opacity-50 line-through bg-destructive/5"
                      : isNew
                        ? "bg-green-50 dark:bg-green-950/20"
                        : isModified
                          ? "bg-amber-50 dark:bg-amber-950/20"
                          : ""
                  }
                >
                  {/* Name */}
                  <TableCell className="p-1">
                    {isEditable && !isDeleted ? (
                      <Input
                        value={record.name}
                        onChange={(e) =>
                          updateRecord(record._key, "name", e.target.value)
                        }
                        placeholder="@"
                        className="h-8 text-sm"
                      />
                    ) : (
                      <span className="px-3 text-sm font-mono">
                        {record.name || "@"}
                      </span>
                    )}
                  </TableCell>

                  {/* Type */}
                  <TableCell className="p-1">
                    {isEditable && !isDeleted ? (
                      <Select
                        value={record.type}
                        onValueChange={(v) =>
                          updateRecord(record._key, "type", v)
                        }
                      >
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {editableTypes.map((t) => (
                            <SelectItem key={t} value={t}>
                              {t}
                            </SelectItem>
                          ))}
                          {/* Show current type if not in editable list */}
                          {!editableTypes.includes(record.type) && (
                            <SelectItem value={record.type}>
                              {record.type}
                            </SelectItem>
                          )}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Badge variant="secondary" className="font-mono">
                        {record.type}
                      </Badge>
                    )}
                  </TableCell>

                  {/* TTL */}
                  <TableCell className="p-1">
                    {isEditable && !isDeleted ? (
                      <Select
                        value={String(record.ttl)}
                        onValueChange={(v) =>
                          updateRecord(record._key, "ttl", parseInt(v, 10))
                        }
                      >
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {TTL_PRESETS.map((p) => (
                            <SelectItem key={p.value} value={p.value}>
                              {p.label}
                            </SelectItem>
                          ))}
                          {/* Show current value if not in presets */}
                          {!TTL_PRESETS.some(
                            (p) => p.value === String(record.ttl)
                          ) && (
                            <SelectItem value={String(record.ttl)}>
                              {record.ttl}s
                            </SelectItem>
                          )}
                        </SelectContent>
                      </Select>
                    ) : (
                      <span className="px-3 text-sm">{record.ttl}</span>
                    )}
                  </TableCell>

                  {/* Data */}
                  <TableCell className="p-1">
                    {isEditable && !isDeleted ? (
                      hasHelper(record.type) ? (
                        <button
                          type="button"
                          onClick={() => setHelperKey(record._key)}
                          className="flex h-8 w-full items-center rounded-md border border-input bg-background px-3 text-sm font-mono text-left truncate hover:bg-accent cursor-pointer"
                          title="Click to edit"
                        >
                          {record.content || (
                            <span className="text-muted-foreground">
                              Click to edit...
                            </span>
                          )}
                        </button>
                      ) : (
                        <Input
                          value={record.content}
                          onChange={(e) =>
                            updateRecord(
                              record._key,
                              "content",
                              e.target.value
                            )
                          }
                          placeholder="Record data"
                          className="h-8 text-sm font-mono"
                        />
                      )
                    ) : (
                      <span className="px-3 text-sm font-mono break-all">
                        {record.content}
                      </span>
                    )}
                  </TableCell>

                  {/* Status */}
                  <TableCell className="p-1 text-center">
                    {isEditable && !isDeleted ? (
                      <button
                        type="button"
                        onClick={() =>
                          updateRecord(
                            record._key,
                            "disabled",
                            !record.disabled
                          )
                        }
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                          record.disabled
                            ? "bg-muted text-muted-foreground"
                            : "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                        }`}
                      >
                        {record.disabled ? "Off" : "On"}
                      </button>
                    ) : (
                      <span
                        className={`text-xs ${
                          record.disabled
                            ? "text-muted-foreground"
                            : "text-green-600 dark:text-green-400"
                        }`}
                      >
                        {record.disabled ? "Off" : "On"}
                      </span>
                    )}
                  </TableCell>

                  {/* Comment */}
                  <TableCell className="p-1">
                    {isEditable && !isDeleted ? (
                      <Input
                        value={record.comment}
                        onChange={(e) =>
                          updateRecord(record._key, "comment", e.target.value)
                        }
                        placeholder=""
                        className="h-8 text-sm"
                      />
                    ) : (
                      <span className="px-3 text-sm text-muted-foreground">
                        {record.comment}
                      </span>
                    )}
                  </TableCell>

                  {/* Actions */}
                  {!readOnly && (
                    <TableCell className="p-1">
                      {isEditable && (
                        <>
                          {isDeleted ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => restoreRecord(record._key)}
                              title="Restore"
                            >
                              <Undo2 className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              onClick={() => deleteRecord(record._key)}
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Record count */}
      <div className="text-sm text-muted-foreground">
        {records.filter((r) => r._state !== "deleted").length} record
        {records.filter((r) => r._state !== "deleted").length !== 1 ? "s" : ""}
        {typeFilter !== "all" && ` (filtered: ${filteredRecords.length})`}
      </div>

      {/* Record data helper dialog */}
      {helperRecord && (
        <RecordDataHelperDialog
          type={helperRecord.type}
          value={helperRecord.content}
          open={!!helperKey}
          onOpenChange={(open) => {
            if (!open) setHelperKey(null);
          }}
          onApply={(value) => {
            updateRecord(helperRecord._key, "content", value);
          }}
        />
      )}
    </div>
  );
}
