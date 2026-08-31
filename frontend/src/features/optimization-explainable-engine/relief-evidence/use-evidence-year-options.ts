import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { assessmentYearSelectOptions } from "@/features/tax-return-profile/assessment-years";
import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";

import { getYears } from "../api";
import { yaDisplay } from "../format-lkr";

export type EvidenceYearOption = { value: string; label: string };

function fallbackYearOptions(): EvidenceYearOption[] {
  return assessmentYearSelectOptions()
    .map((opt) => {
      const orm = normalizeTaxYearToOrm(opt.value);
      if (!orm) return null;
      return { value: orm, label: `YA ${yaDisplay(orm)}` };
    })
    .filter((opt): opt is EvidenceYearOption => opt != null);
}

/** Years from OE Engine, plus recent YA fallbacks if the catalog is offline. */
export function useEvidenceYearOptions(preferredYear?: string | null): EvidenceYearOption[] {
  const yearsQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "years", "evidence"],
    queryFn: getYears,
    retry: false,
  });

  return useMemo(() => {
    const fromEngine = (yearsQuery.data?.assessment_years ?? []).filter(Boolean);
    const merged = new Set<string>([...fromEngine, ...fallbackYearOptions().map((o) => o.value)]);
    if (preferredYear) merged.add(preferredYear);
    return [...merged]
      .sort((a, b) => b.localeCompare(a))
      .map((ya) => ({ value: ya, label: `YA ${yaDisplay(ya)}` }));
  }, [preferredYear, yearsQuery.data?.assessment_years]);
}
