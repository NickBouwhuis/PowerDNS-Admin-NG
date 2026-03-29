"use client";

import { useState, useCallback } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ---------------------------------------------------------------------------
// Types that have structured helpers
// ---------------------------------------------------------------------------

const HELPER_TYPES = new Set([
  "MX",
  "SRV",
  "CAA",
  "SSHFP",
  "TLSA",
  "NAPTR",
  "SOA",
  "TXT",
  "SPF",
]);

export function hasHelper(type: string): boolean {
  return HELPER_TYPES.has(type);
}

// ---------------------------------------------------------------------------
// Record type metadata (title + description)
// ---------------------------------------------------------------------------

const RECORD_META: Record<string, { title: string; description: string }> = {
  MX: {
    title: "MX Record",
    description: "Mail exchange — routes email to a mail server.",
  },
  SRV: {
    title: "SRV Record",
    description: "Service record — defines host and port for a service.",
  },
  CAA: {
    title: "CAA Record",
    description:
      "Certification Authority Authorization — controls which CAs can issue certificates.",
  },
  SSHFP: {
    title: "SSHFP Record",
    description: "SSH Fingerprint — publishes SSH host key fingerprints in DNS.",
  },
  TLSA: {
    title: "TLSA Record",
    description: "Associates a TLS certificate with a domain (DANE).",
  },
  NAPTR: {
    title: "NAPTR Record",
    description:
      "Naming Authority Pointer — used for ENUM, SIP, and URI rewriting.",
  },
  SOA: {
    title: "SOA Record",
    description:
      "Start of Authority — defines primary NS, admin contact, and zone timers.",
  },
  TXT: {
    title: "TXT Record",
    description:
      'Text record — include surrounding quotes for multi-part values. Long values are automatically chunked by PowerDNS.',
  },
  SPF: {
    title: "SPF Record",
    description:
      'Sender Policy Framework — defines which servers are allowed to send email for your domain.',
  },
};

// ---------------------------------------------------------------------------
// Parse / compose helpers per record type
// ---------------------------------------------------------------------------

function parseMX(data: string) {
  const parts = data.trim().split(/\s+/);
  return {
    priority: parts[0] || "10",
    server: parts.slice(1).join(" ") || "",
  };
}
function composeMX(f: { priority: string; server: string }) {
  return `${f.priority} ${f.server}`.trim();
}

function parseSRV(data: string) {
  const parts = data.trim().split(/\s+/);
  return {
    priority: parts[0] || "0",
    weight: parts[1] || "0",
    port: parts[2] || "0",
    target: parts[3] || "",
  };
}
function composeSRV(f: {
  priority: string;
  weight: string;
  port: string;
  target: string;
}) {
  return `${f.priority} ${f.weight} ${f.port} ${f.target}`.trim();
}

function parseCAA(data: string) {
  const match = data.match(/^(\d+)\s+(\S+)\s+"?(.+?)"?$/);
  if (match) return { flag: match[1], tag: match[2], value: match[3] };
  return { flag: "0", tag: "issue", value: "" };
}
function composeCAA(f: { flag: string; tag: string; value: string }) {
  return `${f.flag} ${f.tag} "${f.value}"`;
}

function parseSSHFP(data: string) {
  const parts = data.trim().split(/\s+/);
  return {
    algorithm: parts[0] || "1",
    fpType: parts[1] || "1",
    fingerprint: parts[2] || "",
  };
}
function composeSSHFP(f: {
  algorithm: string;
  fpType: string;
  fingerprint: string;
}) {
  return `${f.algorithm} ${f.fpType} ${f.fingerprint}`.trim();
}

function parseTLSA(data: string) {
  const parts = data.trim().split(/\s+/);
  return {
    usage: parts[0] || "3",
    selector: parts[1] || "1",
    matchingType: parts[2] || "1",
    certData: parts[3] || "",
  };
}
function composeTLSA(f: {
  usage: string;
  selector: string;
  matchingType: string;
  certData: string;
}) {
  return `${f.usage} ${f.selector} ${f.matchingType} ${f.certData}`.trim();
}

function parseNAPTR(data: string) {
  const parts = data.trim().split(/\s+/);
  return {
    order: parts[0] || "100",
    preference: parts[1] || "10",
    flags: parts[2] || '""',
    service: parts[3] || '""',
    regexp: parts[4] || '""',
    replacement: parts[5] || ".",
  };
}
function composeNAPTR(f: {
  order: string;
  preference: string;
  flags: string;
  service: string;
  regexp: string;
  replacement: string;
}) {
  return `${f.order} ${f.preference} ${f.flags} ${f.service} ${f.regexp} ${f.replacement}`.trim();
}

