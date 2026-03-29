"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ChevronDown, ChevronRight } from "lucide-react";

import { useZoneChangelog } from "@/hooks/use-zone-detail";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function ZoneChangelogPage() {
  const params = useParams();
  const zoneName = decodeURIComponent(params.name as string);
  const [page, setPage] = useState(1);
  const perPage = 25;
  const { data, isLoading, error } = useZoneChangelog(zoneName, page, perPage);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">
          {error instanceof ApiError
            ? error.detail
            : "Failed to load changelog"}
        </p>
      </div>
    );
  }

  if (!data || data.entries.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center text-muted-foreground">
        No changelog entries found for this zone.
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / perPage);

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        {data.total} changelog {data.total === 1 ? "entry" : "entries"}
      </div>

      <div className="space-y-2">
        {data.entries.map((entry) => {
          const isExpanded = expandedIds.has(entry.id);
          const hasDetail = entry.detail !== null;

          return (
            <div
              key={entry.id}
              className="rounded-lg border bg-card text-card-foreground"
            >
              <div
                className={`flex items-start gap-3 p-4 ${
                  hasDetail ? "cursor-pointer hover:bg-muted/50" : ""
                }`}
                onClick={() => hasDetail && toggleExpand(entry.id)}
              >
                {hasDetail && (
                  <span className="mt-0.5 text-muted-foreground">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </span>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{entry.msg}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="secondary" className="text-xs">
                      {entry.created_by}
                    </Badge>
                    {entry.created_on && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(entry.created_on).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {isExpanded && hasDetail && (
                <div className="border-t px-4 py-3">
                  <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap bg-muted rounded-md p-3">
                    {typeof entry.detail === "string"
                      ? entry.detail
                      : JSON.stringify(entry.detail, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
