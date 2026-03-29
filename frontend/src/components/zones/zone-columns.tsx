"use client";

import { type ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { ArrowUpDown, Lock, LockOpen, MoreHorizontal, Trash2 } from "lucide-react";

import type { Zone } from "@/types/zones";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ZoneColumnsOptions {
  onSort: (column: string) => void;
  sortBy: string;
  sortDir: "asc" | "desc";
  onDelete?: (zone: Zone) => void;
  onDnssec?: (zone: Zone) => void;
}

export function getZoneColumns({
  onSort,
  sortBy,
  sortDir,
  onDelete,
  onDnssec,
}: ZoneColumnsOptions): ColumnDef<Zone>[] {
  const SortHeader = ({
    column,
    label,
  }: {
    column: string;
    label: string;
  }) => (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3 h-8"
      onClick={() => onSort(column)}
    >
      {label}
      <ArrowUpDown className="ml-2 h-4 w-4" />
      {sortBy === column && (
        <span className="ml-1 text-xs text-muted-foreground">
          {sortDir === "asc" ? "\u2191" : "\u2193"}
        </span>
      )}
    </Button>
  );

  return [
    {
      accessorKey: "name",
      header: () => <SortHeader column="name" label="Name" />,
      cell: ({ row }) => (
        <Link
          href={`/zones/${row.original.name}`}
          className="font-medium text-primary hover:underline"
        >
          {row.original.name}
        </Link>
      ),
    },
    {
      accessorKey: "dnssec",
      header: () => <SortHeader column="dnssec" label="DNSSEC" />,
      cell: ({ row }) => {
        const badge = row.original.dnssec ? (
          <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer">
            <Lock className="h-3 w-3" />
            On
          </Badge>
        ) : (
          <Badge variant="secondary" className="gap-1 bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 cursor-pointer">
            <LockOpen className="h-3 w-3" />
            Off
          </Badge>
        );
        return onDnssec ? (
          <button onClick={() => onDnssec(row.original)}>{badge}</button>
        ) : badge;
      },
    },
    {
      accessorKey: "type",
      header: () => <SortHeader column="type" label="Type" />,
      cell: ({ row }) => {
        const type = row.original.type;
        if (!type) return null;
        const lower = type.toLowerCase();
        if (lower === "master" || lower === "primary") {
          return <Badge className="bg-blue-600 text-white hover:bg-blue-700">{type}</Badge>;
        }
        if (lower === "slave" || lower === "secondary") {
          return <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-300">{type}</Badge>;
        }
        if (lower === "native") {
          return <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-200 dark:bg-purple-900/30 dark:text-purple-300">{type}</Badge>;
        }
        return <Badge variant="outline">{type}</Badge>;
      },
    },
    {
      accessorKey: "serial",
      header: () => <SortHeader column="serial" label="Serial" />,
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.serial ?? "-"}
        </span>
      ),
    },
    {
      accessorKey: "master",
      header: () => <SortHeader column="master" label="Master" />,
      cell: ({ row }) => {
        const masters = row.original.master;
        if (!masters || masters.length === 0) return <span className="text-muted-foreground">-</span>;
        return (
          <span className="text-xs">
            {masters.join(", ")}
          </span>
        );
      },
    },
    {
      accessorKey: "account",
      header: () => <SortHeader column="account" label="Account" />,
      cell: ({ row }) => (
        <span className={row.original.account ? "" : "text-muted-foreground"}>
          {row.original.account || "-"}
        </span>
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Actions</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href={`/zones/${row.original.name}`}>
                View Records
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href={`/zones/${row.original.name}/settings`}>
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href={`/zones/${row.original.name}/changelog`}>
                Changelog
              </Link>
            </DropdownMenuItem>
            {onDelete && (
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => onDelete(row.original)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];
}
