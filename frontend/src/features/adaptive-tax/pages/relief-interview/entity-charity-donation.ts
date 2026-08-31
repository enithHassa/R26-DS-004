/**
 * Fifth Schedule 1(a)(iib) approved charity — entities (Rs 500,000).
 * Out of scope for resident-individual Relief Interview / Calculator UX.
 * Individual path remains `donations_approved_charitable` (1(a)(iia), Rs 75,000).
 */

export const ENTITY_CHARITY_DONATION_GROUP =
  "donations_approved_charitable_entity";

export function isEntityCharityDonationGroup(compareGroupId: string): boolean {
  return compareGroupId === ENTITY_CHARITY_DONATION_GROUP;
}
