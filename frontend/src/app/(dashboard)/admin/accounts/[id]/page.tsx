"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  useAdminAccount,
  useUpdateAccount,
  useUpdateAccountMembers,
  useAdminUsers,
} from "@/hooks/use-admin";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function EditAccountPage() {
  const params = useParams();
  const accountId = parseInt(params.id as string);
  const { data: account, isLoading, error } = useAdminAccount(accountId);
  const { data: allUsers } = useAdminUsers();
  const updateAccount = useUpdateAccount(accountId);
  const updateMembers = useUpdateAccountMembers(accountId);

  const [description, setDescription] = useState("");
  const [contact, setContact] = useState("");
  const [mail, setMail] = useState("");
  const [memberIds, setMemberIds] = useState<number[]>([]);
  const [userSearch, setUserSearch] = useState("");

  useEffect(() => {
    if (account) {
      setDescription(account.description);
      setContact(account.contact);
      setMail(account.mail);
      setMemberIds(account.members.map((m) => m.id));
    }
  }, [account]);

  const handleSaveDetails = async () => {
    try {
      await updateAccount.mutateAsync({ description, contact, mail });
      toast.success("Account details updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update account"
      );
    }
  };

  const handleSaveMembers = async () => {
    try {
      await updateMembers.mutateAsync(memberIds);
      toast.success("Account members updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update members"
      );
    }
  };

  const toggleMember = (userId: number) => {
    setMemberIds((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId]
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !account) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">
          {error instanceof ApiError ? error.detail : "Account not found"}
        </p>
      </div>
    );
  }

  const filteredUsers = (allUsers ?? []).filter((u) =>
    u.username.toLowerCase().includes(userSearch.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/admin/accounts">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {account.name}
          </h1>
          <p className="text-muted-foreground">Edit account details and members.</p>
        </div>
      </div>

      {/* Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Account Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Description</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Contact</Label>
            <Input
              value={contact}
              onChange={(e) => setContact(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input
              type="email"
              value={mail}
              onChange={(e) => setMail(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            onClick={handleSaveDetails}
            disabled={updateAccount.isPending}
          >
            {updateAccount.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save Details
          </Button>
        </CardContent>
      </Card>

      {/* Members */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Members</CardTitle>
          <CardDescription>
            Users assigned to this account can access its zones.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            placeholder="Search users..."
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
          />
          <div className="max-h-[300px] overflow-y-auto border rounded-md">
            {filteredUsers.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground text-center">
                No users found
              </p>
            ) : (
              <div className="divide-y">
                {filteredUsers.map((u) => (
                  <label
                    key={u.id}
                    className="flex items-center gap-3 px-4 py-2 hover:bg-muted/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={memberIds.includes(u.id)}
                      onChange={() => toggleMember(u.id)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">{u.username}</span>
                    {u.role && (
                      <Badge variant="secondary" className="text-xs ml-auto">
                        {u.role}
                      </Badge>
                    )}
                  </label>
                ))}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {memberIds.length} member{memberIds.length !== 1 ? "s" : ""}{" "}
            selected
          </p>
          <Button
            size="sm"
            onClick={handleSaveMembers}
            disabled={updateMembers.isPending}
          >
            {updateMembers.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save Members
          </Button>
        </CardContent>
      </Card>

      {/* Domains */}
      {account.domains.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Domains</CardTitle>
            <CardDescription>
              Zones assigned to this account.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {account.domains.map((d) => (
                <Link
                  key={d.id}
                  href={`/zones/${encodeURIComponent(d.name)}`}
                >
                  <Badge variant="outline" className="cursor-pointer hover:bg-muted">
                    {d.name}
                  </Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
