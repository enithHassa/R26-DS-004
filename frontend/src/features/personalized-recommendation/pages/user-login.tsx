import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Coins,
  Landmark,
  Loader2,
  LogIn,
  Percent,
  PiggyBank,
  Receipt,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { login } from "../api/auth";
import { useUserSessionStore } from "../store/user-session-store";

const DOT_GRID_BG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='2' cy='2' r='1.4' fill='white' fill-opacity='0.14'/%3E%3C/svg%3E";

export function UserLoginPage() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const setSession = useUserSessionStore((s) => s.login);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useMutation({
    mutationFn: () => login({ username, password }),
    onSuccess: (result) => {
      setSession(result.role, result.profile_id, result.full_name);
      navigate(result.role === "auditor" ? "/" : "/portal", { replace: true });
    },
  });

  if (isAuthenticated) {
    return <Navigate to={role === "auditor" ? "/" : "/portal"} replace />;
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    loginMutation.mutate();
  };

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10"
      style={{
        background:
          "radial-gradient(1200px circle at 15% 20%, color-mix(in srgb, var(--tax-accent) 55%, transparent) 0%, transparent 42%)," +
          "radial-gradient(1000px circle at 85% 75%, color-mix(in srgb, var(--primary) 65%, transparent) 0%, transparent 50%)," +
          "radial-gradient(800px circle at 50% 100%, color-mix(in srgb, var(--tax-accent) 30%, transparent) 0%, transparent 55%)," +
          "linear-gradient(160deg, #241419 0%, #150d10 55%, #1b1013 100%)",
      }}
    >
      {/* subtle dot-grid texture for depth */}
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{ backgroundImage: `url("${DOT_GRID_BG}")`, backgroundSize: "40px 40px" }}
        aria-hidden
      />

      {/* soft glow ring behind the card */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
        style={{ background: "color-mix(in srgb, var(--tax-accent) 35%, transparent)" }}
        aria-hidden
      />

      {/* scattered tax-themed watermark icons */}
      <Landmark className="pointer-events-none absolute -left-8 -top-8 h-56 w-56 text-white/[0.06]" strokeWidth={0.75} />
      <TrendingUp className="pointer-events-none absolute left-12 bottom-24 h-24 w-24 text-white/10" strokeWidth={1} />
      <Percent
        className="pointer-events-none absolute right-14 top-20 h-28 w-28 rotate-12 text-[var(--tax-accent)]/25 drop-shadow-[0_0_18px_var(--tax-accent)]"
        strokeWidth={1}
      />
      <Receipt className="pointer-events-none absolute bottom-16 left-20 h-36 w-36 -rotate-6 text-white/[0.08]" strokeWidth={0.75} />
      <PiggyBank className="pointer-events-none absolute right-24 bottom-10 h-20 w-20 rotate-6 text-white/10" strokeWidth={1} />
      <Coins className="pointer-events-none absolute -bottom-10 -right-10 h-52 w-52 text-white/[0.06]" strokeWidth={0.75} />

      <div className="relative z-10 flex w-full max-w-sm flex-col items-center">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 shadow-lg ring-1 ring-white/20 backdrop-blur-sm">
            <Wallet className="h-7 w-7 text-white" />
          </div>
          <div className="text-lg font-semibold tracking-tight text-white">AI Tax Advisory</div>
          <div className="text-xs text-white/60">Decision Support</div>
        </div>

        <Card className="w-full border-white/10 bg-white/95 shadow-2xl backdrop-blur-md">
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
          </CardHeader>
          <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
                placeholder="Taxpayer_25265"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {loginMutation.isError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                {(loginMutation.error as Error).message}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={!username || !password || loginMutation.isPending}
            >
              {loginMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  <LogIn className="h-4 w-4" />
                  Sign in
                </>
              )}
            </Button>
          </form>
        </CardContent>
        </Card>
      </div>
    </div>
  );
}
