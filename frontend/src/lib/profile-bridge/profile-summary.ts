import type { FinancialProfile } from "@/features/personalized-recommendation/types";
import type { AuditorProfileSummary } from "@/store/auditor-workspace-store";

function readSection1(profile: FinancialProfile): Record<string, unknown> | undefined {
  const detail = profile.tax_return_detail;
  if (!detail || typeof detail !== "object") return undefined;
  const section1 = (detail as Record<string, unknown>).section1;
  return section1 && typeof section1 === "object"
    ? (section1 as Record<string, unknown>)
    : undefined;
}

/** Build auditor panel summary fields from a Comp 3 profile. */
export function profileToAuditorSummary(profile: FinancialProfile): AuditorProfileSummary {
  const section1 = readSection1(profile);
  const tin =
    typeof section1?.tin === "string"
      ? section1.tin
      : typeof section1?.nic === "string"
        ? section1.nic
        : "";

  return {
    id: profile.id,
    fullName: profile.full_name,
    occupation: profile.occupation,
    taxYear: profile.tax_year,
    tin,
  };
}
