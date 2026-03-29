import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface SearchZone {
  name: string;
  zone_id: string;
}

export interface SearchRecord {
  name: string;
  zone: string;
  type: string;
  content: string;
  ttl: number | null;
  disabled: boolean;
}

export interface SearchComment {
  name: string;
  zone: string;
  content: string;
}

export interface SearchResults {
  query: string;
  zones: SearchZone[];
  records: SearchRecord[];
  comments: SearchComment[];
}

export function useSearch(query: string) {
  return useQuery<SearchResults>({
    queryKey: ["search", query],
    queryFn: () =>
      api.get<SearchResults>(
        `/api/v2/search?q=${encodeURIComponent(query)}`
      ),
    enabled: query.length > 0,
  });
}
