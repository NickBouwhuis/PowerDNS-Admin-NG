"use client";

import { Globe, PanelLeftClose, PanelLeft } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SidebarNav } from "./sidebar-nav";
import { ScrollArea } from "@/components/ui/scroll-area";

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 hidden border-r bg-sidebar transition-all duration-300 md:flex md:flex-col",
        collapsed ? "w-0 overflow-hidden" : "w-64"
      )}
    >
      <div className="flex h-14 items-center border-b px-4">
        <Globe className="h-5 w-5 shrink-0 text-sidebar-primary" />
        <span className="ml-2 text-lg font-semibold text-sidebar-foreground">
          PowerDNS-AdminNG
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="ml-auto h-7 w-7 text-sidebar-foreground/50 hover:text-sidebar-foreground"
          onClick={onToggle}
        >
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 py-2">
        <SidebarNav />
      </ScrollArea>
    </aside>
  );
}

export function SidebarToggle({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  if (!collapsed) return null;

  return (
    <Button
      variant="ghost"
      size="icon"
      className="hidden md:inline-flex h-7 w-7"
      onClick={onToggle}
    >
      <PanelLeft className="h-4 w-4" />
    </Button>
  );
}
