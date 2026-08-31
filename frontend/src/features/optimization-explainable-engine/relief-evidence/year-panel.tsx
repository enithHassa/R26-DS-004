import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getReliefs } from "../api";
import { reliefListedForInterview } from "../compare-types";
import { yaDisplay } from "../format-lkr";
import { sortReliefsForInterview } from "../sort-reliefs";
import { FALLBACK_CLAIMABLE_RELIEFS, reliefRequiresReceipt } from "./needs-receipt";
import { ReliefEvidenceSlot } from "./slot";
import { countReliefEvidence } from "./store";
import { useEvidenceRevision } from "./use-relief-evidence";
import type { EvidenceYearOption } from "./use-evidence-year-options";
import type { ReliefEntry } from "../types";

type CatalogRow = {
  compare_group_id: string;
  display_name: string;
  auto_applied?: boolean;
  input_kind?: string;
};

function catalogRows(entries: ReliefEntry[], assessmentYear: string): CatalogRow[] {
  const listed = sortReliefsForInterview(
    entries.filter((entry) => reliefListedForInterview(entry, assessmentYear)),
  );
  return listed.map((entry) => ({
    compare_group_id: entry.compare_group_id,
    display_name: entry.display_name,
    auto_applied: entry.auto_applied,
    input_kind: entry.input_kind,
  }));
}

export function YearReliefEvidencePanel({
  profileId,
  assessmentYear,
  onYearChange,
  yearOptions,
}: {
  profileId: string;
  assessmentYear: string;
  onYearChange: (ya: string) => void;
  yearOptions: EvidenceYearOption[];
}) {
  const reliefsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "reliefs", "evidence", assessmentYear],
    queryFn: () => getReliefs(assessmentYear),
    enabled: Boolean(assessmentYear),
    retry: false,
  });

  const rows: CatalogRow[] = useMemo(() => {
    if (reliefsQuery.data?.entries?.length) {
      return catalogRows(reliefsQuery.data.entries, assessmentYear);
    }
    if (reliefsQuery.isError || reliefsQuery.data?.entries?.length === 0) {
      return FALLBACK_CLAIMABLE_RELIEFS.map((row) => ({ ...row, input_kind: "amount" }));
    }
    return [];
  }, [assessmentYear, reliefsQuery.data?.entries, reliefsQuery.isError]);

  const [openId, setOpenId] = useState<string | null>(null);
  useEvidenceRevision();

  return (
    <div className="trp-evidence-panel">
      <div className="trp-evidence-panel-head">
        <div>
          <p className="trp-evidence-kicker">Supporting documents by year</p>
          <p className="trp-evidence-copy">
            Reliefs change each year of assessment. Pick a year, then attach receipts for
            every claim except personal relief.
          </p>
        </div>
        <label className="trp-evidence-year">
          <span>Year of Assessment</span>
          <select
            value={assessmentYear}
            onChange={(event) => onYearChange(event.target.value)}
          >
            {yearOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {reliefsQuery.isLoading ? (
        <p className="trp-evidence-copy">Loading reliefs for {yaDisplay(assessmentYear)}…</p>
      ) : null}

      {reliefsQuery.isError ? (
        <p className="trp-evidence-copy">
          Could not reach the relief catalog (port 8009). You can still attach receipts to
          the common claim types below.
        </p>
      ) : null}

      <ul className="trp-evidence-list">
        {rows.map((row) => {
          const needs = reliefRequiresReceipt({
            compare_group_id: row.compare_group_id,
            display_name: row.display_name,
            auto_applied: row.auto_applied,
            input_kind: row.input_kind ?? "amount",
          });
          const count = countReliefEvidence(
            profileId,
            assessmentYear,
            row.compare_group_id,
            row.display_name,
          );
          const open = openId === row.compare_group_id;
          return (
            <li key={row.compare_group_id} className="trp-evidence-row">
              <button
                type="button"
                className="trp-evidence-row-btn"
                onClick={() =>
                  setOpenId(open ? null : row.compare_group_id)
                }
              >
                <span className="trp-evidence-row-name">{row.display_name}</span>
                {needs ? (
                  <span
                    className={
                      count > 0
                        ? "trp-evidence-badge trp-evidence-badge--ready"
                        : "trp-evidence-badge"
                    }
                  >
                    {count > 0 ? `${count} image${count === 1 ? "" : "s"} loaded` : "No image yet"}
                  </span>
                ) : (
                  <span className="trp-evidence-badge trp-evidence-badge--skip">
                    No receipt required
                  </span>
                )}
              </button>
              {open ? (
                <div className="trp-evidence-row-body">
                  <ReliefEvidenceSlot
                    profileId={profileId}
                    assessmentYear={assessmentYear}
                    compareGroupId={row.compare_group_id}
                    displayName={row.display_name}
                    autoApplied={row.auto_applied}
                    inputKind={row.input_kind}
                    mode="upload"
                  />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
