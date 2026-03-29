"use client";

import { useState, useCallback } from "react";
import { Search, X } from "lucide-react";

import type { Zone, ZoneTab } from "@/types/zones";
import { useZones } from "@/hooks/use-zones";
import { DataTable } from "@/components/shared/data-table";
import { getZoneColumns } from "./zone-columns";
import { Input } from "@/components/ui/input";

interface ZoneTableProps {
  tab: ZoneTab;
  onDelete?: (zone: Zone) => void;
  onDnssec?: (zone: Zone) => void;
}

export function ZoneTable({ tab, onDelete, onDnssec }: ZoneTableProps) {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const perPage = 25;

  // Debounce search input
  const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(null);
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearch(value);
      if (debounceTimer) clearTimeout(debounceTimer);
      const timer = setTimeout(() => {
        setDebouncedSearch(value);
        setPage(1);
      }, 300);
      setDebounceTimer(timer);
    },
    [debounceTimer]
  );

  const handleSort = useCallback(
    (column: string) => {
      if (sortBy === column) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortBy(column);
        setSortDir("asc");
      }
      setPage(1);
    },
    [sortBy]
  );

  const { data, isLoading } = useZones({
    tab,
    search: debouncedSearch,
    sort_by: sortBy,
    sort_dir: sortDir,
    page,
    per_page: perPage,
  });

  const columns = getZoneColumns({
    onSort: handleSort,
    sortBy,
    sortDir,
    onDelete,
    onDnssec,
  });

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search zones..."
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-8 pr-8"
        />
        {search && (
          <button
            onClick={() => {
              setSearch("");
              setDebouncedSearch("");
              setPage(1);
            }}
            className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <DataTable
        columns={columns}
        data={data?.zones ?? []}
        total={data?.filtered ?? 0}
        page={page}
        perPage={perPage}
        onPageChange={setPage}
        isLoading={isLoading}
      />
    </div>
  );
}
