import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { getReliefInterviewApprovedAll } from "../../api";
import { formatLkr } from "../../format-lkr";
import {
  findByGroup,
  compareRowStatus,
  type ApprovedEntry,
} from "./catalog-types";
import {
  isListedPublicDoneeGroup,
  isListedPublicDoneesCompareType,
  LISTED_PUBLIC_DONEES_COMPARE_LABEL,
  LISTED_PUBLIC_DONEES_COMPARE_TYPE,
} from "./listed-donees";
import { isRentalIncomeReliefGroup } from "./rental-income-relief";
import { isBankMergerQpGroup } from "./bank-merger-qp";
import { isEntityCharityDonationGroup } from "./entity-charity-donation";
import { isResidentReliefsDeductionGroup } from "./resident-reliefs-notice";
import { isQualifyingPaymentsDeductionGroup } from "./qualifying-payments-notice";
import { isNonResidentCitizenReliefGroup } from "./non-resident-citizen-notice";
import { useReliefInterview } from "./session";
import { RELIEF_INTERVIEW_YAS, yaDisplay } from "./types";

type YearBucket = {
  assessment_year: string;
  entries: ApprovedEntry[];
};

function coerceEntries(raw: unknown[]): ApprovedEntry[] {
  return raw.filter((e): e is ApprovedEntry => {
    const row = e as Partial<ApprovedEntry>;
    return Boolean(row.entry_id && row.compare_group_id);
  }) as ApprovedEntry[];
}

function formatCatalogCap(entry: ApprovedEntry): string {
  const raw = entry.cap_amount;
  if (raw == null || raw === "") return "—";
  if (entry.unit === "percent" || isRentalIncomeReliefGroup(entry.compare_group_id)) {
    return `${String(raw).replace(/%$/, "")}%`;
  }
  if (entry.unit === "text") return String(raw);
  return formatLkr(String(raw));
}

function findCompareEntry(
  entries: ApprovedEntry[],
  groupId: string,
): ApprovedEntry | undefined {
  if (groupId === LISTED_PUBLIC_DONEES_COMPARE_TYPE) {
    return entries.find((e) => isListedPublicDoneeGroup(e.compare_group_id));
  }
  return findByGroup(entries, groupId);
}

