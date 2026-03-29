"use client";

import { Globe, Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SidebarNav } from "./sidebar-nav";

export function MobileSidebar() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden">
          <Menu className="h-5 w-5" />
          <span className="sr-only">Open navigation</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-64 p-0">
        <SheetHeader className="flex h-14 flex-row items-center border-b px-4">
          <Globe className="h-5 w-5 text-primary" />
          <SheetTitle className="ml-2 text-lg">PowerDNS-AdminNG</SheetTitle>
        </SheetHeader>
        <ScrollArea className="flex-1 py-2">
          <SidebarNav />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
