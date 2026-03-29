"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Plus,
  Loader2,
  MoreHorizontal,
  Trash2,
  Pencil,
  Copy,
} from "lucide-react";
import { toast } from "sonner";

import {
  useAdminTemplates,
  useDeleteTemplate,
  useCreateTemplate,
  useCreateTemplateFromZone,
} from "@/hooks/use-admin";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function TemplatesPage() {
  const { data: templates, isLoading } = useAdminTemplates();
  const deleteTemplate = useDeleteTemplate();
  const createTemplate = useCreateTemplate();
  const createFromZone = useCreateTemplateFromZone();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: number;
    name: string;
  } | null>(null);

  // Create form
  const [createTab, setCreateTab] = useState("blank");
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [fromZoneName, setFromZoneName] = useState("");

  const handleCreate = async () => {
    if (!newName.trim()) {
      toast.error("Template name is required");
      return;
    }
    try {
      if (createTab === "from-zone") {
        if (!fromZoneName.trim()) {
          toast.error("Zone name is required");
          return;
        }
        await createFromZone.mutateAsync({
          name: newName.trim(),
          description: newDescription,
          zone_name: fromZoneName.trim(),
        });
      } else {
        await createTemplate.mutateAsync({
          name: newName.trim(),
          description: newDescription,
        });
      }
      toast.success(`Template ${newName} created`);
      setCreateOpen(false);
      setNewName("");
      setNewDescription("");
      setFromZoneName("");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to create template"
      );
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteTemplate.mutateAsync(deleteTarget.id);
      toast.success(`Template ${deleteTarget.name} deleted`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to delete template"
      );
    }
  };

  const isPending = createTemplate.isPending || createFromZone.isPending;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Templates</h1>
          <p className="text-muted-foreground">
            Manage domain templates for quick zone creation.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Template
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
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-[100px]">Records</TableHead>
                <TableHead className="w-[50px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(templates ?? []).length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-center text-muted-foreground h-24"
                  >
                    No templates found
                  </TableCell>
                </TableRow>
              ) : (
                (templates ?? []).map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell>{t.description || "—"}</TableCell>
                    <TableCell className="text-center">
                      {t.record_count}
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
                          <DropdownMenuItem asChild>
                            <Link href={`/admin/templates/${t.id}`}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() =>
                              setDeleteTarget({ id: t.id, name: t.name })
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
            <DialogTitle>Create Template</DialogTitle>
            <DialogDescription>
              Create a new domain template.
            </DialogDescription>
          </DialogHeader>
          <Tabs value={createTab} onValueChange={setCreateTab}>
            <TabsList className="w-full">
              <TabsTrigger value="blank" className="flex-1">
                Blank
              </TabsTrigger>
              <TabsTrigger value="from-zone" className="flex-1">
                From Zone
              </TabsTrigger>
            </TabsList>
            <div className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="template-name"
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Input
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </div>
              <TabsContent value="from-zone" className="mt-0">
                <div className="space-y-2">
                  <Label>Source Zone</Label>
                  <Input
                    value={fromZoneName}
                    onChange={(e) => setFromZoneName(e.target.value)}
                    placeholder="example.com"
                  />
                  <p className="text-xs text-muted-foreground">
                    Records from this zone will be copied into the template.
                  </p>
                </div>
              </TabsContent>
            </div>
          </Tabs>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={isPending}>
              {isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create
            </Button>
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
            <DialogTitle>Delete Template</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete template{" "}
              <strong>{deleteTarget?.name}</strong>? This will also delete all
              its records.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteTemplate.isPending}
            >
              {deleteTemplate.isPending && (
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
