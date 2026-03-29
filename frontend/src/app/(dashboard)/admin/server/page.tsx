"use client";

import { useState } from "react";
import {
  Activity,
  Globe,
  Users,
  History,
  Clock,
  Search,
} from "lucide-react";

import {
  useServerStatistics,
  useServerConfiguration,
} from "@/hooks/use-server";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export default function ServerPage() {
  const { data: stats, isLoading: statsLoading } = useServerStatistics();
  const { data: config, isLoading: configLoading } = useServerConfiguration();
  const [statsFilter, setStatsFilter] = useState("");
  const [configFilter, setConfigFilter] = useState("");

  const filteredStats = stats?.pdns_stats.filter(
    (s) => {
      const q = statsFilter.toLowerCase();
      const val = typeof s.value === "string" ? s.value : JSON.stringify(s.value);
      return s.name.toLowerCase().includes(q) || val.toLowerCase().includes(q);
    }
  );

  const filteredConfig = config?.config.filter(
    (c) => {
      const q = configFilter.toLowerCase();
      const val = typeof c.value === "string" ? c.value : JSON.stringify(c.value);
      return c.name.toLowerCase().includes(q) || val.toLowerCase().includes(q);
    }
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Server Info</h1>
        <p className="text-sm text-muted-foreground">
          PowerDNS server statistics and configuration.
        </p>
      </div>

      {/* Summary cards */}
      {statsLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Uptime</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.uptime != null ? formatUptime(stats.uptime) : "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Zones</CardTitle>
              <Globe className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.zone_count ?? "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.user_count ?? "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                History Entries
              </CardTitle>
              <History className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.history_count ?? "—"}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs: Statistics + Configuration */}
      <Tabs defaultValue="statistics">
        <TabsList>
          <TabsTrigger value="statistics">
            <Activity className="mr-2 h-4 w-4" />
            Statistics
          </TabsTrigger>
          <TabsTrigger value="configuration">
            Configuration
          </TabsTrigger>
        </TabsList>

        <TabsContent value="statistics">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">PowerDNS Statistics</CardTitle>
              <CardDescription>
                Live statistics from the PowerDNS Authoritative Server.
              </CardDescription>
              <div className="relative mt-2">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Filter statistics..."
                  value={statsFilter}
                  onChange={(e) => setStatsFilter(e.target.value)}
                  className="pl-8 max-w-sm"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {statsLoading ? (
                <div className="p-6 space-y-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredStats?.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={3}
                          className="text-center text-muted-foreground py-8"
                        >
                          No statistics match your filter.
                        </TableCell>
                      </TableRow>
                    )}
                    {filteredStats?.map((s) => (
                      <TableRow key={s.name}>
                        <TableCell className="font-mono text-sm">
                          {s.name}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {s.type}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {s.value}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="configuration">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                PowerDNS Configuration
              </CardTitle>
              <CardDescription>
                Current configuration of the PowerDNS Authoritative Server.
              </CardDescription>
              <div className="relative mt-2">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Filter configuration..."
                  value={configFilter}
                  onChange={(e) => setConfigFilter(e.target.value)}
                  className="pl-8 max-w-sm"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {configLoading ? (
                <div className="p-6 space-y-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredConfig?.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={2}
                          className="text-center text-muted-foreground py-8"
                        >
                          No configuration items match your filter.
                        </TableCell>
                      </TableRow>
                    )}
                    {filteredConfig?.map((c) => (
                      <TableRow key={c.name}>
                        <TableCell className="font-mono text-sm">
                          {c.name}
                        </TableCell>
                        <TableCell className="font-mono text-sm break-all">
                          {c.value || "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
