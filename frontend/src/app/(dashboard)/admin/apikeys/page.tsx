"use client";

import { useState } from "react";
import {
  Plus,
  Loader2,
  MoreHorizontal,
  Trash2,
  Copy,
  Key,
} from "lucide-react";
import { toast } from "sonner";

import {
  useAdminApiKeys,
  useDeleteApiKey,
  useCreateApiKey,
  type AdminApiKeyCreated,
} from "@/hooks/use-admin";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

export default function ApiKeysPage() {
  const { data: keys, isLoading } = useAdminApiKeys();
  const deleteApiKey = useDeleteApiKey();
  const createApiKey = useCreateApiKey();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: number;
    description: string;
  } | null>(null);
  const [createdKey, setCreatedKey] = useState<AdminApiKeyCreated | null>(null);

  // Create form
  const [newDescription, setNewDescription] = useState("");
  const [newRole, setNewRole] = useState("User");
  const [newDomains, setNewDomains] = useState("");
  const [newAccounts, setNewAccounts] = useState("");

  const handleCreate = async () => {
    try {
      const result = await createApiKey.mutateAsync({
        description: newDescription,
        role_name: newRole,
        domain_names: newDomains
          .split(",")
          .map((d) => d.trim())
          .filter(Boolean),
        account_names: newAccounts
          .split(",")
          .map((a) => a.trim())
          .filter(Boolean),
      });
      setCreatedKey(result);
      setCreateOpen(false);
      setNewDescription("");
      setNewRole("User");
      setNewDomains("");
      setNewAccounts("");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to create API key"
      );
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteApiKey.mutateAsync(deleteTarget.id);
      toast.success("API key deleted");
      setDeleteTarget(null);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to delete API key"
      );
    }
  };

  const copyKey = () => {
    if (createdKey?.plain_key) {
      navigator.clipboard.writeText(createdKey.plain_key);
      toast.success("Key copied to clipboard");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
          <p className="text-muted-foreground">
            Manage API keys for programmatic access.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Key
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">ID</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-[120px]">Role</TableHead>
                <TableHead>Domains</TableHead>
                <TableHead>Accounts</TableHead>
                <TableHead className="w-[50px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(keys ?? []).length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center text-muted-foreground h-24"
                  >
                    No API keys found
                  </TableCell>
                </TableRow>
              ) : (
                (keys ?? []).map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-mono">{k.id}</TableCell>
                    <TableCell>{k.description || "—"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{k.role || "None"}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {k.domains.length > 0
                          ? k.domains.map((d) => (
                              <Badge
                                key={d.id}
                                variant="outline"
                                className="text-xs"
                              >
                                {d.name}
                              </Badge>
                            ))
                          : "—"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {k.accounts.length > 0
                          ? k.accounts.map((a) => (
                              <Badge
                                key={a.id}
                                variant="outline"
                                className="text-xs"
                              >
                                {a.name}
                              </Badge>
                            ))
                          : "—"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() =>
                              setDeleteTarget({
                                id: k.id,
                                description: k.description || `Key #${k.id}`,
                              })
                            }
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
            <DialogDescription>
              Create a new API key for programmatic access. The key will only be
              shown once.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="What is this key for?"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={newRole} onValueChange={setNewRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="User">User</SelectItem>
                  <SelectItem value="Operator">Operator</SelectItem>
                  <SelectItem value="Administrator">Administrator</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Domains</Label>
              <Input
                value={newDomains}
                onChange={(e) => setNewDomains(e.target.value)}
                placeholder="example.com, example.org (comma-separated)"
              />
              <p className="text-xs text-muted-foreground">
                Restrict key to specific zones (optional).
              </p>
            </div>
            <div className="space-y-2">
              <Label>Accounts</Label>
              <Input
                value={newAccounts}
                onChange={(e) => setNewAccounts(e.target.value)}
                placeholder="account1, account2 (comma-separated)"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={createApiKey.isPending}
            >
              {createApiKey.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Show created key */}
      <Dialog
        open={!!createdKey}
        onOpenChange={(open) => !open && setCreatedKey(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              API Key Created
            </DialogTitle>
            <DialogDescription>
              Copy this key now. It will not be shown again.
            </DialogDescription>
          </DialogHeader>
          {createdKey?.plain_key && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded-md bg-muted p-3 text-sm font-mono break-all">
                  {createdKey.plain_key}
                </code>
                <Button variant="outline" size="icon" onClick={copyKey}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Role: {createdKey.role} · ID: {createdKey.id}
              </p>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setCreatedKey(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete API Key</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete{" "}
              <strong>{deleteTarget?.description}</strong>? This cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteApiKey.isPending}
            >
              {deleteApiKey.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
