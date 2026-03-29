"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { useZoneDetail } from "@/hooks/use-zone-detail";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ZoneDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const zoneName = decodeURIComponent(params.name as string);

  const { data, isLoading } = useZoneDetail(zoneName);

  // Determine active tab from pathname
  let activeTab = "records";
  if (pathname.endsWith("/settings")) activeTab = "settings";
  else if (pathname.endsWith("/changelog")) activeTab = "changelog";

  const basePath = `/zones/${encodeURIComponent(zoneName)}`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1 min-w-0">
          {isLoading ? (
            <>
              <Skeleton className="h-8 w-64 mb-1" />
              <Skeleton className="h-4 w-48" />
            </>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight truncate">
                  {zoneName}
                </h1>
                {data?.zone.type && (
                  <Badge variant="secondary">{data.zone.type}</Badge>
                )}
                {data?.zone.dnssec && (
                  <Badge variant="outline">DNSSEC</Badge>
                )}
              </div>
              <p className="text-muted-foreground text-sm">
                {data?.zone.serial ? `Serial: ${data.zone.serial}` : ""}
                {data?.zone.account ? ` · Account: ${data.zone.account}` : ""}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Tab navigation */}
      <Tabs value={activeTab}>
        <TabsList>
          <TabsTrigger value="records" asChild>
            <Link href={basePath}>Records</Link>
          </TabsTrigger>
          <TabsTrigger value="settings" asChild>
            <Link href={`${basePath}/settings`}>Settings</Link>
          </TabsTrigger>
          <TabsTrigger value="changelog" asChild>
            <Link href={`${basePath}/changelog`}>Changelog</Link>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Page content */}
      {children}
    </div>
  );
}
