export interface Zone {
  id: number;
  name: string;
  type: string | null;
  dnssec: boolean;
  serial: number | null;
  notified_serial: number | null;
  master: string[];
  account: string | null;
  account_id: number | null;
}

export interface ZoneListResponse {
  total: number;
  filtered: number;
  zones: Zone[];
}

export interface ZoneCreateRequest {
  name: string;
  type: string;
  soa_edit_api: string;
  nameservers: string[];
  master_ips: string[];
  account_id: number | null;
  template_id: number | null;
}

export interface ZoneCreateResponse {
  status: string;
  message: string;
  zone: Zone | null;
}

export type ZoneTab = "forward" | "reverse_ipv4" | "reverse_ipv6";

export interface ZoneListParams {
  tab: ZoneTab;
  search: string;
  sort_by: string;
  sort_dir: "asc" | "desc";
  page: number;
  per_page: number;
}
