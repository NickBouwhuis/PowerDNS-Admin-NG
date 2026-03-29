"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  let activeTab = "basic";
  if (pathname.endsWith("/pdns")) activeTab = "pdns";
  else if (pathname.endsWith("/records")) activeTab = "records";
  else if (pathname.endsWith("/auth")) activeTab = "auth";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configure PowerDNS-AdminNG application settings.
        </p>
      </div>

      <Tabs value={activeTab}>
        <TabsList>
          <TabsTrigger value="basic" asChild>
            <Link href="/admin/settings">Basic</Link>
          </TabsTrigger>
          <TabsTrigger value="pdns" asChild>
            <Link href="/admin/settings/pdns">PowerDNS</Link>
          </TabsTrigger>
          <TabsTrigger value="records" asChild>
            <Link href="/admin/settings/records">Records</Link>
          </TabsTrigger>
          <TabsTrigger value="auth" asChild>
            <Link href="/admin/settings/auth">Authentication</Link>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {children}
    </div>
  );
}
