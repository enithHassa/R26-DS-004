import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Layers } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  summarizeActivity,
  type ActivitySummaryGroup,
  type ActivitySummaryMember,
  type ExtractedTransactionItem,
} from "@/features/transaction-semantic/api";
import { formatLkr } from "@/features/transaction-semantic/format-lkr";

function formatMoney(value: string | null): string {
  if (value === null) return "-";
  return formatLkr(value);
}

export interface ActivitySummaryPanelProps {
  transactions: ExtractedTransactionItem[];
  /** documents = extract QA; tax = override / review aid */
  variant?: "documents" | "tax";
  /** Row ids still in review after classification (tax variant). */
  reviewRowIds?: Iterable<string>;
  defaultScope?: "all" | "review";
}

function filterGroupsToRowIds(
  groups: ActivitySummaryGroup[],
  rowIds: Set<string>,
): ActivitySummaryGroup[] {
  const out: ActivitySummaryGroup[] = [];
  for (const group of groups) {
    const members = group.members.filter((m) => m.row_id != null && rowIds.has(m.row_id));
    if (members.length === 0) continue;
    const total = members.reduce((sum, m) => sum + Number(m.amount_lkr), 0);
    out.push({
      ...group,
      count: members.length,
      total_lkr: String(total),
      members,
    });
  }
  return out.sort((a, b) => Math.abs(Number(b.total_lkr)) - Math.abs(Number(a.total_lkr)));
}

export function ActivitySummaryPanel({
  transactions,
  variant = "documents",
  reviewRowIds,
  defaultScope = "all",
}: ActivitySummaryPanelProps) {
  const reviewSet = useMemo(() => new Set(reviewRowIds ?? []), [reviewRowIds]);
  const hasReviewScope = reviewSet.size > 0;

  const [groups, setGroups] = useState<ActivitySummaryGroup[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [directionFilter, setDirectionFilter] = useState<"all" | "CR" | "DR">(
    variant === "tax" ? "CR" : "all",
  );
  const [scope, setScope] = useState<"all" | "review">(
    hasReviewScope && defaultScope === "review" ? "review" : "all",
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (hasReviewScope && defaultScope === "review") {
      setScope("review");
    } else {
      setScope("all");
    }
  }, [hasReviewScope, defaultScope, transactions]);

  useEffect(() => {
    if (transactions.length === 0) {
      setGroups([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void summarizeActivity({
      items: transactions.map((tx) => ({
        row_id: tx.id,
        raw_desc: tx.description,
        amount_lkr: tx.amount_lkr,
        tx_date: tx.tx_date,
        direction: tx.direction,
      })),
    })
      .then((resp) => {
        if (cancelled) return;
        setGroups(resp.groups);
        setExpanded({});
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Activity summary failed.");
        setGroups([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [transactions]);

  const scopedGroups = useMemo(() => {
    if (scope === "review" && hasReviewScope) {
      return filterGroupsToRowIds(groups, reviewSet);
    }
    return groups;
  }, [groups, scope, hasReviewScope, reviewSet]);

  const visible = scopedGroups.filter(
    (g) => directionFilter === "all" || g.direction === directionFilter,
  );

  function toggle(key: string): void {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const title =
    variant === "tax" ? "Activity groups (for overrides)" : "Summarized activity log";
  const description =
    variant === "tax"
      ? "Same intent/merchant grouping as Documents. Default focus is review / unproven credits so you can clear INVCEFT or P2P batches with auditor override — not a separate tax engine."
      : "Similar movements grouped by bank intent and merchant family (not by amount). Expand a group to review each row. Tax decisions live on Tax classification.";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers className="h-4 w-4" /> {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {transactions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {variant === "tax"
              ? "Classify a document to see activity groups."
              : "Load or preview a document to see groups."}
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {hasReviewScope ? (
                <>
                  <Button
                    size="sm"
                    variant={scope === "review" ? "default" : "outline"}
                    onClick={() => setScope("review")}
                  >
                    Review / unproven
                  </Button>
                  <Button
                    size="sm"
                    variant={scope === "all" ? "default" : "outline"}
                    onClick={() => setScope("all")}
                  >
                    All activity
                  </Button>
                </>
              ) : null}
              {(["all", "CR", "DR"] as const).map((key) => (
                <Button
                  key={key}
                  size="sm"
                  variant={directionFilter === key ? "default" : "outline"}
                  onClick={() => setDirectionFilter(key)}
                >
                  {key === "all" ? "All dirs" : key === "CR" ? "Credits" : "Debits"}
                </Button>
              ))}
            </div>
            {isLoading ? <p className="text-sm text-muted-foreground">Building groups…</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            {!isLoading && !error && visible.length === 0 ? (
              <p className="text-sm text-muted-foreground">No groups for this filter.</p>
            ) : null}
            <div className="space-y-2">
              {visible.map((group) => {
                const open = Boolean(expanded[group.group_key]);
                return (
                  <ActivityGroupRow
                    key={group.group_key}
                    group={group}
                    open={open}
                    onToggle={() => toggle(group.group_key)}
                    highlightReview={scope === "review"}
                  />
                );
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ActivityGroupRow({
  group,
  open,
  onToggle,
  highlightReview,
}: {
  group: ActivitySummaryGroup;
  open: boolean;
  onToggle: () => void;
  highlightReview: boolean;
}) {
  return (
    <div
      className={`rounded-xl border bg-white ${highlightReview ? "border-amber-200/80" : ""}`}
    >
      <button
        type="button"
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-slate-50/80"
        onClick={onToggle}
      >
        <span className="mt-0.5 text-muted-foreground">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-foreground">{group.label}</p>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
              {group.direction}
            </span>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-muted-foreground">
              {group.count} row{group.count === 1 ? "" : "s"}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{group.hint}</p>
        </div>
        <p className="shrink-0 text-sm font-semibold tabular-nums text-foreground">
          {formatMoney(group.total_lkr)}
        </p>
      </button>
      {open ? (
        <div className="border-t px-4 py-3">
          <MemberTable members={group.members} groupKey={group.group_key} />
        </div>
      ) : null}
    </div>
  );
}

function MemberTable({
  members,
  groupKey,
}: {
  members: ActivitySummaryMember[];
  groupKey: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="p-2 font-medium">Date</th>
            <th className="p-2 font-medium">Description</th>
            <th className="p-2 font-medium">Dir</th>
            <th className="p-2 font-medium">Amount</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m, idx) => (
            <tr
              key={`${groupKey}-${m.row_id ?? idx}`}
              className="border-b align-top last:border-0"
            >
              <td className="p-2 whitespace-nowrap">{m.tx_date ?? "-"}</td>
              <td className="p-2 max-w-[420px] whitespace-normal">{m.description}</td>
              <td className="p-2">{m.direction}</td>
              <td className="p-2 tabular-nums">{formatMoney(m.amount_lkr)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
