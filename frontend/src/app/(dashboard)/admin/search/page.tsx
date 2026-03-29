"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Globe, FileText, MessageSquare } from "lucide-react";

import { useSearch } from "@/hooks/use-search";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const { data, isLoading, isFetching } = useSearch(submitted);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      setSubmitted(query.trim());
    }
  };

  const totalResults =
    (data?.zones.length ?? 0) +
    (data?.records.length ?? 0) +
    (data?.comments.length ?? 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Global Search
        </h1>
        <p className="text-sm text-muted-foreground">
          Search across zones, records, and comments.
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 max-w-xl">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search zones, records, comments..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8"
            autoFocus
          />
        </div>
        <Button type="submit" disabled={!query.trim() || isFetching}>
          Search
        </Button>
      </form>

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-60 w-full" />
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            {totalResults} result{totalResults !== 1 ? "s" : ""} for &quot;{data.query}&quot;
          </p>

          {/* Zones */}
          {data.zones.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Zones
                  <Badge variant="secondary">{data.zones.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.zones.map((z) => (
                      <TableRow key={z.zone_id}>
                        <TableCell>
                          <Link
                            href={`/zones/${encodeURIComponent(z.name)}`}
                            className="font-mono text-sm text-primary hover:underline"
                          >
                            {z.name}
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* Records */}
          {data.records.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Records
                  <Badge variant="secondary">{data.records.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Zone</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Content</TableHead>
                      <TableHead>TTL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.records.map((r, i) => (
                      <TableRow key={`${r.zone}-${r.name}-${r.type}-${i}`}>
                        <TableCell className="font-mono text-sm">
                          {r.name}
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`/zones/${encodeURIComponent(r.zone)}`}
                            className="text-sm text-primary hover:underline"
                          >
                            {r.zone}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{r.type}</Badge>
                        </TableCell>
                        <TableCell className="font-mono text-sm max-w-xs truncate">
                          {r.content}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {r.ttl ?? "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* Comments */}
          {data.comments.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" />
                  Comments
                  <Badge variant="secondary">{data.comments.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Zone</TableHead>
                      <TableHead>Comment</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.comments.map((c, i) => (
                      <TableRow key={`${c.zone}-${c.name}-${i}`}>
                        <TableCell className="font-mono text-sm">
                          {c.name}
                        </TableCell>
                        <TableCell>
                          <Link
                            href={`/zones/${encodeURIComponent(c.zone)}`}
                            className="text-sm text-primary hover:underline"
                          >
                            {c.zone}
                          </Link>
                        </TableCell>
                        <TableCell className="text-sm">
                          {c.content}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {totalResults === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No results found for &quot;{data.query}&quot;.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
