"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import type { AuthSettings, LoginRequest } from "@/types/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading: authLoading } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otpToken, setOtpToken] = useState("");
  const [authMethod, setAuthMethod] = useState<"LOCAL" | "LDAP">("LOCAL");
  const [showOtp, setShowOtp] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: settings } = useQuery<AuthSettings>({
    queryKey: ["auth", "settings"],
    queryFn: () => api.get<AuthSettings>("/api/v2/auth/settings"),
    staleTime: 5 * 60 * 1000,
  });

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [authLoading, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;

    setIsSubmitting(true);
    try {
      const data: LoginRequest = {
        username,
        password,
        auth_method: authMethod,
      };
      if (showOtp && otpToken) {
        data.otp_token = otpToken;
      }

      const result = await login(data);

      if (result.status === "otp_required") {
        setShowOtp(true);
        toast.info("Please enter your OTP token");
      } else if (result.status === "otp_setup_required") {
        toast.info("OTP setup required");
        router.push("/welcome");
      } else if (result.status === "ok") {
        router.push("/");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail);
      } else {
        toast.error("An unexpected error occurred");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const hasOAuth =
    settings &&
    (settings.google_oauth_enabled ||
      settings.github_oauth_enabled ||
      settings.azure_oauth_enabled ||
      settings.oidc_oauth_enabled);
  const hasSaml = settings?.saml_enabled;
  const hasExternalAuth = hasOAuth || hasSaml;

  if (authLoading) {
    return (
      <div className="flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">PowerDNS-AdminNG</CardTitle>
        <CardDescription>Sign in to manage your DNS zones</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {showOtp && (
            <div className="space-y-2">
              <Label htmlFor="otp">OTP Token</Label>
              <Input
                id="otp"
                type="text"
                placeholder="6-digit code"
                value={otpToken}
                onChange={(e) => setOtpToken(e.target.value)}
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                autoFocus
                required
              />
            </div>
          )}

          {settings?.ldap_enabled && (
            <div className="flex items-center gap-4">
              <Label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="auth_method"
                  value="LOCAL"
                  checked={authMethod === "LOCAL"}
                  onChange={() => setAuthMethod("LOCAL")}
                  className="accent-primary"
                />
                Local
              </Label>
              <Label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="auth_method"
                  value="LDAP"
                  checked={authMethod === "LDAP"}
                  onChange={() => setAuthMethod("LDAP")}
                  className="accent-primary"
                />
                LDAP
              </Label>
            </div>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Sign In"
            )}
          </Button>
        </form>

        {hasExternalAuth && (
          <>
            <div className="relative my-4">
              <Separator />
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                or continue with
              </span>
            </div>

            <div className="grid gap-2">
              {settings?.google_oauth_enabled && (
                <Button variant="outline" className="w-full" asChild>
                  <a href="/google/login">Google</a>
                </Button>
              )}
              {settings?.github_oauth_enabled && (
                <Button variant="outline" className="w-full" asChild>
                  <a href="/github/login">GitHub</a>
                </Button>
              )}
              {settings?.azure_oauth_enabled && (
                <Button variant="outline" className="w-full" asChild>
                  <a href="/azure/login">Microsoft</a>
                </Button>
              )}
              {settings?.oidc_oauth_enabled && (
                <Button variant="outline" className="w-full" asChild>
                  <a href="/oidc/login">OpenID Connect</a>
                </Button>
              )}
              {settings?.saml_enabled && (
                <Button variant="outline" className="w-full" asChild>
                  <a href="/saml/login">SAML SSO</a>
                </Button>
              )}
            </div>
          </>
        )}
      </CardContent>

      {settings?.signup_enabled && (
        <CardFooter className="justify-center">
          <p className="text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-primary hover:underline">
              Sign up
            </Link>
          </p>
        </CardFooter>
      )}
    </Card>
  );
}
