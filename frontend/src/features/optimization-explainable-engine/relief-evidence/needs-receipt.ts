import type { ReliefEntry } from "../types";

/** Personal / auto-applied statutory reliefs do not need a receipt upload. */
export function reliefRequiresReceipt(
  entry: Pick<ReliefEntry, "compare_group_id" | "display_name" | "auto_applied" | "input_kind">,
): boolean {
  if (entry.auto_applied) return false;
  const group = (entry.compare_group_id ?? "").toLowerCase().trim();
  const name = (entry.display_name ?? "").toLowerCase();
  if (group === "personal_relief" || name.includes("personal relief")) return false;
  if (entry.input_kind === "notice" && (group.includes("personal") || name.includes("personal"))) {
    return false;
  }
  return true;
}

export const FALLBACK_CLAIMABLE_RELIEFS: Array<{
  compare_group_id: string;
  display_name: string;
}> = [
  { compare_group_id: "solar_panel_relief", display_name: "Solar Panel Expenditure" },
  { compare_group_id: "rental_income_relief", display_name: "Rental income relief" },
  {
    compare_group_id: "donation_to_charitable_institution",
    display_name: "Donation to approved charitable institution",
  },
  {
    compare_group_id: "donation_to_government_or_approved_fund",
    display_name: "Donation to government or approved fund",
  },
  { compare_group_id: "life_insurance", display_name: "Life insurance premiums" },
  { compare_group_id: "qp_cinema_upgrading", display_name: "Expenditure on upgrading a cinema" },
  { compare_group_id: "qp_samurdhi_shop", display_name: "Samurdhi shop contribution" },
  { compare_group_id: "qp_film_production", display_name: "Expenditure on film production" },
  {
    compare_group_id: "qp_cinema_construction",
    display_name: "Expenditure on construction and equipping of a new cinema",
  },
];
