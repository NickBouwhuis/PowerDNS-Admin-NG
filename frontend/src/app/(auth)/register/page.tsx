"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuthSettings } from "@/types/auth";
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

interface RegisterForm {
  firstname: string;
  lastname: string;
  username: string;
  email: string;
  password: string;
  rpassword: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState<RegisterForm>({
    firstname: "",
    lastname: "",
    username: "",
    email: "",
    password: "",
    rpassword: "",
  });

  const { data: settings } = useQuery<AuthSettings>({
    queryKey: ["auth", "settings"],
    queryFn: () => api.get<AuthSettings>("/api/v2/auth/settings"),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [authLoading, isAuthenticated, router]);

  const updateField = (field: keyof RegisterForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!form.firstname.trim()) errs.firstname = "First name is required";
    if (!form.lastname.trim()) errs.lastname = "Last name is required";
    if (!form.username.trim()) errs.username = "Username is required";
    if (!form.email.trim()) errs.email = "Email is required";
    else if (!/^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/.test(form.email))
      errs.email = "Invalid email address";
    if (!form.password) errs.password = "Password is required";
    if (!form.rpassword) errs.rpassword = "Password confirmation is required";
    if (form.password && form.rpassword && form.password !== form.rpassword) {
      errs.password = "Passwords do not match";
      errs.rpassword = "Passwords do not match";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const passwordStrength = (pw: string): { score: number; label: string } => {
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^a-zA-Z0-9]/.test(pw)) score++;

    const labels = ["Very Weak", "Weak", "Fair", "Good", "Strong"];
    return { score, label: labels[Math.min(score, labels.length - 1)] };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      // Registration goes through the existing web route for now,
      // since it handles captcha and email verification server-side.
      // We'll POST as form data to the existing endpoint.
      const formData = new FormData();
      formData.append("firstname", form.firstname);
      formData.append("lastname", form.lastname);
      formData.append("username", form.username);
      formData.append("email", form.email);
      formData.append("password", form.password);
      formData.append("rpassword", form.rpassword);

      const res = await fetch("/register", {
        method: "POST",
        credentials: "include",
        body: formData,
        redirect: "follow",
      });

      if (res.redirected || res.ok) {
        toast.success("Registration successful! Please sign in.");
        router.push("/login");
      } else {
        toast.error("Registration failed. Please try again.");
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

  const strength = passwordStrength(form.password);
  const strengthColors = [
    "bg-destructive",
    "bg-destructive",
    "bg-orange-500",
    "bg-yellow-500",
    "bg-green-500",
  ];

  if (authLoading) {
    return (
      <div className="flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (settings && !settings.signup_enabled) {
    return (
      <Card>
        <CardHeader className="text-center">
          <CardTitle>Registration Disabled</CardTitle>
          <CardDescription>
            Registration is currently disabled by the administrator.
          </CardDescription>
        </CardHeader>
        <CardFooter className="justify-center">
          <Link href="/login" className="text-primary hover:underline text-sm">
            Back to login
          </Link>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">Create Account</CardTitle>
        <CardDescription>Register for PowerDNS-AdminNG</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="firstname">First Name</Label>
              <Input
                id="firstname"
                value={form.firstname}
                onChange={(e) => updateField("firstname", e.target.value)}
                className={errors.firstname ? "border-destructive" : ""}
                required
              />
              {errors.firstname && (
                <p className="text-xs text-destructive">{errors.firstname}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastname">Last Name</Label>
              <Input
                id="lastname"
                value={form.lastname}
                onChange={(e) => updateField("lastname", e.target.value)}
                className={errors.lastname ? "border-destructive" : ""}
                required
              />
              {errors.lastname && (
                <p className="text-xs text-destructive">{errors.lastname}</p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={form.username}
              onChange={(e) => updateField("username", e.target.value)}
              autoComplete="username"
              className={errors.username ? "border-destructive" : ""}
              required
            />
            {errors.username && (
              <p className="text-xs text-destructive">{errors.username}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => updateField("email", e.target.value)}
              autoComplete="email"
              className={errors.email ? "border-destructive" : ""}
              required
            />
            {errors.email && (
              <p className="text-xs text-destructive">{errors.email}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => updateField("password", e.target.value)}
              autoComplete="new-password"
              className={errors.password ? "border-destructive" : ""}
              required
            />
            {form.password && (
              <div className="space-y-1">
                <div className="flex gap-1">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded-full ${
                        i < strength.score
                          ? strengthColors[strength.score - 1]
                          : "bg-muted"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {strength.label}
                </p>
              </div>
            )}
            {errors.password && (
              <p className="text-xs text-destructive">{errors.password}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="rpassword">Confirm Password</Label>
            <Input
              id="rpassword"
              type="password"
              value={form.rpassword}
              onChange={(e) => updateField("rpassword", e.target.value)}
              autoComplete="new-password"
              className={errors.rpassword ? "border-destructive" : ""}
              required
            />
            {errors.rpassword && (
              <p className="text-xs text-destructive">{errors.rpassword}</p>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Create Account"
            )}
          </Button>
        </form>
      </CardContent>
      <CardFooter className="justify-center">
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