export function ReliefInterviewComparePage() {
  const navigate = useNavigate();
  const { session, setSelectedCompareGroupId } = useReliefInterview();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [years, setYears] = useState<YearBucket[]>([]);
  const [groupId, setGroupId] = useState<string>(
    session.selectedCompareGroupId ?? "",
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getReliefInterviewApprovedAll()
      .then((data) => {
        if (cancelled) return;
        const buckets: YearBucket[] = data.years.map((y) => ({
          assessment_year: y.assessment_year,
          entries: coerceEntries(y.entries ?? []),
        }));
        setYears(buckets);
        const other: string[] = [];
        const groups = new Set<string>();
        for (const b of buckets) {
          for (const e of b.entries) {
            groups.add(e.compare_group_id);
            if (
              !isListedPublicDoneeGroup(e.compare_group_id) &&
              !isBankMergerQpGroup(e.compare_group_id) &&
              !isEntityCharityDonationGroup(e.compare_group_id) &&
              !isResidentReliefsDeductionGroup(e.compare_group_id) &&
              !isQualifyingPaymentsDeductionGroup(e.compare_group_id) &&
              !isNonResidentCitizenReliefGroup(e.compare_group_id)
            ) {
              other.push(e.compare_group_id);
            }
          }
        }
        const hasDonees = buckets.some((b) =>
          b.entries.some((e) => isListedPublicDoneeGroup(e.compare_group_id)),
        );
        if (isListedPublicDoneesCompareType(groupId) && hasDonees) {
          setGroupId(LISTED_PUBLIC_DONEES_COMPARE_TYPE);
          setSelectedCompareGroupId(LISTED_PUBLIC_DONEES_COMPARE_TYPE);
        } else {
          const firstOther = other[0];
          if (
            firstOther &&
            (!groupId || !groups.has(groupId) || isListedPublicDoneeGroup(groupId))
          ) {
            setGroupId(firstOther);
            setSelectedCompareGroupId(firstOther);
          }
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load catalogs.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once on mount
  }, []);

  const groupOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const b of years) {
      for (const e of b.entries) {
        if (isListedPublicDoneeGroup(e.compare_group_id)) continue;
        if (isBankMergerQpGroup(e.compare_group_id)) continue;
        if (isEntityCharityDonationGroup(e.compare_group_id)) continue;
        if (isResidentReliefsDeductionGroup(e.compare_group_id)) continue;
        if (isQualifyingPaymentsDeductionGroup(e.compare_group_id)) continue;
        if (isNonResidentCitizenReliefGroup(e.compare_group_id)) continue;
        if (!map.has(e.compare_group_id)) {
          map.set(e.compare_group_id, e.display_name || e.compare_group_id);
        }
      }
    }
    const sorted = [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
    const hasDonees = years.some((b) =>
      b.entries.some((e) => isListedPublicDoneeGroup(e.compare_group_id)),
    );
    if (hasDonees) {
      sorted.push([
        LISTED_PUBLIC_DONEES_COMPARE_TYPE,
        LISTED_PUBLIC_DONEES_COMPARE_LABEL,
      ]);
    }
    return sorted;
  }, [years]);

  const rows = useMemo(() => {
    if (!groupId) return [];
    return RELIEF_INTERVIEW_YAS.map((ya) => {
      const bucket = years.find((y) => y.assessment_year === ya);
      const entry = bucket
        ? findCompareEntry(bucket.entries, groupId)
        : undefined;
      return { ya, entry };
    });
  }, [years, groupId]);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading multi-year catalogs…
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          Pick one relief group and see its catalog value for every supported
          assessment year (YA 2018/19–2025/26). Interview as-of and compare
          years are highlighted when a Relief Interview session exists.
        </p>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {groupOptions.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No compare groups yet — approved catalogs are empty until Phase 5
          promotes extractor rows. The table below still lists every YA so the
          flow is ready.
        </p>
      ) : (
        <div className="max-w-md space-y-2">
          <Label htmlFor="ri-compare-group">Relief</Label>
          <Select
            id="ri-compare-group"
            value={groupId}
            onChange={(e) => {
              setGroupId(e.target.value);
              setSelectedCompareGroupId(e.target.value || null);
            }}
          >
            {groupOptions.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </Select>
        </div>
      )}

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead className="border-b bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Assessment year</th>
              <th className="px-3 py-2 font-medium">Cap / value</th>
              <th className="px-3 py-2 font-medium">Section</th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ ya, entry }) => (
              <tr
                key={ya}
                className={
                  ya === session.assessmentYear
                    ? "bg-primary/5"
                    : ya === session.compareYear
                      ? "bg-muted/30"
                      : undefined
                }
              >
                <td className="px-3 py-2 font-medium">
                  YA {yaDisplay(ya)}
                  {ya === session.assessmentYear ? (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      (as of)
                    </span>
                  ) : null}
                  {ya === session.compareYear ? (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      (compare)
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  {(() => {
                    const status = compareRowStatus(entry, ya);
                    if (status === "Removed") {
                      return (
                        <span className="text-destructive">—</span>
                      );
                    }
                    if (entry?.cap_amount != null && entry.cap_amount !== "") {
                      return formatCatalogCap(entry);
                    }
                    return entry ? "—" : "Not in catalog";
                  })()}
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {(() => {
                    const status = compareRowStatus(entry, ya);
                    if (status === "Removed") return "—";
                    return entry?.section_ref ?? "—";
                  })()}
                </td>
                <td className="px-3 py-2 text-xs">
                  {(() => {
                    const status = compareRowStatus(entry, ya);
                    if (status === "Removed") {
                      return (
                        <span className="font-medium text-destructive">
                          Removed
                        </span>
                      );
                    }
                    if (status === "Last known figure — not confirmed for this year") {
                      return (
                        <span className="text-amber-800 dark:text-amber-200">
                          {status}
                        </span>
                      );
                    }
                    return status;
                  })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => void navigate("/adaptive-tax/relief-interview/reliefs")}
        >
          Back to interview
        </Button>
        <Button
          type="button"
          onClick={() => void navigate("/adaptive-tax/relief-interview/result")}
        >
          Continue to result
        </Button>
      </div>
    </div>
  );
}
