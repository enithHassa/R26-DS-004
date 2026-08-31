import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, Lock, LockOpen, LogOut, Search, ShieldCheck, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listProfiles } from "@/features/personalized-recommendation/api/profiles";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import type { FinancialProfile } from "@/features/personalized-recommendation/types";
import { profileToAuditorSummary } from "@/lib/profile-bridge/profile-summary";
import { cn } from "@/lib/utils";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

function profileMatchesQuery(profile: FinancialProfile, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const haystack = [
    profile.full_name,
    profile.occupation,
    profile.tax_year,
    profile.transaction_taxpayer_id ?? "",
    profile.id,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

export function AuditorWorkspacePanel() {
  const navigate = useNavigate();
  const fullName = useUserSessionStore((s) => s.fullName);
  const logout = useUserSessionStore((s) => s.logout);
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);
  const isLocked = useAuditorWorkspaceStore((s) => s.isLocked);
  const isPanelCollapsed = useAuditorWorkspaceStore((s) => s.isPanelCollapsed);
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const setActiveProfile = useAuditorWorkspaceStore((s) => s.setActiveProfile);
  const setProfileSummary = useAuditorWorkspaceStore((s) => s.setProfileSummary);
  const setLocked = useAuditorWorkspaceStore((s) => s.setLocked);
  const setPanelCollapsed = useAuditorWorkspaceStore((s) => s.setPanelCollapsed);
  const clearProfile = useAuditorWorkspaceStore((s) => s.clearProfile);

  const [hoverOpen, setHoverOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const profilesQuery = useQuery({
    queryKey: ["profiles", "auditor-workspace"],
    queryFn: () => listProfiles({ page: 1, page_size: 100 }),
  });

  const profiles = profilesQuery.data?.items ?? [];
  const filteredProfiles = useMemo(
    () => profiles.filter((p) => profileMatchesQuery(p, searchQuery)),
    [profiles, searchQuery],
  );

  const showExpanded = !isPanelCollapsed || hoverOpen;
  const flyout = isPanelCollapsed && hoverOpen;
  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  useEffect(() => {
    if (!activeProfileId || profileSummary?.id === activeProfileId) return;
    const match = profiles.find((p) => p.id === activeProfileId);
    if (match) {
      setProfileSummary(profileToAuditorSummary(match));
    }
  }, [activeProfileId, profileSummary?.id, profiles, setProfileSummary]);

  function handleSelect(id: string): void {
    if (isLocked) return;
    const match = profiles.find((p) => p.id === id);
    setActiveProfile(id, match ? profileToAuditorSummary(match) : null);
  }

  function handleLockToggle(): void {
    if (!activeProfileId) return;
    const nextLocked = !isLocked;
    setLocked(nextLocked);
    if (nextLocked) {
      setPanelCollapsed(true);
      setHoverOpen(false);
    }
  }

  function handleSignOut(): void {
    logout();
    navigate("/login", { replace: true });
  }

  const panelBody = (
    <>
      <div className="shrink-0 border-b px-4 py-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <UserRound className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
            <div>
              <div className="text-sm font-semibold">Active taxpayer</div>
              <div className="text-xs text-muted-foreground">
                Locked selection applies across all modules
              </div>
            </div>
          </div>
          {activeProfileId ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              aria-label="Collapse taxpayer panel"
              title="Collapse panel"
              onClick={() => {
                setPanelCollapsed(true);
                setHoverOpen(false);
              }}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-4 py-3">
        <div className="shrink-0 space-y-1.5">
          <Label htmlFor="auditor-profile-search">Search taxpayers</Label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="auditor-profile-search"
              type="search"
              placeholder="Name, occupation, TIN, txn id…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
              disabled={isLocked}
            />
          </div>
        </div>

        <div
          className="min-h-0 flex-1 overflow-y-auto rounded-md border bg-background"
          role="listbox"
          aria-label="Taxpayer profiles"
        >
          {profilesQuery.isLoading ? (
            <p className="p-3 text-xs text-muted-foreground">Loading profiles…</p>
          ) : filteredProfiles.length === 0 ? (
            <p className="p-3 text-xs text-muted-foreground">
              {searchQuery.trim() ? "No profiles match your search." : "No profiles found."}
            </p>
          ) : (
            <ul className="divide-y">
              {filteredProfiles.map((profile) => {
                const isSelected = profile.id === activeProfileId;
                return (
                  <li key={profile.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      disabled={isLocked && !isSelected}
                      onClick={() => handleSelect(profile.id)}
                      className={cn(
                        "flex w-full flex-col gap-0.5 px-3 py-2.5 text-left text-xs transition-colors",
                        "hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
                        isSelected && "bg-accent text-accent-foreground",
                        isLocked && !isSelected && "cursor-not-allowed opacity-50",
                      )}
                    >
                      <span className="font-medium text-foreground">{profile.full_name}</span>
                      <span className="text-muted-foreground">{profile.occupation}</span>
                      <span className="text-[10px] text-muted-foreground">
                        TRP YA {profile.tax_year}
                        {profile.transaction_taxpayer_id
                          ? ` · ${profile.transaction_taxpayer_id}`
                          : ""}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="shrink-0 space-y-3">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={isLocked ? "default" : "outline"}
              size="sm"
              className="flex-1"
              onClick={handleLockToggle}
              disabled={!activeProfileId}
            >
              {isLocked ? (
                <>
                  <Lock className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                  Locked
                </>
              ) : (
                <>
                  <LockOpen className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                  Lock in
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => clearProfile()}
              disabled={!activeProfileId || isLocked}
            >
              Clear
            </Button>
          </div>

          {activeProfileId && profileSummary ? (
            <div className="rounded-md border bg-muted/30 p-3 text-xs leading-relaxed">
              <p className="font-medium text-foreground">{profileSummary.fullName}</p>
              <p className="text-muted-foreground">{profileSummary.occupation}</p>
              {profileSummary.tin ? (
                <p className="text-muted-foreground">TIN {profileSummary.tin}</p>
              ) : null}
              <p className="mt-2 text-muted-foreground">TRP YA {profileSummary.taxYear}</p>
              {activeProfile?.transaction_taxpayer_id ? (
                <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                  txn id: {activeProfile.transaction_taxpayer_id}
                </p>
              ) : null}
              <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                {activeProfileId.slice(0, 8)}…
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Select a taxpayer from the list to pre-fill recommendations, transaction
              classification, and optimization income.
            </p>
          )}
        </div>
      </div>

      <div className="shrink-0 border-t px-4 py-3">
        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="truncate">{fullName ?? "Auditor"}</span>
        </div>
        <Button type="button" variant="outline" size="sm" className="w-full" onClick={handleSignOut}>
          <LogOut className="mr-2 h-3.5 w-3.5" aria-hidden />
          Sign out
        </Button>
      </div>
    </>
  );

  return (
    <>
      {/* Collapsed rail — only when collapsed and not hover-flyout */}
      {isPanelCollapsed && !hoverOpen ? (
        <div
          className={cn(
            "hidden h-full w-11 shrink-0 flex-col border-l bg-card lg:flex",
          )}
        >
          <button
            type="button"
            className={cn(
              "flex min-h-0 flex-1 flex-col items-center gap-2 py-5 transition-colors",
              "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
            aria-label={
              profileSummary
                ? `Expand taxpayer panel — ${profileSummary.fullName}${isLocked ? ", locked" : ""}`
                : "Expand active taxpayer panel"
            }
            title="Hover or click to expand"
            onMouseEnter={() => setHoverOpen(true)}
            onFocus={() => setHoverOpen(true)}
            onClick={() => {
              setPanelCollapsed(false);
              setHoverOpen(false);
            }}
          >
            <UserRound className="h-5 w-5 text-muted-foreground" aria-hidden />
            {isLocked ? <Lock className="h-3.5 w-3.5 text-primary" aria-hidden /> : null}
            {profileSummary ? (
              <span
                className="max-h-[40vh] truncate text-[10px] font-medium text-muted-foreground [writing-mode:vertical-rl] rotate-180"
                aria-hidden
              >
                {profileSummary.fullName}
              </span>
            ) : null}
          </button>
          <button
            type="button"
            className="mb-3 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Sign out"
            title="Sign out"
            onClick={handleSignOut}
          >
            <LogOut className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ) : null}

      {/* Docked panel */}
      {!isPanelCollapsed && showExpanded ? (
        <aside className="hidden h-full w-72 shrink-0 flex flex-col overflow-hidden border-l bg-card lg:flex">
          {panelBody}
        </aside>
      ) : null}

      {/* Hover flyout — fixed overlay, opaque, full viewport height */}
      {flyout ? (
        <aside
          className="fixed inset-y-0 right-0 z-50 flex w-72 flex-col border-l bg-card shadow-2xl"
          onMouseEnter={() => setHoverOpen(true)}
          onMouseLeave={() => setHoverOpen(false)}
        >
          {panelBody}
        </aside>
      ) : null}
    </>
  );
}
