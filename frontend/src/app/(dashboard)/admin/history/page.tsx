"use client";

import { useState } from "react";
import { Loader2, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

import { useHistory, useClearHistory, type HistoryFilters } from "@/hooks/use-history";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export default function HistoryPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<HistoryFilters>({
    page: 1,
    per_page: 50,
  });
  const [domainInput, setDomainInput] = useState("");
  const [userInput, setUserInput] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [clearOpen, setClearOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data, isLoading } = useHistory(filters);
  const clearHistory = useClearHistory();
  const isAdmin = user?.role === "Administrator";

  const applyFilters = () => {
    setFilters({
      ...filters,
      page: 1,
      domain_name: domainInput || undefined,
      user_name: userInput || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    });
  };

  const resetFilters = () => {
    setDomainInput("");
    setUserInput("");
    setDateFrom("");
    setDateTo("");
    setFilters({ page: 1, per_page: 50 });
  };

  const totalPages = data ? Math.ceil(data.total / (filters.per_page || 50)) : 0;

  const handleClear = async () => {
    try {
      await clearHistory.mutateAsync();
      toast.success("History cleared");
      setClearOpen(false);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to clear history"
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">History</h1>
          <p className="text-sm text-muted-foreground">
            View activity log and audit trail.
          </p>
        </div>
        {isAdmin && (
          <Dialog open={clearOpen} onOpenChange={setClearOpen}>
            <DialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="mr-2 h-4 w-4" />
                Clear All
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Clear all history?</DialogTitle>
                <DialogDescription>
                  This will permanently remove all history entries. This action
                  cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setClearOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleClear}
                  disabled={clearHistory.isPending}
                >
                  {clearHistory.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Clear All
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filters</CardTitle>
          <CardDescription>Narrow down history entries.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="domain">Zone</Label>
              <Input
                id="domain"
                placeholder="example.com"
                value={domainInput}
                onChange={(e) => setDomainInput(e.target.value)}
                className="w-48"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="user">User</Label>
              <Input
                id="user"
                placeholder="admin"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="from">From</Label>
              <Input
                id="from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to">To</Label>
              <Input
                id="to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-40"
              />
            </div>
            <Button onClick={applyFilters}>Apply</Button>
            <Button variant="outline" onClick={resetFilters}>
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Time</TableHead>
                  <TableHead className="w-[120px]">User</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.entries.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={3}
                      className="text-center text-muted-foreground py-8"
                    >
                      No history entries found.
                    </TableCell>
                  </TableRow>
                )}
                {data?.entries.map((entry) => (
                  <TableRow
                    key={entry.id}
                    className="cursor-pointer"
                    onClick={() =>
                      setExpandedId(
                        expandedId === entry.id ? null : entry.id
                      )
                    }
                  >
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {entry.created_on
                        ? new Date(entry.created_on).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {entry.created_by}
                    </TableCell>
                    <TableCell>
                      <div>{entry.msg}</div>
                      {expandedId === entry.id && entry.detail && (
                        <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-x-auto max-w-2xl">
                          {typeof entry.detail === "string"
                            ? entry.detail
                            : JSON.stringify(entry.detail, null, 2)}
                        </pre>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <p className="text-sm text-muted-foreground">
                {data?.total ?? 0} total entries
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={(filters.page ?? 1) <= 1}
                  onClick={() =>
                    setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))
                  }
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">
                  Page {filters.page ?? 1} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={(filters.page ?? 1) >= totalPages}
                  onClick={() =>
                    setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))
                  }
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
