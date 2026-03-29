"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, KeyRound } from "lucide-react";
import { toast } from "sonner";

import { useAdminUser, useUpdateUser } from "@/hooks/use-admin";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function EditUserPage() {
  const params = useParams();
  const router = useRouter();
  const username = decodeURIComponent(params.username as string);
  const { data: user, isLoading, error } = useAdminUser(username);

  const [firstname, setFirstname] = useState("");
  const [lastname, setLastname] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("User");
  const [password, setPassword] = useState("");

  const updateUser = useUpdateUser(user?.id ?? 0);

  useEffect(() => {
    if (user) {
      setFirstname(user.firstname);
      setLastname(user.lastname);
      setEmail(user.email);
      setRole(user.role || "User");
    }
  }, [user]);

  const handleSave = async () => {
    try {
      const data: Record<string, string> = {
        firstname,
        lastname,
        email,
        role_name: role,
      };
      if (password) data.password = password;
      await updateUser.mutateAsync(data);
      toast.success("User updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update user"
      );
    }
  };

  const handleDisableOtp = async () => {
    try {
      await updateUser.mutateAsync({ otp_secret: "" });
      toast.success("OTP disabled");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to disable OTP"
      );
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">
          {error instanceof ApiError ? error.detail : "User not found"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/admin/users">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{username}</h1>
          <p className="text-muted-foreground">Edit user details and role.</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">User Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>First Name</Label>
              <Input
                value={firstname}
                onChange={(e) => setFirstname(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Last Name</Label>
              <Input
                value={lastname}
                onChange={(e) => setLastname(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Select value={role} onValueChange={setRole}>
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
            <Label>New Password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Leave empty to keep current"
            />
          </div>
          <Button onClick={handleSave} disabled={updateUser.isPending}>
            {updateUser.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save Changes
          </Button>
        </CardContent>
      </Card>

      {/* OTP */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Two-Factor Authentication</CardTitle>
          <CardDescription>
            {user.otp_enabled
              ? "OTP is currently enabled for this user."
              : "OTP is not configured."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {user.otp_enabled ? (
            <div className="flex items-center gap-4">
              <Badge
                variant="outline"
                className="text-green-600 border-green-400"
              >
                <KeyRound className="mr-1 h-3 w-3" />
                Enabled
              </Badge>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDisableOtp}
                disabled={updateUser.isPending}
              >
                Disable OTP
              </Button>
            </div>
          ) : (
            <Badge variant="secondary">Not configured</Badge>
          )}
        </CardContent>
      </Card>

      {/* Accounts */}
      {user.accounts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Accounts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {user.accounts.map((a) => (
                <Badge key={a.id} variant="secondary">
                  {a.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
