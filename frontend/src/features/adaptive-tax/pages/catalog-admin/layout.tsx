import { useState, type FormEvent } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { LogOut, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { verifyCatalogAdminMutating, verifyCatalogAdminToken } from "./api";
import {
  clearCatalogAdminSession,
  loadCatalogAdminSession,
  saveCatalogAdminSession,
  type CatalogAdminSession,
} from "./session";

const INTERNAL_NAV = [
  { to: "/adaptive-tax/catalog-admin", end: true, label: "Queue" },
  { to: "/adaptive-tax/catalog-admin/upload", end: false, label: "Add New Act" },
] as const;

function SignInForm({ onSignedIn }: { onSignedIn: (session: CatalogAdminSession) => void }) {
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
      await verifyCatalogAdminToken(next);
      await verifyCatalogAdminMutating(next);
      saveCatalogAdminSession(next);
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
        <h1 className="text-lg font-semibold tracking-tight">Catalog admin</h1>
        <p className="text-sm text-muted-foreground">
          Add New Act is gated separately from Relief Interview. The token opens
          the door; your name is recorded on every later approve / reject /
          promote (not a second password).
        </p>
      </div>
      <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
        <div className="space-y-2">
          <Label htmlFor="catalog-admin-token">Access token</Label>
          <Input
            id="catalog-admin-token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="catalog-admin-reviewer">Your name</Label>
          <Input
            id="catalog-admin-reviewer"
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

export function CatalogAdminLayout() {
  const [session, setSession] = useState<CatalogAdminSession | null>(() =>
    loadCatalogAdminSession(),
  );

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
            Catalog admin
          </h1>
          <p className="text-sm text-muted-foreground">
            Upload a new Inland Revenue Act PDF. This is not the taxpayer interview.
          </p>
          <nav className="flex flex-wrap gap-1 pt-2" aria-label="Catalog admin">
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
            Reviewer{" "}
            <span className="font-medium text-foreground">{session.reviewer}</span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              clearCatalogAdminSession();
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
