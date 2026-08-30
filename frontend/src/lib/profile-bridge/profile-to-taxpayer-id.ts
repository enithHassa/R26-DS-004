import type { FinancialProfile } from "@/features/personalized-recommendation/types";

/** YAML linked-account profiles currently shipped in the repo. */
const KNOWN_YAML_TAXPAYER_IDS = new Set(["taxpayer_00001"]);

/**
 * Map a Comp 3 financial profile to the transaction-semantic `taxpayer_id`.
 * Prefer the persisted `transaction_taxpayer_id` column when set.
 */
export function profileToTaxpayerId(
  profile: Pick<FinancialProfile, "id" | "full_name" | "transaction_taxpayer_id">,
): string {
  if (profile.transaction_taxpayer_id?.trim()) {
    return profile.transaction_taxpayer_id.trim();
  }

  const slug = profile.full_name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");

  if (KNOWN_YAML_TAXPAYER_IDS.has(slug)) {
    return slug;
  }

  // Demo account naming convention used in seed data.
  if (/taxpayer[_-]?0*1$/i.test(profile.full_name.trim())) {
    return "taxpayer_00001";
  }

  return slug || "taxpayer_00001";
}

export function hasLinkedAccountYaml(taxpayerId: string): boolean {
  return KNOWN_YAML_TAXPAYER_IDS.has(taxpayerId);
}
