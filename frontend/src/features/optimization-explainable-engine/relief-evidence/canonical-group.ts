import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";

/** Map extract / fallback ids onto the year-view compare_group_id. */
const GROUP_ALIASES: Record<string, string> = {
  solar: "solar_panel_relief",
  solar_panel: "solar_panel_relief",
  solar_panel_expenditure: "solar_panel_relief",
  rent_relief: "rental_income_relief",
  rental_relief: "rental_income_relief",
  charitable_donation: "donation_to_charitable_institution",
  donations: "donation_to_charitable_institution",
  donation_to_approved_charitable_institution: "donation_to_charitable_institution",
  approved_charitable_institution: "donation_to_charitable_institution",
  donation_to_government: "donation_to_government_or_approved_fund",
  donation_to_approved_fund: "donation_to_government_or_approved_fund",
  samurdhi_shop_contribution: "qp_samurdhi_shop",
  contribution_to_samurdhi_shop: "qp_samurdhi_shop",
  contribution_shop_samurdhi: "qp_samurdhi_shop",
  film_production_expenditure: "qp_film_production",
  expenditure_on_film_production: "qp_film_production",
  qp_film: "qp_film_production",
  cinema_upgrade_expenditure: "qp_cinema_upgrading",
  expenditure_on_upgrading_a_cinema: "qp_cinema_upgrading",
  qp_cinema_upgrade: "qp_cinema_upgrading",
  expenditure_on_construction_and_equipping_of_a_new_cinema: "qp_cinema_construction",
  qp_cinema_new: "qp_cinema_construction",
};

export function slugEvidenceKey(value: string | null | undefined): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_");
}

export function canonicalEvidenceGroupId(groupId: string | null | undefined): string {
  const key = slugEvidenceKey(groupId);
  return GROUP_ALIASES[key] ?? key;
}

export function evidenceYearKeys(assessmentYear: string | null | undefined): string[] {
  const raw = String(assessmentYear ?? "").trim();
  if (!raw) return [];
  const orm = normalizeTaxYearToOrm(raw) ?? raw;
  return [...new Set([orm, raw])];
}

export function evidenceGroupsMatch(
  storedKey: string,
  wantedGroupId: string,
  displayName?: string | null,
): boolean {
  const stored = canonicalEvidenceGroupId(storedKey);
  const wanted = canonicalEvidenceGroupId(wantedGroupId);
  if (!stored || !wanted) return false;
  if (stored === wanted) return true;
  const fromName = canonicalEvidenceGroupId(displayName);
  return Boolean(fromName) && stored === fromName && wanted === fromName;
}

export function canonicalEvidenceYear(assessmentYear: string): string {
  return normalizeTaxYearToOrm(assessmentYear) ?? assessmentYear.trim();
}
