"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useCreateZone } from "@/hooks/use-zones";
import { useAccounts, useTemplates } from "@/hooks/use-lookups";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function ZoneAddPage() {
  const router = useRouter();
  const createZone = useCreateZone();
  const { data: accounts = [] } = useAccounts();
  const { data: templates = [] } = useTemplates();

  const [name, setName] = useState("");
  const [type, setType] = useState("native");
  const [soaEditApi, setSoaEditApi] = useState("DEFAULT");
  const [accountId, setAccountId] = useState<string>("");
  const [templateId, setTemplateId] = useState<string>("");
  const [masterIps, setMasterIps] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Zone name is required");
      return;
    }

    try {
      await createZone.mutateAsync({
        name: name.trim(),
        type,
        soa_edit_api: soaEditApi,
        nameservers: [],
        master_ips: type === "slave"
          ? masterIps.split(",").map((ip) => ip.trim()).filter(Boolean)
          : [],
        account_id: accountId ? parseInt(accountId) : null,
        template_id: templateId ? parseInt(templateId) : null,
      });

      toast.success(`Zone ${name} created successfully`);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail);
      } else {
        toast.error("Failed to create zone");
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Add Zone</h1>
          <p className="text-muted-foreground">
            Create a new DNS zone in PowerDNS.
          </p>
        </div>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Zone Details</CardTitle>
          <CardDescription>
            Configure the basic settings for your new zone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="zone-name">Zone Name</Label>
              <Input
                id="zone-name"
                placeholder="example.com"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                required
              />
              <p className="text-xs text-muted-foreground">
                Enter the fully qualified domain name without a trailing dot.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Zone Type</Label>
                <Select value={type} onValueChange={setType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="native">Native</SelectItem>
                    <SelectItem value="master">Master</SelectItem>
                    <SelectItem value="slave">Slave</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>SOA-EDIT-API</Label>
                <Select value={soaEditApi} onValueChange={setSoaEditApi}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="DEFAULT">DEFAULT</SelectItem>
                    <SelectItem value="INCREASE">INCREASE</SelectItem>
                    <SelectItem value="EPOCH">EPOCH</SelectItem>
                    <SelectItem value="OFF">OFF</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {type === "slave" && (
              <div className="space-y-2">
                <Label htmlFor="master-ips">Master IP Addresses</Label>
                <Input
                  id="master-ips"
                  placeholder="192.168.1.1, 10.0.0.1"
                  value={masterIps}
                  onChange={(e) => setMasterIps(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Comma-separated list of master server IP addresses.
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label>Account</Label>
              <Select value={accountId} onValueChange={setAccountId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an account (optional)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">None</SelectItem>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id.toString()}>
                      {account.name}
                      {account.description ? ` - ${account.description}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {templates.length > 0 && (
              <div className="space-y-2">
                <Label>Template</Label>
                <Select value={templateId} onValueChange={setTemplateId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a template (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">None</SelectItem>
                    {templates.map((template) => (
                      <SelectItem
                        key={template.id}
                        value={template.id.toString()}
                      >
                        {template.name}
                        {template.description
                          ? ` - ${template.description}`
                          : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Optionally apply a record template after zone creation.
                </p>
              </div>
            )}

            <div className="flex gap-4">
              <Button type="submit" disabled={createZone.isPending}>
                {createZone.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Create Zone
              </Button>
              <Button variant="outline" type="button" asChild>
                <Link href="/">Cancel</Link>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
