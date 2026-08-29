import {
  getFinalizedTaxComputationSnapshot,
  getProfile,
  type TaxComputationSnapshotDetail,
} from "@/features/personalized-recommendation/api/profiles";
import type { FinancialProfile } from "@/features/personalized-recommendation/types";
import { profileToAuditorSummary } from "@/lib/profile-bridge/profile-summary";
import { sessionFromSnapshot } from "@/lib/profile-bridge/oe-snapshot";
import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";
import { profileToInterviewIncome } from "@/lib/profile-bridge/tax-return-to-oe-income";
import { detailFromProfile } from "@/features/tax-return-profile/mappers";

import { getReliefs, getYears } from "../api";
import type { InterviewSession, ReliefAnswer, ReliefEntry } from "../types";
import { createEmptyTaxpayerSession } from "./empty-session";
import { profileHasUsableIncome, suggestClaimsFromProfile } from "./suggest-claims";

export type TaxpayerOeScenario = {
  profile: FinancialProfile;
  assessmentYear: string;
  availableYears: string[];
  session: InterviewSession;
  reliefEntries: ReliefEntry[];
  suggestedClaims: ReliefAnswer[];
  finalized: TaxComputationSnapshotDetail | null;
  hasProfileIncome: boolean;
  fullName: string;
  tin: string;
};

export async function loadTaxpayerScenario(
  profileId: string,
  preferredYear?: string | null,
): Promise<TaxpayerOeScenario> {
  const [profile, yearsRes] = await Promise.all([getProfile(profileId), getYears()]);
  const availableYears = yearsRes.assessment_years?.length
    ? yearsRes.assessment_years
    : (yearsRes.years ?? []).map((y) => y.assessment_year);

  const summary = profileToAuditorSummary(profile);
  const detail = detailFromProfile(profile);
  const profileYa =
    normalizeTaxYearToOrm(detail.section1.taxYear) ||
    normalizeTaxYearToOrm(profile.tax_year) ||
    null;

  let assessmentYear =
    (preferredYear && availableYears.includes(preferredYear) ? preferredYear : null) ||
    (profileYa && availableYears.includes(profileYa) ? profileYa : null) ||
    availableYears[availableYears.length - 1] ||
    profileYa ||
    "2025_26";

  const finalized = await getFinalizedTaxComputationSnapshot(profileId, assessmentYear);

  let session: InterviewSession;
  let suggestedClaims: ReliefAnswer[] = [];
  let reliefEntries: ReliefEntry[] = [];

  try {
    const reliefs = await getReliefs(assessmentYear);
    reliefEntries = reliefs.entries ?? [];
  } catch {
    reliefEntries = [];
  }

  if (finalized) {
    session = sessionFromSnapshot(finalized);
    assessmentYear = session.assessmentYear;
    suggestedClaims = session.reliefAnswers;
  } else {
    const mapped = profileToInterviewIncome(profile);
    const ya = availableYears.includes(mapped.assessmentYear)
      ? mapped.assessmentYear
      : assessmentYear;
    assessmentYear = ya;
    session = {
      ...createEmptyTaxpayerSession(ya),
      income: mapped.income,
      assessmentYear: ya,
    };
    suggestedClaims = suggestClaimsFromProfile(
      profile,
      session.income,
      reliefEntries,
      ya,
    );
    session = { ...session, reliefAnswers: suggestedClaims };
  }

  return {
    profile,
    assessmentYear,
    availableYears: availableYears.length ? availableYears : [assessmentYear],
    session,
    reliefEntries,
    suggestedClaims,
    finalized,
    hasProfileIncome: profileHasUsableIncome(detail),
    fullName: summary.fullName || profile.full_name || "",
    tin: summary.tin || "",
  };
}
