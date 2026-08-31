import { Link } from "react-router-dom";
import { AlertCircle, UserRound } from "lucide-react";

import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

type Props = {
  moduleLabel: string;
};

/** Inline reminder when a module needs an active profile from the right panel. */
export function ActiveProfileBanner({ moduleLabel }: Props) {
  const activeProfileId = useAuditorWorkspaceStore((s) => s.activeProfileId);
  const profileSummary = useAuditorWorkspaceStore((s) => s.profileSummary);
  const isLocked = useAuditorWorkspaceStore((s) => s.isLocked);

  if (!activeProfileId) {
    return (
      <div
        className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950"
        role="status"
      >
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <p>
          No taxpayer selected for <strong>{moduleLabel}</strong>. Use the{" "}
          <strong>Active taxpayer</strong> panel (right on desktop, top bar on mobile) to select
          and lock a profile.
        </p>
      </div>
    );
  }

  const profileHref = `/profile?selected=${encodeURIComponent(activeProfileId)}`;

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm"
      role="status"
    >
      <div className="flex items-center gap-2">
        <UserRound className="h-4 w-4 text-muted-foreground" aria-hidden />
        <span>
          {moduleLabel} for{" "}
          <strong>{profileSummary?.fullName ?? "selected profile"}</strong>
          {profileSummary?.tin ? ` · TIN ${profileSummary.tin}` : ""}
          {isLocked ? " (locked)" : ""}
        </span>
      </div>
      <Link
        to={profileHref}
        className="text-xs font-medium text-primary underline-offset-2 hover:underline"
      >
        Open financial profile
      </Link>
    </div>
  );
}
