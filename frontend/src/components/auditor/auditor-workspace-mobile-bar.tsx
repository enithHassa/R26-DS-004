import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Lock, LockOpen, LogOut, UserRound } from "lucide-react";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { listProfiles } from "@/features/personalized-recommendation/api/profiles";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { profileToAuditorSummary } from "@/lib/profile-bridge/profile-summary";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

/** Compact profile picker for viewports where the right panel is hidden. */
export function AuditorWorkspaceMobileBar() {
  const navigate = useNavigate();
  const logout = useUserSessionStore((s) => s.logout);
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const isLocked = useAuditorWorkspaceStore((s) => s.isLocked);
  const setActiveProfile = useAuditorWorkspaceStore((s) => s.setActiveProfile);
  const setLocked = useAuditorWorkspaceStore((s) => s.setLocked);
  const clearProfile = useAuditorWorkspaceStore((s) => s.clearProfile);

  const profilesQuery = useQuery({
    queryKey: ["profiles", "auditor-workspace"],
    queryFn: () => listProfiles({ page: 1, page_size: 100 }),
  });

  const profiles = profilesQuery.data?.items ?? [];

  function handleSelect(id: string): void {
    if (isLocked) return;
    if (!id) {
      clearProfile();
      return;
    }
    const match = profiles.find((p) => p.id === id);
    setActiveProfile(id, match ? profileToAuditorSummary(match) : null);
  }

  function handleSignOut(): void {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="mb-6 rounded-md border bg-card/60 p-3 lg:hidden">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <UserRound className="h-4 w-4 text-muted-foreground" aria-hidden />
          Active taxpayer
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={handleSignOut}>
          <LogOut className="mr-1 h-3.5 w-3.5" aria-hidden />
          Sign out
        </Button>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1 space-y-1">
          <Label htmlFor="auditor-profile-select-mobile" className="text-xs">
            Profile
          </Label>
          <Select
            id="auditor-profile-select-mobile"
            value={activeProfileId ?? ""}
            onChange={(e) => handleSelect(e.target.value)}
            disabled={profilesQuery.isLoading || isLocked}
          >
            <option value="">
              {profilesQuery.isLoading ? "Loading…" : "Select a profile"}
            </option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={isLocked ? "default" : "outline"}
            size="sm"
            onClick={() => setLocked(!isLocked)}
            disabled={!activeProfileId}
          >
            {isLocked ? (
              <>
                <Lock className="mr-1 h-3.5 w-3.5" aria-hidden />
                Locked
              </>
            ) : (
              <>
                <LockOpen className="mr-1 h-3.5 w-3.5" aria-hidden />
                Lock
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
      </div>
      {profileSummary ? (
        <p className="mt-2 text-xs text-muted-foreground">
          {profileSummary.fullName}
          {profileSummary.tin ? ` · TIN ${profileSummary.tin}` : ""}
        </p>
      ) : null}
    </div>
  );
}
