"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Globe, FileText, MessageSquare, Search } from "lucide-react";

import { useSearch } from "@/hooks/use-search";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

export function CommandSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const { data } = useSearch(query);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const navigate = useCallback(
    (path: string) => {
      setOpen(false);
      setQuery("");
      router.push(path);
    },
    [router]
  );

  return (
    <>
      <Button
        variant="outline"
        className="relative h-8 w-full max-w-sm justify-start text-sm text-muted-foreground sm:w-64"
        onClick={() => setOpen(true)}
      >
        <Search className="mr-2 h-4 w-4" />
        Search...
        <kbd className="pointer-events-none absolute right-1.5 hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 sm:flex">
          <span className="text-xs">&#8984;</span>K
        </kbd>
      </Button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput
          placeholder="Search zones, records, comments..."
          value={query}
          onValueChange={setQuery}
        />
        <CommandList>
          <CommandEmpty>
            {query.length > 0
              ? "No results found."
              : "Type to search..."}
          </CommandEmpty>

          {data?.zones && data.zones.length > 0 && (
            <CommandGroup heading="Zones">
              {data.zones.map((z) => (
                <CommandItem
                  key={z.zone_id}
                  value={`zone-${z.name}`}
                  onSelect={() =>
                    navigate(`/zones/${encodeURIComponent(z.name)}`)
                  }
                >
                  <Globe className="mr-2 h-4 w-4" />
                  {z.name}
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          {data?.records && data.records.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Records">
                {data.records.slice(0, 20).map((r, i) => (
                  <CommandItem
                    key={`${r.zone}-${r.name}-${r.type}-${i}`}
                    value={`record-${r.name}-${r.zone}-${r.type}`}
                    onSelect={() =>
                      navigate(`/zones/${encodeURIComponent(r.zone)}`)
                    }
                  >
                    <FileText className="mr-2 h-4 w-4" />
                    <span className="font-mono text-sm">{r.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {r.type}
                    </span>
                    <span className="ml-2 text-xs text-muted-foreground truncate max-w-48">
                      {r.content}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {r.zone}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}

          {data?.comments && data.comments.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Comments">
                {data.comments.slice(0, 10).map((c, i) => (
                  <CommandItem
                    key={`${c.zone}-${c.name}-${i}`}
                    value={`comment-${c.name}-${c.zone}-${c.content}`}
                    onSelect={() =>
                      navigate(`/zones/${encodeURIComponent(c.zone)}`)
                    }
                  >
                    <MessageSquare className="mr-2 h-4 w-4" />
                    <span className="font-mono text-sm">{c.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground truncate">
                      {c.content}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {c.zone}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
