"use client";

import { MobileSidebar } from "./mobile-sidebar";
import { UserNav } from "./user-nav";
import { SidebarToggle } from "./app-sidebar";
import { CommandSearch } from "@/components/shared/command-search";

interface HeaderProps {
  sidebarCollapsed: boolean;
  onSidebarToggle: () => void;
}

export function Header({ sidebarCollapsed, onSidebarToggle }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b bg-background px-4 sm:px-6">
      <MobileSidebar />
      <SidebarToggle
        collapsed={sidebarCollapsed}
        onToggle={onSidebarToggle}
      />
      <div className="flex-1 flex justify-center">
        <CommandSearch />
      </div>
      <UserNav />
    </header>
  );
}
