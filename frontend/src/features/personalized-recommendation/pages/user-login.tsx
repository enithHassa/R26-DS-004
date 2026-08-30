import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Loader2, LogIn, Zap } from "lucide-react";

import { login } from "../api/auth";
import { useUserSessionStore } from "../store/user-session-store";

import "@/pages/demo/demo-theme.css";

export function UserLoginPage() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const profileId = useUserSessionStore((s) => s.profileId);
  const setSession = useUserSessionStore((s) => s.login);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useMutation({
    mutationFn: () => login({ username, password }),
    onSuccess: (result) => {
      setSession(result.role, result.user_id, result.profile_id, result.full_name);
      navigate(
        result.role === "auditor" ? "/" : result.profile_id ? "/taxwise" : "/portal/financial-intake",
        { replace: true },
      );
    },
  });

  if (isAuthenticated) {
    return (
      <Navigate
        to={role === "auditor" ? "/" : profileId ? "/taxwise" : "/portal/financial-intake"}
        replace
      />
    );
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    loginMutation.mutate();
  };

  return (
    <div className="demo-landing relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(900px circle at 20% 15%, rgba(45, 212, 191, 0.12) 0%, transparent 50%)," +
            "radial-gradient(700px circle at 85% 80%, rgba(45, 212, 191, 0.08) 0%, transparent 45%)",
        }}
        aria-hidden
      />

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Link to="/demo" className="mb-4 flex items-center gap-2.5">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--demo-accent)]">
              <Zap className="h-5 w-5 text-[var(--demo-accent-foreground)]" />
            </span>
            <span className="text-xl font-bold tracking-tight text-[var(--demo-text)]">
              TaxWise AI
            </span>
          </Link>
          <p className="text-sm text-[var(--demo-text-muted)]">
            Sign in to your tax advisory account
          </p>
        </div>

        <div className="rounded-xl border border-[var(--demo-border)] bg-[var(--demo-bg-card)] p-6 shadow-xl sm:p-8">
          <h1 className="mb-6 text-lg font-semibold text-[var(--demo-text)]">Sign in</h1>

          <form className="space-y-5" onSubmit={onSubmit}>
            <div className="space-y-1.5">
              <label
                htmlFor="username"
                className="block text-sm font-medium text-[var(--demo-text-muted)]"
              >
                Username or email
              </label>
              <input
                id="username"
                autoComplete="username"
                placeholder="Email or Taxpayer_00001"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-lg border border-[var(--demo-border)] bg-[var(--demo-bg)] px-3.5 py-2.5 text-sm text-[var(--demo-text)] outline-none placeholder:text-[var(--demo-text-muted)]/60 focus:border-[var(--demo-accent)]/50 focus:ring-1 focus:ring-[var(--demo-accent)]/40"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-sm font-medium text-[var(--demo-text-muted)]"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-[var(--demo-border)] bg-[var(--demo-bg)] px-3.5 py-2.5 text-sm text-[var(--demo-text)] outline-none placeholder:text-[var(--demo-text-muted)]/60 focus:border-[var(--demo-accent)]/50 focus:ring-1 focus:ring-[var(--demo-accent)]/40"
              />
            </div>

            {loginMutation.isError && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-sm text-red-300">
                {(loginMutation.error as Error).message}
              </div>
            )}

            <button
              type="submit"
              disabled={!username || !password || loginMutation.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--demo-accent)] px-4 py-2.5 text-sm font-semibold text-[var(--demo-accent-foreground)] transition-colors hover:bg-[var(--demo-accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
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
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-[var(--demo-text-muted)]">
          <Link to="/demo" className="text-[var(--demo-accent)] hover:text-[var(--demo-accent-hover)]">
            ← Back to TaxWise AI
          </Link>
        </p>
      </div>
    </div>
  );
}
