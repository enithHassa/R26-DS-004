import { useState, type FormEvent } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { verifyActAdminToken } from "./api";
import {
  clearActAdminSession,
  loadActAdminSession,
  saveActAdminSession,
  type ActAdminSession,
} from "./session";

const INTERNAL_NAV = [
  { to: "/optimization-explainable-engine/act-admin", end: true, label: "Queue" },
  { to: "/optimization-explainable-engine/act-admin/upload", end: false, label: "Add New Act" },
] as const;

function SignInForm({ onSignedIn }: { onSignedIn: (session: ActAdminSession) => void }) {
  const [token, setToken] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    const next = { token: token.trim(), reviewer: reviewer.trim() };
    if (!next.token || !next.reviewer) {
      setError("Enter both the access token and your name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await verifyActAdminToken(next);
      saveActAdminSession(next);
      onSignedIn(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-4 rounded-md border p-6">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold tracking-tight">Act admin</h1>
        <p className="text-sm text-muted-foreground">
          Upload Acts for the Optimization and Explainable Engine. Draft extracts stay out of live
          year views until you activate on review.
        </p>
        <p className="text-xs text-muted-foreground">
          Local dev: use{" "}
          <code className="rounded bg-muted px-1">OE_ENGINE_ACT_ADMIN_TOKEN</code> from{" "}
          <code className="rounded bg-muted px-1">.env</code> (default{" "}
          <code className="rounded bg-muted px-1">local-oe-act-admin</code>).
        </p>
      </div>
      <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
        <div className="space-y-2">
          <Label htmlFor="oe-act-admin-token">Access token</Label>
          <Input
            id="oe-act-admin-token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="oe-act-admin-reviewer">Your name</Label>
          <Input
            id="oe-act-admin-reviewer"
            type="text"
            autoComplete="name"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="e.g. A. Perera"
            required
          />
        </div>
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={busy}>
          {busy ? "Checking…" : "Continue"}
        </Button>
      </form>
    </div>
  );
}

export function ActAdminLayout() {
  const [session, setSession] = useState<ActAdminSession | null>(() => loadActAdminSession());

  if (!session) {
    return (
      <div className="mx-auto max-w-4xl p-4 sm:p-6">
        <SignInForm onSignedIn={setSession} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <ShieldCheck className="h-5 w-5 text-muted-foreground" aria-hidden />
            Act admin
          </h1>
          <p className="text-sm text-muted-foreground">
            Upload a new Inland Revenue Act PDF for this engine. This is not the taxpayer interview.
          </p>
          <nav className="flex flex-wrap gap-1 pt-2" aria-label="Act admin">
            {INTERNAL_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive
                    ? "rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground"
                    : "rounded-md px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            Reviewer <span className="font-medium text-foreground">{session.reviewer}</span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              clearActAdminSession();
              setSession(null);
            }}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
