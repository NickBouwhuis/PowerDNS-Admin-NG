"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Globe,
  LayoutDashboard,
  Users,
  Building2,
  KeyRound,
  FileText,
  History,
  Settings,
  Server,
  Search,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
}

const mainNav: NavItem[] = [
  {
    title: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
  },
];

const adminNav: NavItem[] = [
  {
    title: "Users",
    href: "/admin/users",
    icon: Users,
    roles: ["Administrator"],
  },
  {
    title: "Accounts",
    href: "/admin/accounts",
    icon: Building2,
    roles: ["Administrator", "Operator"],
  },
  {
    title: "API Keys",
    href: "/admin/apikeys",
    icon: KeyRound,
    roles: ["Administrator"],
  },
  {
    title: "Templates",
    href: "/admin/templates",
    icon: FileText,
    roles: ["Administrator", "Operator"],
  },
  {
    title: "History",
    href: "/admin/history",
    icon: History,
    roles: ["Administrator", "Operator"],
  },
  {
    title: "Global Search",
    href: "/admin/search",
    icon: Search,
    roles: ["Administrator", "Operator"],
  },
  {
    title: "Server Info",
    href: "/admin/server",
    icon: Server,
    roles: ["Administrator"],
  },
  {
    title: "Settings",
    href: "/admin/settings",
    icon: Settings,
    roles: ["Administrator"],
  },
];

export function SidebarNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const filteredAdminNav = adminNav.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <nav className="flex flex-col gap-1 px-2">
      {mainNav.map((item) => (
        <Button
          key={item.href}
          variant="ghost"
          className={cn(
            "w-full justify-start gap-2 text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent",
            isActive(item.href) &&
              "bg-sidebar-accent text-sidebar-foreground font-medium"
          )}
          asChild
        >
          <Link href={item.href}>
            <item.icon className="h-4 w-4" />
            {item.title}
          </Link>
        </Button>
      ))}

      {filteredAdminNav.length > 0 && (
        <>
          <div className="px-3 py-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/50">
              Administration
            </h3>
          </div>
          {filteredAdminNav.map((item) => (
            <Button
              key={item.href}
              variant="ghost"
              className={cn(
                "w-full justify-start gap-2 text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent",
                isActive(item.href) &&
                  "bg-sidebar-accent text-sidebar-foreground font-medium"
              )}
              asChild
            >
              <Link href={item.href}>
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            </Button>
          ))}
        </>
      )}
    </nav>
  );
}
