import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Layers } from "lucide-react";
import { useState } from "react";

import { formatLkr } from "@/features/personalized-recommendation/utils/format-lkr";
import {
  getUserPortalActivityGroups,
  type UserPortalActivityGroup,
} from "@/pages/user-view/api/user-transactions";

interface UserActivityGroupsPanelProps {
  profileId: string;
  taxYear?: string | null;
}

export function UserActivityGroupsPanel({ profileId, taxYear }: UserActivityGroupsPanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const groupsQuery = useQuery({
    queryKey: ["user-activity-groups", profileId, taxYear],
    queryFn: () => getUserPortalActivityGroups(profileId, taxYear),
    enabled: !!profileId,
  });

  const groups = groupsQuery.data?.groups ?? [];

  if (groupsQuery.isLoading) {
    return <p className="px-5 py-8 text-sm text-[var(--uv-text-muted)]">Loading income groups…</p>;
  }

  if (!groups.length) {
    return (
      <p className="px-5 py-10 text-center text-sm text-[var(--uv-text-muted)]">
        No released credit activity grouped yet. Your adviser will publish classified statements
        first.
      </p>
    );
  }

  return (
    <div className="divide-y divide-[var(--uv-border)]/70">
      {groups.map((group: UserPortalActivityGroup) => {
        const isOpen = expanded[group.class_key] ?? false;
        return (
          <div key={group.class_key} className="px-5 py-4">
            <button
              type="button"
              onClick={() =>
                setExpanded((current) => ({ ...current, [group.class_key]: !isOpen }))
              }
              className="flex w-full items-start gap-3 text-left"
            >
              <span className="mt-0.5 text-[var(--uv-text-muted)]">
                {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </span>
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]">
                <Layers className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-[var(--uv-text)]">{group.label}</span>
                  <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-[var(--uv-text-muted)]">
                    {group.transaction_count} txn
                  </span>
                  {group.review_count > 0 ? (
                    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">
                      {group.review_count} review
                    </span>
                  ) : null}
                </span>
                <span className="mt-1 block text-sm text-[var(--uv-text-muted)]">
                  Total {formatLkr(group.total_amount_lkr)} · Taxable {formatLkr(group.taxable_amount_lkr)}
                </span>
              </span>
            </button>
            {isOpen ? (
              <p className="ml-14 mt-2 text-xs text-[var(--uv-text-muted)]">
                Grouped from adviser-approved credits in this assessment year.
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