function parseSOA(data: string) {
  const parts = data.trim().split(/\s+/);
  return {
    primaryNs: parts[0] || "",
    adminEmail: parts[1] || "",
    serial: parts[2] || "0",
    refresh: parts[3] || "3600",
    retry: parts[4] || "900",
    expire: parts[5] || "604800",
    minimum: parts[6] || "86400",
  };
}
function composeSOA(f: {
  primaryNs: string;
  adminEmail: string;
  serial: string;
  refresh: string;
  retry: string;
  expire: string;
  minimum: string;
}) {
  return `${f.primaryNs} ${f.adminEmail} ${f.serial} ${f.refresh} ${f.retry} ${f.expire} ${f.minimum}`.trim();
}

// ---------------------------------------------------------------------------
// Individual helper forms
//
// Each form gets a `draft` string and `setDraft` callback.
// The draft is the working value shown in the "Result" preview.
// On "Apply" the parent commits draft → record content.
// ---------------------------------------------------------------------------

function MXHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseMX(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeMX(next));
  };
  return (
    <div className="grid grid-cols-[100px_1fr] gap-3">
      <div className="space-y-1.5">
        <Label>Priority</Label>
        <Input
          type="number"
          value={fields.priority}
          onChange={(e) => update({ priority: e.target.value })}
          placeholder="10"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Mail Server</Label>
        <Input
          value={fields.server}
          onChange={(e) => update({ server: e.target.value })}
          placeholder="mail.example.com."
        />
      </div>
    </div>
  );
}

function SRVHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseSRV(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeSRV(next));
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label>Priority</Label>
          <Input
            type="number"
            value={fields.priority}
            onChange={(e) => update({ priority: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Weight</Label>
          <Input
            type="number"
            value={fields.weight}
            onChange={(e) => update({ weight: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Port</Label>
          <Input
            type="number"
            value={fields.port}
            onChange={(e) => update({ port: e.target.value })}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Target</Label>
        <Input
          value={fields.target}
          onChange={(e) => update({ target: e.target.value })}
          placeholder="server.example.com."
        />
      </div>
    </div>
  );
}

function CAAHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseCAA(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeCAA(next));
  };
  return (
    <div className="grid grid-cols-[80px_120px_1fr] gap-3">
      <div className="space-y-1.5">
        <Label>Flag</Label>
        <Input
          type="number"
          value={fields.flag}
          onChange={(e) => update({ flag: e.target.value })}
          placeholder="0"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Tag</Label>
        <Select
          value={fields.tag}
          onValueChange={(v) => update({ tag: v })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="issue">issue</SelectItem>
            <SelectItem value="issuewild">issuewild</SelectItem>
            <SelectItem value="iodef">iodef</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Value</Label>
        <Input
          value={fields.value}
          onChange={(e) => update({ value: e.target.value })}
          placeholder="letsencrypt.org"
        />
      </div>
    </div>
  );
}

function SSHFPHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseSSHFP(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeSSHFP(next));
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Algorithm</Label>
          <Select
            value={fields.algorithm}
            onValueChange={(v) => update({ algorithm: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 — RSA</SelectItem>
              <SelectItem value="2">2 — DSA</SelectItem>
              <SelectItem value="3">3 — ECDSA</SelectItem>
              <SelectItem value="4">4 — Ed25519</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Fingerprint Type</Label>
          <Select
            value={fields.fpType}
            onValueChange={(v) => update({ fpType: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 — SHA-1</SelectItem>
              <SelectItem value="2">2 — SHA-256</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Fingerprint</Label>
        <Input
          className="font-mono"
          value={fields.fingerprint}
          onChange={(e) => update({ fingerprint: e.target.value })}
          placeholder="abc123..."
        />
      </div>
    </div>
  );
}

function TLSAHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseTLSA(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeTLSA(next));
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label>Usage</Label>
          <Select
            value={fields.usage}
            onValueChange={(v) => update({ usage: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">0 — CA</SelectItem>
              <SelectItem value="1">1 — Service</SelectItem>
              <SelectItem value="2">2 — Trust Anchor</SelectItem>
              <SelectItem value="3">3 — Domain-issued</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Selector</Label>
          <Select
            value={fields.selector}
            onValueChange={(v) => update({ selector: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">0 — Full cert</SelectItem>
              <SelectItem value="1">1 — Public key</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Matching Type</Label>
          <Select
            value={fields.matchingType}
            onValueChange={(v) => update({ matchingType: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">0 — Exact</SelectItem>
              <SelectItem value="1">1 — SHA-256</SelectItem>
              <SelectItem value="2">2 — SHA-512</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Certificate Data</Label>
        <Input
          className="font-mono"
          value={fields.certData}
          onChange={(e) => update({ certData: e.target.value })}
          placeholder="hex hash..."
        />
      </div>
    </div>
  );
}

function NAPTRHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseNAPTR(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeNAPTR(next));
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Order</Label>
          <Input
            type="number"
            value={fields.order}
            onChange={(e) => update({ order: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Preference</Label>
          <Input
            type="number"
            value={fields.preference}
            onChange={(e) => update({ preference: e.target.value })}
          />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label>Flags</Label>
          <Input
            value={fields.flags}
            onChange={(e) => update({ flags: e.target.value })}
            placeholder={'"S"'}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Service</Label>
          <Input
            value={fields.service}
            onChange={(e) => update({ service: e.target.value })}
            placeholder={'"SIP+D2U"'}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Regexp</Label>
          <Input
            value={fields.regexp}
            onChange={(e) => update({ regexp: e.target.value })}
            placeholder={'""'}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Replacement</Label>
        <Input
          value={fields.replacement}
          onChange={(e) => update({ replacement: e.target.value })}
          placeholder="_sip._udp.example.com."
        />
      </div>
    </div>
  );
}

function SOAHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  const [fields, setFields] = useState(() => parseSOA(draft));
  const update = (patch: Partial<typeof fields>) => {
    const next = { ...fields, ...patch };
    setFields(next);
    setDraft(composeSOA(next));
  };
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Primary Nameserver</Label>
          <Input
            value={fields.primaryNs}
            onChange={(e) => update({ primaryNs: e.target.value })}
            placeholder="ns1.example.com."
          />
        </div>
        <div className="space-y-1.5">
          <Label>Admin Email</Label>
          <Input
            value={fields.adminEmail}
            onChange={(e) => update({ adminEmail: e.target.value })}
            placeholder="hostmaster.example.com."
          />
        </div>
      </div>
      <div className="grid grid-cols-5 gap-3">
        <div className="space-y-1.5">
          <Label>Serial</Label>
          <Input
            value={fields.serial}
            onChange={(e) => update({ serial: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Refresh</Label>
          <Input
            type="number"
            value={fields.refresh}
            onChange={(e) => update({ refresh: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Retry</Label>
          <Input
            type="number"
            value={fields.retry}
            onChange={(e) => update({ retry: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Expire</Label>
          <Input
            type="number"
            value={fields.expire}
            onChange={(e) => update({ expire: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Minimum</Label>
          <Input
            type="number"
            value={fields.minimum}
            onChange={(e) => update({ minimum: e.target.value })}
          />
        </div>
      </div>
    </div>
  );
}

function TXTHelper({
  draft,
  setDraft,
}: {
  draft: string;
  setDraft: (v: string) => void;
}) {
  // Strip surrounding quotes for editing comfort
  const inner = draft.startsWith('"') && draft.endsWith('"')
    ? draft.slice(1, -1)
    : draft;
  const [text, setText] = useState(inner);

  const handleChange = (v: string) => {
    setText(v);
    // Always wrap in quotes for PowerDNS
    setDraft(`"${v}"`);
  };

  return (
    <div className="space-y-2">
      <Textarea
        className="font-mono min-h-[120px]"
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="v=spf1 include:example.com ~all"
      />
      <p className="text-xs text-muted-foreground">
        Quotes are added automatically. Just enter the value.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper form dispatcher
// ---------------------------------------------------------------------------

function HelperForm({
  type,
  draft,
  setDraft,
}: {
  type: string;
  draft: string;
  setDraft: (v: string) => void;
}) {
  switch (type) {
    case "MX":
      return <MXHelper draft={draft} setDraft={setDraft} />;
    case "SRV":
      return <SRVHelper draft={draft} setDraft={setDraft} />;
    case "CAA":
      return <CAAHelper draft={draft} setDraft={setDraft} />;
    case "SSHFP":
      return <SSHFPHelper draft={draft} setDraft={setDraft} />;
    case "TLSA":
      return <TLSAHelper draft={draft} setDraft={setDraft} />;
    case "NAPTR":
      return <NAPTRHelper draft={draft} setDraft={setDraft} />;
    case "SOA":
      return <SOAHelper draft={draft} setDraft={setDraft} />;
    case "TXT":
    case "SPF":
      return <TXTHelper draft={draft} setDraft={setDraft} />;
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Modal dialog — opened from the record editor
// ---------------------------------------------------------------------------

interface RecordDataHelperDialogProps {
  type: string;
  value: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply: (value: string) => void;
}

export function RecordDataHelperDialog({
  type,
  value,
  open,
  onOpenChange,
  onApply,
}: RecordDataHelperDialogProps) {
  const [draft, setDraft] = useState(value);

  // Re-sync draft when dialog opens with a new value
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (next) setDraft(value);
      onOpenChange(next);
    },
    [value, onOpenChange]
  );

  const meta = RECORD_META[type];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{meta?.title ?? type} Helper</DialogTitle>
          <DialogDescription>{meta?.description}</DialogDescription>
        </DialogHeader>

        <HelperForm type={type} draft={draft} setDraft={setDraft} />

        {/* Live preview */}
        <div className="space-y-1.5">
          <Label className="text-muted-foreground">Result</Label>
          <pre className="rounded-md bg-muted p-3 text-sm font-mono whitespace-pre-wrap break-all">
            {draft || <span className="text-muted-foreground italic">empty</span>}
          </pre>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onApply(draft);
              onOpenChange(false);
            }}
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
