"use client";

import { useState, useEffect } from "react";
import { Loader2, Shield, ShieldOff } from "lucide-react";
import { toast } from "sonner";

import { useProfile, useUpdateProfile, useToggleOtp } from "@/hooks/use-profile";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function ProfilePage() {
  const { data: profile, isLoading } = useProfile();
  const updateProfile = useUpdateProfile();
  const toggleOtp = useToggleOtp();

  const [firstname, setFirstname] = useState("");
  const [lastname, setLastname] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otpDialogOpen, setOtpDialogOpen] = useState(false);
  const [otpUri, setOtpUri] = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setFirstname(profile.firstname);
      setLastname(profile.lastname);
      setEmail(profile.email);
    }
  }, [profile]);

  const handleSaveProfile = async () => {
    try {
      await updateProfile.mutateAsync({
        firstname,
        lastname,
        email,
      });
      toast.success("Profile updated");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to update profile"
      );
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    if (!newPassword) {
      toast.error("Password cannot be empty");
      return;
    }
    try {
      await updateProfile.mutateAsync({ password: newPassword });
      setNewPassword("");
      setConfirmPassword("");
      toast.success("Password changed");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to change password"
      );
    }
  };

  const handleToggleOtp = async () => {
    if (!profile) return;
    const enable = !profile.otp_enabled;
    try {
      const result = await toggleOtp.mutateAsync(enable);
      if (enable && result.otp_uri) {
        setOtpUri(result.otp_uri);
        setOtpDialogOpen(true);
      }
      toast.success(enable ? "OTP enabled" : "OTP disabled");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to toggle OTP"
      );
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!profile) return null;

  const isLocalAuth = profile.auth_type === "LOCAL";

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account settings.
        </p>
      </div>

      {/* Profile info */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Personal Information</CardTitle>
              <CardDescription>
                Update your profile details.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Badge variant="secondary">{profile.role}</Badge>
              <Badge variant="outline">{profile.auth_type}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="username">Username</Label>
            <Input id="username" value={profile.username} disabled />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="firstname">First Name</Label>
              <Input
                id="firstname"
                value={firstname}
                onChange={(e) => setFirstname(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lastname">Last Name</Label>
              <Input
                id="lastname"
                value={lastname}
                onChange={(e) => setLastname(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <Button
            onClick={handleSaveProfile}
            disabled={updateProfile.isPending}
          >
            {updateProfile.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save Changes
          </Button>
        </CardContent>
      </Card>

      {/* Password */}
      {isLocalAuth && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Change Password</CardTitle>
            <CardDescription>
              Set a new password for your account.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm-password">Confirm Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
            <Button
              onClick={handleChangePassword}
              disabled={updateProfile.isPending || !newPassword}
            >
              {updateProfile.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Change Password
            </Button>
          </CardContent>
        </Card>
      )}

      {/* OTP */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Two-Factor Authentication</CardTitle>
          <CardDescription>
            {profile.otp_enabled
              ? "OTP is currently enabled on your account."
              : "Add an extra layer of security with OTP."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Badge variant={profile.otp_enabled ? "default" : "secondary"}>
              {profile.otp_enabled ? "Enabled" : "Disabled"}
            </Badge>
            <Button
              variant={profile.otp_enabled ? "destructive" : "default"}
              onClick={handleToggleOtp}
              disabled={toggleOtp.isPending}
            >
              {toggleOtp.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : profile.otp_enabled ? (
                <ShieldOff className="mr-2 h-4 w-4" />
              ) : (
                <Shield className="mr-2 h-4 w-4" />
              )}
              {profile.otp_enabled ? "Disable OTP" : "Enable OTP"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* OTP Setup Dialog */}
      <Dialog open={otpDialogOpen} onOpenChange={setOtpDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>OTP Setup</DialogTitle>
            <DialogDescription>
              Scan this QR code or enter the URI manually in your authenticator
              app.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {otpUri && (
              <>
                <div className="flex justify-center">
                  {/* QR code would be generated client-side with a library like qrcode.react */}
                  <div className="border rounded p-4 bg-muted text-center">
                    <p className="text-sm text-muted-foreground mb-2">
                      Use your authenticator app to scan:
                    </p>
                    <code className="text-xs break-all block max-w-sm">
                      {otpUri}
                    </code>
                  </div>
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setOtpDialogOpen(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
